import { useEffect, useState } from "react";
import { api } from "../api";
import { MetricChart, ScoreChart } from "../charts";
import { RunSummary } from "../api";

export default function Benchmarks() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  useEffect(() => {
    api<{ runs: RunSummary[] }>("/api/runs").then((d) => setRuns(d.runs));
  }, []);
  const chart = runs
    .filter((r) => r.best_score != null)
    .slice()
    .reverse()
    .map((r, i) => ({ iteration: i + 1, score: r.best_score as number }));
  return (
    <>
      <h1>Benchmarks</h1>
      <p className="sub">Quality, iterations, latency, and tokens across LLM control runs.</p>
      <div className="grid2">
        <div className="card">
          <h3>Score series</h3>
          <ScoreChart data={chart} />
        </div>
        <div className="card">
          <h3>Tokens</h3>
          <MetricChart
            data={runs.slice().reverse().map((r, i) => ({ iteration: i + 1, tokens: r.tokens }))}
            dataKey="tokens"
          />
        </div>
      </div>
      <div className="kpis">
        <div className="card"><h3>Runs</h3><div className="value">{runs.length}</div></div>
        <div className="card"><h3>Tokens</h3><div className="value">{runs.reduce((a, r) => a + r.tokens, 0)}</div></div>
        <div className="card"><h3>Mean latency</h3><div className="value">{runs.length ? (runs.reduce((a, r) => a + r.latency_seconds, 0) / runs.length).toFixed(2) : 0}s</div></div>
      </div>
    </>
  );
}
