import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { ApprovalRequestRecord } from "../api/types";

/**
 * Resolving an approval here calls the same `RosterService.resolve_approval()` every
 * other caller (CLI, tests, a future second client) goes through -- this view has no
 * authority of its own, it only ever unblocks the kernel's own pipeline. See
 * ApprovalRequestRecord's own docstring: "resolving one approved does not execute
 * anything; it only unblocks RosterService from issuing the CapabilityGrant."
 */
export function ApprovalsView({ client }: { client: KernelClient }) {
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
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const resolve = async (approvalId: string, approved: boolean) => {
    setBusy(approvalId);
    try {
      await client.resolveApproval(
        approvalId,
        "owner",
        approved,
        reason[approvalId] || (approved ? "approved via desktop" : "denied via desktop"),
      );
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (error) return <div className="panel error">{error}</div>;
  if (!approvals) return <div className="panel">Loading approvals...</div>;
  if (approvals.length === 0) {
    return <div className="panel empty">No pending approvals. The kernel is not waiting on you.</div>;
  }

  return (
    <div className="panel">
      <div className="title">Pending approvals ({approvals.length})</div>
      <div className="approval-list">
        {approvals.map((a) => (
          <div className="approval-card" key={a.id}>
            <div className="approval-head">
              <b>
                {a.subject_id}: {a.action}:{a.scope}
              </b>
              <span className={`badge risk-${a.risk}`}>{a.risk}</span>
            </div>
            <p className="muted">{a.reason}</p>
            <input
              className="reason-input"
              placeholder="Resolution reason (optional)"
              value={reason[a.id] || ""}
              onChange={(e) => setReason({ ...reason, [a.id]: e.target.value })}
            />
            <div className="approval-actions">
              <button
                className="approve"
                disabled={busy === a.id}
                onClick={() => resolve(a.id, true)}
              >
                Approve
              </button>
              <button
                className="deny"
                disabled={busy === a.id}
                onClick={() => resolve(a.id, false)}
              >
                Deny
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
