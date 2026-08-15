import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { CountBar, MetricChart, ScoreChart } from "../charts";
import { Kpi, StatusChip } from "../motion/Kpi";

type Row = {
  id: string;
  kind?: string;
  name?: string;
  status: string;
  best_score?: number | null;
  iterations?: number;
  passes?: number;
  latency_seconds: number;
  tokens: number;
  href?: string;
  provider?: string;
};

export default function Observability() {
  const [runs, setRuns] = useState<Row[]>([]);
  useEffect(() => {
    api<{ runs: Row[] }>("/api/activity").then((d) => setRuns(d.runs));
  }, []);
  const chrono = [...runs].reverse();
  const scoreChart = chrono.filter((r) => r.best_score != null).map((r, i) => ({ iteration: i + 1, score: r.best_score as number }));
  const tokenChart = chrono.map((r, i) => ({ iteration: i + 1, tokens: r.tokens || 0 }));
  const latencyChart = chrono.map((r, i) => ({ iteration: i + 1, latency: r.latency_seconds || 0 }));
  const statuses = Object.entries(
    runs.reduce<Record<string, number>>((acc, r) => {
      acc[r.status] = (acc[r.status] || 0) + 1;
      return acc;
    }, {}),
  ).map(([status, count]) => ({ status, count }));
  return (
    <>
      <h1>Observability</h1>
      <p className="sub">Loops and graphs projected from the event log: score, tokens, latency, status mix.</p>
      <div className="kpis dense">
        <Kpi title="Events / runs" value={runs.length} />
        <Kpi title="Tokens" value={runs.reduce((a, r) => a + (r.tokens || 0), 0)} />
        <Kpi title="Mean latency" value={runs.length ? runs.reduce((a, r) => a + r.latency_seconds, 0) / runs.length : 0} suffix="s" digits={2} />
        <Kpi title="Graphs" value={runs.filter((r) => r.kind === "graph").length} />
      </div>
      <div className="grid3">
        <div className="card"><h3>Score</h3><ScoreChart data={scoreChart} /></div>
        <div className="card"><h3>Tokens</h3><MetricChart data={tokenChart} dataKey="tokens" /></div>
        <div className="card"><h3>Latency (s)</h3><MetricChart data={latencyChart} dataKey="latency" color="#3dd68c" /></div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Status mix</h3>
        <CountBar data={statuses} nameKey="status" valueKey="count" />
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <table>
          <thead>
            <tr><th>Name</th><th>Type</th><th>Status</th><th>Score</th><th>Iters</th><th>Latency</th><th>Tokens</th></tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className="row-enter">
                <td>
                  <Link to={run.href || (run.kind === "graph" ? `/graph/${run.id}` : `/live/${run.id}`)}>
                    {run.name || "Untitled"}
                  </Link>
                </td>
                <td>{run.kind}</td>
                <td><StatusChip status={run.status} /></td>
                <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                <td>{run.iterations ?? run.passes ?? 0}</td>
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
