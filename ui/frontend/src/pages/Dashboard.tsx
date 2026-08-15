import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";
import { ScoreChart } from "../charts";

type Dash = {
  kpis: {
    running: number;
    success_rate: number;
    average_quality: number;
    average_iterations: number;
    latency: number;
    tokens: number;
    cost: number;
  };
  recent_runs: RunSummary[];
};

type Health = {
  llm_connected: boolean;
  configured_providers: string[];
  plant: string;
  hint?: string | null;
  persistence?: string;
};

export default function Dashboard() {
  const [data, setData] = useState<Dash | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    api<Dash>("/api/dashboard").then(setData).catch(console.error);
    api<Health>("/api/health").then(setHealth).catch(console.error);
  }, []);
  const k = data?.kpis;
  const chart = (data?.recent_runs || [])
    .filter((r) => r.best_score != null)
    .slice()
    .reverse()
    .map((r, i) => ({ iteration: i + 1, score: r.best_score as number }));
  return (
    <>
      <h1>Mission control</h1>
      <div className="chips">
        <span className={`chip ${health?.llm_connected ? "ok" : "bad"}`}>
          {health?.llm_connected ? "LLM connected" : "No LLM key — open Settings"}
        </span>
        {(health?.configured_providers || []).map((p) => (
          <span className="chip" key={p}>{p}</span>
        ))}
        <span className="chip">{health?.persistence || "memory"} store</span>
      </div>
      {health?.hint && !health.llm_connected && (
        <p className="sub">{health.hint} Then use New Run or Loop Designer.</p>
      )}
      <div className="kpis">
        <Kpi title="Running loops" value={k?.running ?? 0} />
        <Kpi title="Success rate" value={`${Math.round((k?.success_rate ?? 0) * 100)}%`} />
        <Kpi title="Average quality" value={(k?.average_quality ?? 0).toFixed(2)} />
        <Kpi title="Average iterations" value={(k?.average_iterations ?? 0).toFixed(1)} />
        <Kpi title="Latency" value={`${(k?.latency ?? 0).toFixed(2)}s`} />
        <Kpi title="Token usage" value={k?.tokens ?? 0} />
      </div>
      <div className="grid2">
        <div className="card">
          <h3>Quality over recent runs</h3>
          <p className="sub"><Link to="/designer">Loop / graph designer</Link> — 40+ agents, 16 templates, drag-and-drop, click a node to inspect I/O.</p>
          <ScoreChart data={chart} />
        </div>
        <div className="card">
          <h3>Recent runs</h3>
          <table>
            <thead>
              <tr><th>Run</th><th>Status</th><th>Score</th><th>Iters</th></tr>
            </thead>
            <tbody>
              {(data?.recent_runs || []).map((run) => (
                <tr key={run.id}>
                  <td className="mono"><Link to={`/live/${run.id}`}>{run.id.slice(0, 10)}</Link></td>
                  <td><span className={`status ${run.status}`}>{run.status}</span></td>
                  <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                  <td>{run.iterations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Kpi({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="value">{value}</div>
    </div>
  );
}
