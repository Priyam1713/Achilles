import { useCallback, useEffect, useRef, useState } from "react";
import { KernelClient } from "./api/kernelClient";
import type { HealthResponse, KernelEvent } from "./api/types";
import { OverviewView } from "./views/OverviewView";
import { RosterView } from "./views/RosterView";
import { JobsView } from "./views/JobsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { CollaborationView } from "./views/CollaborationView";
import { WorkView } from "./views/WorkView";
import { ToolsView } from "./views/ToolsView";
import "./App.css";

type Tab = "work" | "approvals" | "tools" | "roster" | "jobs" | "collaboration" | "overview";

const TABS: { id: Tab; label: string }[] = [
  { id: "work", label: "Work" },
  { id: "approvals", label: "Approvals" },
  { id: "tools", label: "Tools" },
  { id: "roster", label: "Roster" },
  { id: "jobs", label: "Jobs" },
  { id: "collaboration", label: "Collaboration" },
  { id: "overview", label: "Overview" },
];

/** How many journal events to keep in memory. The stream is unbounded; a desktop window
 *  left open for a day is not a reason to hold every event ever emitted. */
const EVENT_WINDOW = 400;

function App() {
  const [client, setClient] = useState<KernelClient | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [tab, setTab] = useState<Tab>("work");
  const [events, setEvents] = useState<KernelEvent[]>([]);
  const [streamState, setStreamState] = useState<"live" | "reconnecting" | "offline">("offline");
  const [streamDetail, setStreamDetail] = useState<string>("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  /* A failed first connection used to be terminal: connect() ran once and the window sat
     on an error panel until it was restarted (research wave 7, X-09). A local kernel is a
     process on the same machine that will be down sometimes; that is a normal state to
     design for, not an exception. */
  const connect = useCallback(() => {
    setConnecting(true);
    setConnectError(null);
    KernelClient.connect()
      .then((connected) => {
        setClient(connected);
        setConnecting(false);
      })
      .catch((e) => {
        setConnectError((e as Error).message);
        setConnecting(false);
      });
  }, []);

  useEffect(connect, [connect]);

  /* One stream for the whole window. Every view reads from it rather than running its own
     four-second timer, which is what D-027 actually asks for. */
  useEffect(() => {
    if (!client) return;
    const stop = client.streamEvents(
      0,
      (event) =>
        setEvents((current) => {
          const next = [...current, event];
          return next.length > EVENT_WINDOW ? next.slice(next.length - EVENT_WINDOW) : next;
        }),
      (state, detail) => {
        setStreamState(state);
        setStreamDetail(detail ?? "");
      },
    );
    return stop;
  }, [client]);

  useEffect(() => {
    if (!client) return;
    let cancelled = false;
    const poll = () =>
      client
        .health()
        .then((h) => !cancelled && setHealth(h))
        .catch(() => undefined);
    poll();
    /* Resource numbers change without emitting events, so they are the one thing still on
       a timer -- and a slow one. */
    const id = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [client]);

  useEffect(() => {
    if (!client) return;
    client
      .listPendingApprovals()
      .then(({ approvals }) => setPendingApprovals(approvals.length))
      .catch(() => undefined);
  }, [client, events]);

  const onTabKey = (index: number) => (e: React.KeyboardEvent) => {
    const delta = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const next = (index + delta + TABS.length) % TABS.length;
    setTab(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

  const resources = health?.resources;

  return (
    <div className="shell">
      <a className="skip" href="#content">
        Skip to main content
      </a>

      <header className="top">
        <div className="brand">
          ACHILLES
          <small>local sovereign kernel</small>
        </div>

        <span className="conn" role="status" aria-live="polite">
          <span className={`dot ${streamState}`} />
          {streamState === "live"
            ? "live"
            : streamState === "reconnecting"
              ? `reconnecting ${streamDetail}`
              : "offline"}
        </span>

        {resources && (
          <div className="gauges" aria-label="Machine resources">
            <div className="gauge">
              <b>{(resources.gpu_name || "CPU").replace("NVIDIA GeForce ", "")}</b>
              <small>GPU</small>
            </div>
            <div className="gauge">
              <b>{resources.vram_total_mb ? `${(resources.vram_free_mb / 1024).toFixed(1)} GB` : "—"}</b>
              <small>VRAM free</small>
            </div>
            <div className="gauge">
              <b>{(resources.ram_free_mb / 1024).toFixed(1)} GB</b>
              <small>RAM free</small>
            </div>
            <div className="gauge">
              <b>{resources.disk_free_gb.toFixed(0)} GB</b>
              <small>disk free</small>
            </div>
          </div>
        )}
      </header>

      <nav className="tabs" role="tablist" aria-label="Sections">
        {TABS.map((t, index) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-controls="content"
            aria-selected={tab === t.id}
            tabIndex={tab === t.id ? 0 : -1}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onKeyDown={onTabKey(index)}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === "approvals" && pendingApprovals > 0 && (
              <span className="badge risk-high"> {pendingApprovals}</span>
            )}
          </button>
        ))}
      </nav>

      <main className="content" id="content" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {connectError && (
          <div className="panel error">
            <b>Could not reach the kernel.</b>
            <div className="muted small">{connectError}</div>
            <p className="muted small">
              Start it with <span className="mono">./scripts/start.ps1</span> (or{" "}
              <span className="mono">uv run sovereign serve</span>), then retry.
            </p>
            <button className="primary" onClick={connect}>
              Retry connection
            </button>
          </div>
        )}
        {!connectError && connecting && <div className="panel">Connecting to kernel…</div>}
        {client && tab === "work" && <WorkView client={client} events={events} />}
        {client && tab === "approvals" && <ApprovalsView client={client} events={events} />}
        {client && tab === "tools" && <ToolsView client={client} events={events} />}
        {client && tab === "roster" && <RosterView client={client} />}
        {client && tab === "jobs" && <JobsView client={client} />}
        {client && tab === "collaboration" && <CollaborationView client={client} />}
        {client && tab === "overview" && <OverviewView client={client} />}
      </main>

      <div className="footer">THE MODEL IS A COMPONENT. THE KERNEL IS THE SYSTEM.</div>
    </div>
  );
}

export default App;
