import { invoke } from "@tauri-apps/api/core";
import type {
  AgentJobRequest,
  AgentProfileRecord,
  ApprovalRequestRecord,
  CapabilityGrantRecord,
  ChainVerification,
  CollaborationEvent,
  CollaborationRoom,
  DelegationRecord,
  HealthResponse,
  JobRecord,
  KernelEvent,
  PresenceRecord,
  RunRecord,
  ToolSpecRecord,
  WorkspaceEntry,
} from "./types";

/**
 * Typed authenticated client over the kernel's local HTTP API
 * (src/sovereign_ai/api/server.py), the "authenticated KernelClient" named in
 * knowledge/research.md step 13 / D-010.
 *
 * The session token this client authenticates with is never embedded in the app bundle
 * or asked of the user: it is read directly off disk by the Rust side
 * (`get_session_token` in src-tauri/src/lib.rs) from the same `state/session.token` file
 * `kernel/auth.py`'s `SessionAuth` already writes for the browser-served `/ui` page to
 * use, and handed to this client once at startup. Both are "the native ... control-plane
 * process" that docstring already names as an intended reader.
 */
export class KernelClient {
  private baseUrl: string;
  private token: string;

  private constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.token = token;
  }

  static async connect(): Promise<KernelClient> {
    const [baseUrl, token] = await Promise.all([
      invoke<string>("get_kernel_base_url"),
      invoke<string>("get_session_token"),
    ]);
    return new KernelClient(baseUrl, token);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const authed = method !== "GET";
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "content-type": "application/json",
        ...(authed ? { Authorization: `Bearer ${this.token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => response.statusText);
      throw new Error(`${method} ${path} -> ${response.status}: ${detail}`);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  health(): Promise<HealthResponse> {
    return this.request("GET", "/health");
  }

  // --- Jobs ---------------------------------------------------------------------

  listJobs(status?: string, limit = 50): Promise<{ jobs: JobRecord[] }> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status) params.set("status", status);
    return this.request("GET", `/jobs?${params.toString()}`);
  }

  cancelJob(jobId: string): Promise<JobRecord> {
    return this.request("DELETE", `/jobs/${encodeURIComponent(jobId)}`);
  }

  listJobRuns(jobId: string): Promise<{ runs: RunRecord[] }> {
    return this.request("GET", `/jobs/${encodeURIComponent(jobId)}/runs`);
  }

  /** Start an agent task. The desktop had no way to do this at all: it could cancel, list
   *  and resolve, but not begin (research wave 7, X-01). */
  submitAgentJob(payload: AgentJobRequest): Promise<JobRecord> {
    return this.request("POST", "/jobs", { kind: "agent", payload });
  }

  // --- What the machine will let an agent touch -----------------------------------

  listWorkspaces(): Promise<{ workspaces: WorkspaceEntry[] }> {
    return this.request("GET", "/workspaces");
  }

  listTools(): Promise<{ tools: ToolSpecRecord[] }> {
    return this.request("GET", "/tools");
  }

  /** Issue a narrow, expiring capability grant.
   *
   *  This is the only way an agent is ever allowed to mutate anything: PolicyEngine's
   *  untrusted-content gate can never return allowed for a model-proposed mutation, so an
   *  "approved" flag on the request cannot authorise one, no matter what a checkbox says
   *  (docs/FIXES.md F-036, F-052). Authority has to come from a human, scoped and
   *  time-bounded. */
  issueGrant(
    subjectId: string,
    action: string,
    scope: string,
    ttlSeconds: number,
    reason: string,
  ): Promise<CapabilityGrantRecord> {
    return this.request("POST", "/roster/grants", {
      subject_id: subjectId,
      action,
      scope,
      ttl_seconds: ttlSeconds,
      reason,
    });
  }

  // --- Live kernel events -----------------------------------------------------------

  /** Follow the kernel journal over server-sent events.
   *
   *  Uses streaming `fetch` rather than `EventSource` because the session token travels in
   *  an Authorization header and `EventSource` cannot set one -- a URL gets logged, cached
   *  and shared in ways a header does not. Returns an abort function.
   *
   *  The server bounds each stream's lifetime on purpose (an unbounded one holds uvicorn's
   *  graceful shutdown open), so a clean close is normal, not an error: the caller
   *  reconnects from `cursor` and misses no event. */
  streamEvents(
    cursor: number,
    onEvent: (event: KernelEvent) => void,
    onState: (state: "live" | "reconnecting", detail?: string) => void,
  ): () => void {
    const controller = new AbortController();
    let attempt = 0;
    let stopped = false;
    let at = cursor;

    const run = async () => {
      while (!stopped) {
        try {
          const response = await fetch(`${this.baseUrl}/events/stream?after=${at}`, {
            headers: { Authorization: `Bearer ${this.token}` },
            signal: controller.signal,
          });
          if (!response.ok || !response.body) throw new Error(`stream ${response.status}`);
          onState("live");
          attempt = 0;
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let split;
            while ((split = buffer.indexOf("\n\n")) >= 0) {
              const frame = buffer.slice(0, split);
              buffer = buffer.slice(split + 2);
              let payload: KernelEvent | null = null;
              for (const line of frame.split("\n")) {
                if (line.startsWith("data: ")) {
                  try {
                    payload = JSON.parse(line.slice(6)) as KernelEvent;
                  } catch {
                    payload = null;
                  }
                }
              }
              if (payload) {
                at = payload.seq;
                onEvent(payload);
              }
            }
          }
        } catch (error) {
          if (stopped || controller.signal.aborted) return;
          const delay = Math.min(30000, 1000 * 2 ** attempt);
          attempt += 1;
          onState("reconnecting", `${Math.round(delay / 1000)}s`);
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
        if (stopped) return;
        // A clean close is the server's bounded stream expiring; reconnect immediately.
        onState("reconnecting", "resuming");
      }
    };
    void run();

    return () => {
      stopped = true;
      controller.abort();
    };
  }

  // --- Roster: agent profiles, delegations, approvals, grants, presence -----------

  listAgentProfiles(): Promise<{ profiles: AgentProfileRecord[] }> {
    return this.request("GET", "/roster/profiles");
  }

  listPendingApprovals(): Promise<{ approvals: ApprovalRequestRecord[] }> {
    return this.request("GET", "/roster/approvals");
  }

  resolveApproval(
    approvalId: string,
    resolverId: string,
    approved: boolean,
    reason: string,
  ): Promise<{ approval: ApprovalRequestRecord; job: JobRecord | null }> {
    return this.request("POST", `/roster/approvals/${encodeURIComponent(approvalId)}/resolve`, {
      resolver_id: resolverId,
      approved,
      reason,
    });
  }

  listDelegations(parentSubjectId: string): Promise<{ delegations: DelegationRecord[] }> {
    const params = new URLSearchParams({ parent_subject_id: parentSubjectId });
    return this.request("GET", `/roster/delegations?${params.toString()}`);
  }

  listActiveGrants(subjectId: string): Promise<{ grants: CapabilityGrantRecord[] }> {
    const params = new URLSearchParams({ subject_id: subjectId });
    return this.request("GET", `/roster/grants?${params.toString()}`);
  }

  getPresence(subjectId: string): Promise<PresenceRecord> {
    return this.request("GET", `/roster/presence/${encodeURIComponent(subjectId)}`);
  }

  // --- Collaboration rooms ---------------------------------------------------------

  listRooms(): Promise<{ rooms: CollaborationRoom[] }> {
    return this.request("GET", "/collaboration/rooms");
  }

  listRoomEvents(roomId: string, limit = 160): Promise<{ events: CollaborationEvent[] }> {
    const params = new URLSearchParams({ limit: String(limit) });
    return this.request("GET", `/collaboration/rooms/${encodeURIComponent(roomId)}/events?${params.toString()}`);
  }

  verifyRoomChain(roomId: string): Promise<ChainVerification> {
    return this.request("GET", `/collaboration/rooms/${encodeURIComponent(roomId)}/verify`);
  }

  postMessage(
    roomId: string,
    actorId: string,
    content: string,
  ): Promise<{ event: CollaborationEvent; jobs: JobRecord[] }> {
    return this.request("POST", `/collaboration/rooms/${encodeURIComponent(roomId)}/messages`, {
      actor_id: actorId,
      content,
    });
  }
}
