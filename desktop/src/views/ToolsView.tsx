import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { KernelEvent, ToolSpecRecord } from "../api/types";

/**
 * What an agent can actually invoke, and what the kernel is doing right now.
 *
 * Worth a view of its own because until the tool plane existed (`docs/FIXES.md` F-047) the
 * honest answer to "what can this system do?" was three read-only tools, regardless of the
 * hundreds of gigabytes of models installed. Showing the roster -- with which tools can
 * mutate and under what risk scope -- is the difference between a capability claim and a
 * capability.
 */
export function ToolsView({
  client,
  events,
}: {
  client: KernelClient;
  events: KernelEvent[];
}) {
  const [tools, setTools] = useState<ToolSpecRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client
      .listTools()
      .then(({ tools: list }) => setTools(list))
      .catch((e) => setError((e as Error).message));
  }, [client]);

  const recent = events.slice(-60).reverse();

  return (
    <div className="work-grid">
      <section className="panel">
        <div className="title">Tool plane {tools ? `(${tools.length})` : ""}</div>
        {error && <div className="error-text">{error}</div>}
        <table className="data-table">
          <thead>
            <tr>
              <th>tool</th>
              <th>scope</th>
              <th>description</th>
            </tr>
          </thead>
          <tbody>
            {(tools ?? []).map((tool) => (
              <tr key={tool.id}>
                <td>
                  <b className="mono">{tool.id}</b>
                  {tool.mutating && <span className="badge risk-medium"> mutating</span>}
                </td>
                <td className="muted">{tool.risk_scope}</td>
                <td>{tool.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="title">Kernel event stream</div>
        <p className="muted small">
          The append-only journal, live. Every step an agent takes, every grant, every
          checkpoint — the record the audit story rests on.
        </p>
        <div className="steps" aria-live="polite" aria-label="Kernel events">
          {recent.length === 0 ? (
            <p className="empty">waiting for events…</p>
          ) : (
            recent.map((event) => (
              <div className="step" key={event.seq}>
                <span className="step-n">{event.seq}</span>
                <span className="step-body">
                  <span className="step-title mono">{event.event_type}</span>
                  <div className="muted small">
                    {event.stream_id} · {event.trust}
                  </div>
                </span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
