import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { HealthResponse } from "../api/types";

export function OverviewView({ client }: { client: KernelClient }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const h = await client.health();
        if (!cancelled) {
          setHealth(h);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [client]);

  if (error) {
    return <div className="panel error">Kernel unreachable: {error}</div>;
  }
  if (!health) {
    return <div className="panel">Connecting to kernel...</div>;
  }
  const r = health.resources;
  return (
    <div className="panel">
      <div className="title">Kernel status</div>
      <div className="metrics">
        <div className="metric">
          <strong>{health.ok ? "online" : "degraded"}</strong>
          <small>kernel</small>
        </div>
        <div className="metric">
          <strong>{(r.gpu_name || "CPU").replace("NVIDIA GeForce ", "")}</strong>
          <small>GPU</small>
        </div>
        <div className="metric">
          <strong>{r.vram_total_mb ? `${(r.vram_free_mb / 1024).toFixed(1)} GB` : "-"}</strong>
          <small>VRAM free</small>
        </div>
        <div className="metric">
          <strong>{(r.ram_free_mb / 1024).toFixed(1)} GB</strong>
          <small>RAM free</small>
        </div>
        <div className="metric">
          <strong>{r.disk_free_gb.toFixed(0)} GB</strong>
          <small>Disk free</small>
        </div>
      </div>
    </div>
  );
}
