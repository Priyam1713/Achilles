import { useEffect, useState } from "react";
import type { KernelClient } from "../api/kernelClient";
import type { JobRecord } from "../api/types";

export function JobsView({ client }: { client: KernelClient }) {
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const { jobs: list } = await client.listJobs(undefined, 50);
      setJobs(list);
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

  const cancel = async (jobId: string) => {
    setBusy(jobId);
    try {
      await client.cancelJob(jobId);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (error) return <div className="panel error">{error}</div>;
  if (!jobs) return <div className="panel">Loading jobs...</div>;
  if (jobs.length === 0) return <div className="panel empty">No jobs yet.</div>;

  return (
    <div className="panel">
      <div className="title">Jobs ({jobs.length})</div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Kind</th>
            <th>Status</th>
            <th>Created</th>
            <th>Error</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <b>{job.kind}</b>
                <div className="muted">{job.id.slice(0, 8)}</div>
              </td>
              <td>
                <span className={`badge status-${job.status}`}>{job.status}</span>
              </td>
              <td className="muted">{new Date(job.created_at * 1000).toLocaleTimeString()}</td>
              <td className="muted error-text">{job.error ? job.error.slice(0, 80) : ""}</td>
              <td>
                {(job.status === "queued" || job.status === "running") && (
                  <button
                    className="row-action"
                    disabled={busy === job.id}
                    onClick={() => cancel(job.id)}
                  >
                    Cancel
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
