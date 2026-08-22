import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { ApprovalRequestRecord, KernelEvent } from "../api/types";

/**
 * Resolving an approval here calls the same `RosterService.resolve_approval()` every other
 * caller (CLI, tests, the web surface) goes through -- this view has no authority of its
 * own, it only ever unblocks the kernel's own pipeline.
 *
 * What changed (research wave 7, X-03; `knowledge/research.md` D-028): it used to render a
 * subject id, an `action:scope` string, a risk badge and free text, and nothing about what
 * was actually being authorised. An operator repeatedly asked to approve things they cannot
 * see learns to click Approve without reading, which turns the strongest safety mechanism
 * in this project into a rubber stamp. So the evidence now leads, and when there is none,
 * the card says so in as many words rather than looking complete.
 */
export function ApprovalsView({
  client,
  events,
}: {
  client: KernelClient;
  events: KernelEvent[];
}) {
  const [approvals, setApprovals] = useState<ApprovalRequestRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reason, setReason] = useState<Record<string, string>>({});

  const refresh = async () => {
    try {
      const { approvals: list } = await client.listPendingApprovals();
      setApprovals(list);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  /* Driven by the shared event stream instead of a four-second timer: an approval that
     appears while you are looking at this tab should appear, not wait (D-027). */
  useEffect(() => {
    if (events.some((e) => e.event_type.startsWith("approval.") || e.event_type.startsWith("job."))) {
      refresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  const resolve = async (approvalId: string, approved: boolean) => {
    setBusy(approvalId);
    try {
      await client.resolveApproval(
        approvalId,
        "desktop-operator",
        approved,
        reason[approvalId] ||
          (approved ? "approved from the desktop" : "denied from the desktop"),
      );
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (error) return <div className="panel error">{error}</div>;
  if (!approvals) return <div className="panel">Loading approvals…</div>;
  if (approvals.length === 0) {
    return <div className="panel empty">No pending approvals. The kernel is not waiting on you.</div>;
  }

  return (
    <div className="panel">
      <div className="title">Pending approvals ({approvals.length})</div>
      <div className="approval-list">
        {approvals.map((a) => {
          const hasEvidence = a.evidence && Object.keys(a.evidence).length > 0;
          return (
            <div className="approval-card" key={a.id}>
              <div className="approval-head">
                <b>
                  {a.action}:{a.scope}
                </b>
                <span className={`badge risk-${a.risk}`}>{a.risk}</span>
              </div>

              <dl className="kv">
                <dt>subject</dt>
                <dd className="mono">{a.subject_id}</dd>
                <dt>why asked</dt>
                <dd>{a.reason}</dd>
                <dt>expires</dt>
                <dd>{new Date(a.expires_at * 1000).toLocaleTimeString()}</dd>
                <dt>evidence</dt>
                <dd>
                  {hasEvidence ? (
                    <pre className="mono">{JSON.stringify(a.evidence, null, 2)}</pre>
                  ) : (
                    <span className="muted">
                      none recorded — approving means trusting the request text alone
                    </span>
                  )}
                </dd>
              </dl>

              <input
                className="reason-input"
                aria-label="Resolution reason"
                placeholder="Reason (recorded with your decision)"
                value={reason[a.id] || ""}
                onChange={(e) => setReason({ ...reason, [a.id]: e.target.value })}
              />
              <div className="approval-actions">
                <button className="approve" disabled={busy === a.id} onClick={() => resolve(a.id, true)}>
                  Approve
                </button>
                <button className="deny" disabled={busy === a.id} onClick={() => resolve(a.id, false)}>
                  Deny
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
