import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { AgentProfileRecord, PresenceRecord } from "../api/types";

/**
 * Real roster view (knowledge/research.md step 13): lists every durable `AgentProfile`
 * and its derived presence (kernel/presence.py -- computed from active grants/leases/jobs,
 * never self-asserted). This intentionally does not offer a "create profile" form yet:
 * the backend endpoint exists (`POST /roster/profiles`), but a first vertical slice reads
 * real state before it writes it, per the "grow by real backend behavior, not app parity"
 * sequencing this desktop app is scoped to.
 */
export function RosterView({ client }: { client: KernelClient }) {
  const [profiles, setProfiles] = useState<AgentProfileRecord[] | null>(null);
  const [presence, setPresence] = useState<Record<string, PresenceRecord>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { profiles: list } = await client.listAgentProfiles();
        if (cancelled) return;
        setProfiles(list);
        const entries = await Promise.all(
          list.map(async (p) => [p.id, await client.getPresence(p.id)] as const),
        );
        if (!cancelled) setPresence(Object.fromEntries(entries));
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  if (error) return <div className="panel error">{error}</div>;
  if (!profiles) return <div className="panel">Loading roster...</div>;
  if (profiles.length === 0) {
    return <div className="panel empty">No agent profiles registered yet.</div>;
  }

  return (
    <div className="panel">
      <div className="title">Roster ({profiles.length})</div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Role</th>
            <th>Status</th>
            <th>Presence</th>
            <th>Authority ceiling</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => {
            const pres = presence[p.id];
            return (
              <tr key={p.id}>
                <td>
                  <b>{p.display_name}</b>
                  <div className="muted">{p.id}</div>
                </td>
                <td>{p.role}</td>
                <td>
                  <span className={`badge status-${p.status}`}>{p.status}</span>
                </td>
                <td>
                  {pres ? (
                    <span className={`badge ${pres.active ? "status-active" : "status-idle"}`}>
                      {pres.active ? "active" : "idle"}
                    </span>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="muted">{p.authority_ceiling.join(", ") || "none"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
