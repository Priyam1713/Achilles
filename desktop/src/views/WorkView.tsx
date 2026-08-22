import { useEffect, useMemo, useRef, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { JobRecord, KernelEvent, WorkspaceEntry } from "../api/types";

/**
 * The desktop's front door.
 *
 * Research wave 7's first severity-1 finding was that no surface in this project could
 * *start* work: the desktop could cancel, list and resolve, and the only way to make the
 * system do anything was an `@mention` in a collaboration room or a hand-written HTTP
 * request. This view is the missing half (`knowledge/research.md` D-026), and it renders
 * each step as it arrives rather than after the run, because on hardware measured at
 * 6-52 tok/s an undifferentiated wait is the worst possible way to present the one
 * property this system cannot hide (`D-029`).
 */

interface Step {
  index: string;
  title: string;
  kind: "" | "denied" | "error" | "done" | "note";
  detail: string;
  elapsed: string;
}

function parsePayload(event: KernelEvent): Record<string, any> {
  try {
    return JSON.parse(event.payload_json ?? "{}");
  } catch {
    return {};
  }
}

/** What actually happened, in one line. Falls back to raw JSON rather than hiding it. */
function summarise(observation: Record<string, any>): string {
  if (observation.denied || observation.error) return String(observation.error ?? "denied");
  for (const key of ["path", "root", "query", "capability"]) {
    if (key in observation) {
      for (const count of ["count", "total", "replacements", "bytes_written", "returncode"]) {
        if (count in observation) return `${observation[key]}  (${count}=${observation[count]})`;
      }
      return String(observation[key]);
    }
  }
  return JSON.stringify(observation).slice(0, 200);
}

export function WorkView({
  client,
  events,
}: {
  client: KernelClient;
  events: KernelEvent[];
}) {
  const [workspaces, setWorkspaces] = useState<WorkspaceEntry[] | null>(null);
  const [workspace, setWorkspace] = useState("");
  const [task, setTask] = useState("");
  const [capability, setCapability] = useState("tool_routing");
  const [mode, setMode] = useState("smart");
  const [maxSteps, setMaxSteps] = useState(8);
  const [authorise, setAuthorise] = useState(false);
  const [grantNote, setGrantNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [runHead, setRunHead] = useState("No run yet. Describe a task and start one.");
  const [jobs, setJobs] = useState<JobRecord[]>([]);

  const consumed = useRef(0);
  const runStart = useRef(0);
  const lastStep = useRef(0);
  const stepCount = useRef(0);
  const log = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    client
      .listWorkspaces()
      .then(({ workspaces: list }) => {
        setWorkspaces(list);
        if (list.length) setWorkspace(list[0].path);
      })
      .catch((e) => setError((e as Error).message));
  }, [client]);

  const refreshJobs = useMemo(
    () => async () => {
      try {
        const { jobs: list } = await client.listJobs(undefined, 8);
        setJobs(list);
      } catch {
        /* the connection pill in the header already tells this story */
      }
    },
    [client],
  );

  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  /* Steps come from the shared event stream, not from polling. Only events belonging to
     the run being watched are rendered -- forgetting to clear the previous run id is what
     made the second task of a session silently render nothing on the web surface. */
  useEffect(() => {
    if (consumed.current > events.length) consumed.current = 0;
    const fresh = events.slice(consumed.current);
    consumed.current = events.length;
    if (!fresh.length) return;

    let touchedJobs = false;
    for (const event of fresh) {
      if (event.event_type.startsWith("job.")) touchedJobs = true;
      if (!runId || !event.stream_id.endsWith(runId)) continue;
      const payload = parsePayload(event);
      const elapsed = lastStep.current ? `${((Date.now() - lastStep.current) / 1000).toFixed(1)}s` : "";
      lastStep.current = Date.now();

      if (event.event_type === "agent.step.tool_call") {
        const observation = payload.observation ?? {};
        stepCount.current += 1;
        pushStep({
          index: String(stepCount.current),
          title: String(payload.tool ?? "tool"),
          kind: observation.denied ? "denied" : observation.error ? "error" : "",
          detail: summarise(observation),
          elapsed,
        });
      } else if (event.event_type === "agent.step.done") {
        stepCount.current += 1;
        pushStep({
          index: String(stepCount.current),
          title: "done",
          kind: "done",
          detail: String(payload.summary ?? ""),
          elapsed,
        });
        setRunHead(
          `run ${runId} — finished in ${((Date.now() - runStart.current) / 1000).toFixed(1)}s over ${stepCount.current} steps`,
        );
        setBusy(false);
      } else if (event.event_type === "agent.step.unparsable") {
        stepCount.current += 1;
        pushStep({
          index: String(stepCount.current),
          title: "unparsable reply",
          kind: "error",
          detail: "the model did not emit a usable action",
          elapsed,
        });
      } else if (event.event_type === "agent.checkpoint.created") {
        pushStep({
          index: "·",
          title: "checkpoint",
          kind: "note",
          detail: `${String(payload.sha ?? "").slice(0, 12)} — this edit can be undone`,
          elapsed: "",
        });
      } else if (event.event_type === "agent.context.compacted") {
        pushStep({
          index: "·",
          title: "context compacted",
          kind: "note",
          detail: `${payload.elided_turns} earlier steps elided to fit the budget`,
          elapsed: "",
        });
      } else if (event.event_type === "agent.decoding.degraded") {
        pushStep({
          index: "·",
          title: "decoding degraded",
          kind: "error",
          detail: "backend refused the action schema; falling back to prose parsing",
          elapsed: "",
        });
      }
    }
    if (touchedJobs) refreshJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, runId]);

  function pushStep(step: Step) {
    const host = log.current;
    /* Follow the tail only if the reader was already at it. The old surface yanked scroll
       to the bottom on every poll, which made reading history impossible (X-11). */
    const stick = host ? host.scrollHeight - host.scrollTop - host.clientHeight < 60 : true;
    setSteps((current) => [...current, step]);
    if (stick) requestAnimationFrame(() => host && (host.scrollTop = host.scrollHeight));
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    setSteps([]);
    setRunId(null);
    stepCount.current = 0;
    runStart.current = Date.now();
    lastStep.current = Date.now();
    try {
      if (authorise) {
        const grant = await client.issueGrant(
          "desktop-operator",
          "write",
          "workspace",
          900,
          "authorised from the desktop for one run",
        );
        setGrantNote(
          `granted write:workspace to desktop-operator until ${new Date(grant.expires_at * 1000).toLocaleTimeString()}`,
        );
      }
      const job = await client.submitAgentJob({
        task: task.trim(),
        workspace,
        capability,
        mode,
        max_steps: maxSteps,
        approved: authorise,
        agent_profile_id: "desktop-operator",
      });
      setRunHead(`job ${job.id.slice(0, 8)} queued — steps appear as they happen`);
      refreshJobs();
      for (let i = 0; i < 40; i += 1) {
        const { runs } = await client.listJobRuns(job.id);
        if (runs.length) {
          setRunId(runs[runs.length - 1].id);
          setRunHead(`run ${runs[runs.length - 1].id} — live`);
          return;
        }
        await new Promise((r) => setTimeout(r, 250));
      }
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="work-grid">
      <section className="panel">
        <div className="title">Give it a task</div>
        <form onSubmit={start}>
          <label htmlFor="ws">Workspace</label>
          <select id="ws" value={workspace} onChange={(e) => setWorkspace(e.target.value)} required>
            {(workspaces ?? []).map((w) => (
              <option key={w.path} value={w.path}>
                {w.label}
                {w.writable ? "" : " (read-only)"} — {w.path}
              </option>
            ))}
          </select>
          <p className="muted small">
            {workspaces && workspaces.length === 0
              ? "No workspace is registered. Run:  sovereign workspace add <path>"
              : "Knowing a path never grants authority; only registered directories appear here."}
          </p>

          <label htmlFor="task">Task</label>
          <textarea
            id="task"
            value={task}
            required
            onChange={(e) => setTask(e.target.value)}
            placeholder="e.g. read config.env and tell me what ANSWER is"
          />

          <div className="field-row">
            <div>
              <label htmlFor="cap">Capability</label>
              <select id="cap" value={capability} onChange={(e) => setCapability(e.target.value)}>
                <option>coding</option>
                <option>tool_routing</option>
                <option>reasoning</option>
                <option>planning</option>
              </select>
            </div>
            <div>
              <label htmlFor="mode">Mode</label>
              <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
                <option>fast</option>
                <option>smart</option>
                <option>deep</option>
              </select>
            </div>
            <div>
              <label htmlFor="budget">Step budget</label>
              <input
                id="budget"
                type="number"
                min={1}
                max={25}
                value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value) || 8)}
              />
            </div>
          </div>

          <label className="checkline">
            <input type="checkbox" checked={authorise} onChange={(e) => setAuthorise(e.target.checked)} />
            <span>Authorise file writes for 15 minutes</span>
          </label>
          <p className="muted small">
            {grantNote ??
              "Checking this issues a real write:workspace capability grant to desktop-operator, expiring in 15 minutes. Without it a write is refused — an agent cannot authorise its own mutation, and no checkbox here can change that."}
          </p>

          <button className="primary" type="submit" disabled={busy || !workspace}>
            {busy ? "Running…" : "Run task"}
          </button>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
        </form>
      </section>

      <section className="panel">
        <div className="title">Live run</div>
        <p className="muted small">{runHead}</p>
        <div className="steps" ref={log} aria-live="polite" aria-label="Agent steps">
          {steps.length === 0 ? (
            <p className="empty">steps appear here as the agent works</p>
          ) : (
            steps.map((step, i) => (
              <div className={`step ${step.kind}`} key={`${step.index}-${i}`}>
                <span className="step-n">{step.index}</span>
                <span className="step-body">
                  <span className="step-title">{step.title}</span>
                  {step.elapsed && <span className="muted small"> {step.elapsed}</span>}
                  <div className="muted small">{step.detail}</div>
                </span>
              </div>
            ))
          )}
        </div>

        <div className="title" style={{ marginTop: 18 }}>
          Recent jobs
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>kind</th>
              <th>status</th>
              <th>created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={4} className="empty">
                  no jobs yet
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <b>{job.kind}</b>
                    <div className="muted">{job.id.slice(0, 8)}</div>
                  </td>
                  <td>
                    <span className={`badge status-${job.status}`}>{job.status}</span>
                  </td>
                  <td className="muted">{new Date(job.created_at * 1000).toLocaleTimeString()}</td>
                  <td>
                    {(job.status === "queued" || job.status === "running") && (
                      <button
                        className="row-action"
                        onClick={async () => {
                          try {
                            await client.cancelJob(job.id);
                            refreshJobs();
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
