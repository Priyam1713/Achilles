import { useEffect, useState } from "react";
import { KernelClient } from "./api/kernelClient";
import { OverviewView } from "./views/OverviewView";
import { RosterView } from "./views/RosterView";
import { JobsView } from "./views/JobsView";
import { ApprovalsView } from "./views/ApprovalsView";
import { CollaborationView } from "./views/CollaborationView";
import "./App.css";

type Tab = "overview" | "roster" | "jobs" | "approvals" | "collaboration";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "roster", label: "Roster" },
  { id: "jobs", label: "Jobs" },
  { id: "approvals", label: "Approvals" },
  { id: "collaboration", label: "Collaboration" },
];

function App() {
  const [client, setClient] = useState<KernelClient | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    KernelClient.connect()
      .then(setClient)
      .catch((e) => setConnectError((e as Error).message));
  }, []);

  return (
    <div className="shell">
      <div className="top">
        <div className="brand">LOCAL SOVEREIGN AI</div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>
      <main className="content">
        {connectError && (
          <div className="panel error">
            Could not reach the kernel: {connectError}
            <br />
            <span className="muted">
              Start it with Run.ps1 (or `python -m sovereign_ai.cli serve`) first.
            </span>
          </div>
        )}
        {!connectError && !client && <div className="panel">Connecting to kernel...</div>}
        {client && tab === "overview" && <OverviewView client={client} />}
        {client && tab === "roster" && <RosterView client={client} />}
        {client && tab === "jobs" && <JobsView client={client} />}
        {client && tab === "approvals" && <ApprovalsView client={client} />}
        {client && tab === "collaboration" && <CollaborationView client={client} />}
      </main>
      <div className="footer">THE MODEL IS A COMPONENT. THE KERNEL IS THE SYSTEM.</div>
    </div>
  );
}

export default App;
