import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";
import { MetricChart, ScoreChart } from "../charts";

export default function Observability() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  useEffect(() => {
    api<{ runs: RunSummary[] }>("/api/runs").then((d) => setRuns(d.runs));
  }, []);
  const ordered = runs.filter((r) => r.best_score != null).slice().reverse();
  const scoreChart = ordered.map((r, i) => ({ iteration: i + 1, score: r.best_score as number }));
  const tokenChart = ordered.map((r, i) => ({ iteration: i + 1, tokens: r.tokens }));
  const latencyChart = ordered.map((r, i) => ({ iteration: i + 1, latency: r.latency_seconds }));
  return (
    <>
      <h1>Observability</h1>
      <p className="sub">Event-sourced projections from the LLM plant — score, tokens, latency.</p>
      <div className="grid2">
        <div className="card">
          <h3>Score</h3>
          <ScoreChart data={scoreChart} />
        </div>
        <div className="card">
          <h3>Tokens</h3>
          <MetricChart data={tokenChart} dataKey="tokens" />
        </div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Latency (s)</h3>
        <MetricChart data={latencyChart} dataKey="latency" color="#3dd68c" />
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <table>
          <thead>
            <tr><th>Run</th><th>Status</th><th>Score</th><th>Iters</th><th>Latency</th><th>Tokens</th></tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="mono"><Link to={`/live/${run.id}`}>{run.id.slice(0, 10)}</Link></td>
                <td>{run.status}</td>
                <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                <td>{run.iterations}</td>
                <td>{run.latency_seconds.toFixed(2)}</td>
                <td>{run.tokens}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
