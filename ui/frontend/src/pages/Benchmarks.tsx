import { useEffect, useMemo, useState } from "react";
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
  graph_name?: string;
};

function stats(nums: number[]) {
  if (!nums.length) return { n: 0, min: 0, max: 0, mean: 0, p50: 0 };
  const s = [...nums].sort((a, b) => a - b);
  const mean = s.reduce((a, b) => a + b, 0) / s.length;
  const p50 = s[Math.floor(s.length / 2)] || 0;
  return { n: s.length, min: s[0], max: s[s.length - 1], mean, p50 };
}

export default function Benchmarks() {
  const [rows, setRows] = useState<Row[]>([]);
  const [kind, setKind] = useState("all");
  useEffect(() => {
    api<{ runs: Row[] }>("/api/activity").then((d) => setRows(d.runs)).catch(console.error);
  }, []);
  const filtered = useMemo(() => (kind === "all" ? rows : rows.filter((r) => r.kind === kind)), [rows, kind]);
  const loops = filtered.filter((r) => r.kind === "loop");
  const graphs = filtered.filter((r) => r.kind === "graph");
  const scores = loops.map((r) => r.best_score).filter((x): x is number => x != null);
  const tokens = filtered.map((r) => r.tokens || 0);
  const lats = filtered.map((r) => r.latency_seconds || 0);
  const iters = filtered.map((r) => r.iterations ?? r.passes ?? 0);
  const ss = stats(scores);
  const ts = stats(tokens);
  const ls = stats(lats);
  const is = stats(iters);
  const chrono = [...filtered].reverse();
  const scoreChart = chrono.filter((r) => r.best_score != null).map((r, i) => ({ iteration: i + 1, score: r.best_score as number }));
  const tokenChart = chrono.map((r, i) => ({ iteration: i + 1, tokens: r.tokens || 0 }));
  const latChart = chrono.map((r, i) => ({ iteration: i + 1, latency: r.latency_seconds || 0 }));
  const iterChart = chrono.map((r, i) => ({ iteration: i + 1, passes: r.iterations ?? r.passes ?? 0 }));
  const statusCounts = Object.entries(
    filtered.reduce<Record<string, number>>((acc, r) => {
      acc[r.status] = (acc[r.status] || 0) + 1;
      return acc;
    }, {}),
  ).map(([status, count]) => ({ status, count }));
  const providerCounts = Object.entries(
    filtered.reduce<Record<string, number>>((acc, r) => {
      const p = r.provider || "unset";
      acc[p] = (acc[p] || 0) + 1;
      return acc;
    }, {}),
  ).map(([provider, count]) => ({ provider, count }));

  return (
    <>
      <h1>Benchmarks</h1>
      <p className="sub">Loops and graphs side by side: quality, tokens, latency, iterations, status, providers. Filter does not reload the page.</p>
      <div className="chips">
        {["all", "graph", "loop"].map((k) => (
          <button key={k} type="button" className={`chip btn-press ${kind === k ? "ok" : ""}`} onClick={() => setKind(k)}>
            {k}
          </button>
        ))}
        <span className="chip">{filtered.length} runs</span>
      </div>
      <div className="kpis dense">
        <Kpi title="Runs" value={filtered.length} hint={`${graphs.length} graphs · ${loops.length} loops`} />
        <Kpi title="Mean score" value={ss.mean} digits={3} hint={`min ${ss.min.toFixed(3)} · max ${ss.max.toFixed(3)}`} />
        <Kpi title="Median score" value={ss.p50} digits={3} />
        <Kpi title="Mean tokens" value={ts.mean} digits={0} hint={`max ${ts.max}`} />
        <Kpi title="Mean latency" value={ls.mean} suffix="s" digits={2} hint={`max ${ls.max.toFixed(2)}s`} />
        <Kpi title="Mean iters/passes" value={is.mean} digits={1} />
        <Kpi title="Converged loops" value={loops.filter((r) => r.status === "converged").length} />
        <Kpi title="Failed" value={filtered.filter((r) => r.status === "failed").length} />
      </div>
      <div className="grid3">
        <div className="card"><h3>Score series</h3><ScoreChart data={scoreChart} /></div>
        <div className="card"><h3>Tokens</h3><MetricChart data={tokenChart} dataKey="tokens" /></div>
        <div className="card"><h3>Latency</h3><MetricChart data={latChart} dataKey="latency" color="#3dd68c" /></div>
      </div>
      <div className="grid3" style={{ marginTop: 12 }}>
        <div className="card"><h3>Iterations / passes</h3><MetricChart data={iterChart} dataKey="passes" color="#f5c542" /></div>
        <div className="card"><h3>Status</h3><CountBar data={statusCounts} nameKey="status" valueKey="count" /></div>
        <div className="card"><h3>Provider</h3><CountBar data={providerCounts} nameKey="provider" valueKey="count" color="#8b7cff" /></div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Full cohort</h3>
        <table>
          <thead>
            <tr><th>Name</th><th>Type</th><th>Status</th><th>Score</th><th>Iters</th><th>Tokens</th><th>Latency</th><th>Provider</th></tr>
          </thead>
          <tbody>
            {filtered.map((run) => (
              <tr key={run.id} className="row-enter">
                <td>
                  <Link to={run.href || (run.kind === "graph" ? `/graph/${run.id}` : `/live/${run.id}`)}>
                    {run.name || run.graph_name || "Untitled"}
                  </Link>
                </td>
                <td>{run.kind}</td>
                <td><StatusChip status={run.status} /></td>
                <td>{run.best_score != null ? run.best_score.toFixed(3) : "—"}</td>
                <td>{run.iterations ?? run.passes ?? 0}</td>
                <td>{run.tokens}</td>
                <td>{run.latency_seconds.toFixed(2)}</td>
                <td>{run.provider || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
