import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";

export default function Runs() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  useEffect(() => {
    api<{ runs: RunSummary[] }>("/api/runs").then((d) => setRuns(d.runs));
  }, []);
  return (
    <>
      <h1>Runs</h1>
      <p className="sub">Historical executions. Status is projected from the event log.</p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Status</th><th>Run</th><th>Iters</th><th>Score</th><th>Duration</th><th>Tokens</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td><span className={`status ${run.status}`}>{run.status}</span></td>
                <td className="mono"><Link to={`/live/${run.id}`}>{run.id.slice(0, 12)}</Link></td>
                <td>{run.iterations}</td>
                <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                <td>{run.latency_seconds.toFixed(2)}s</td>
                <td>{run.tokens}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
