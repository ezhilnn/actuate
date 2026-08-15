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
  latency_seconds?: number;
  tokens?: number;
  href?: string;
  provider?: string;
  prompt?: string;
  graph_name?: string;
};

type Dash = {
  kpis: {
    running: number;
    running_loops: number;
    running_graphs: number;
    loop_count: number;
    graph_count: number;
    success_rate: number;
    average_quality: number;
    average_iterations: number;
    latency: number;
    max_latency: number;
    tokens: number;
    avg_tokens: number;
    memory: number;
    agents: number;
    templates: number;
  };
  status_counts: { status: string; count: number }[];
  provider_counts: { provider: string; count: number }[];
  templates: { id: string; name: string; nodes: number; edges: number }[];
  score_series: { iteration: number; score: number }[];
  token_series: { iteration: number; tokens: number }[];
  latency_series: { iteration: number; latency: number }[];
  pass_series: { iteration: number; passes: number }[];
  activity: Row[];
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
  const [q, setQ] = useState("");
  useEffect(() => {
    api<Dash>("/api/dashboard").then(setData).catch(() =>
      setData({
        kpis: {
          running: 0,
          running_loops: 0,
          running_graphs: 0,
          loop_count: 0,
          graph_count: 0,
          success_rate: 0,
          average_quality: 0,
          average_iterations: 0,
          latency: 0,
          max_latency: 0,
          tokens: 0,
          avg_tokens: 0,
          memory: 0,
          agents: 0,
          templates: 0,
        },
        status_counts: [],
        provider_counts: [],
        templates: [],
        score_series: [],
        token_series: [],
        latency_series: [],
        pass_series: [],
        activity: [],
      }),
    );
    api<Health>("/api/health").then(setHealth).catch(() => undefined);
  }, []);
  const k = data?.kpis;
  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    return (data?.activity || []).filter((r) => {
      if (!n) return true;
      return [r.name, r.status, r.kind, r.provider, r.prompt, r.graph_name].join(" ").toLowerCase().includes(n);
    });
  }, [data, q]);

  if (!data) {
    return (
      <div>
        <h1>Mission control</h1>
        <p className="sub">Loading data…</p>
        <div className="kpis dense">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card skeleton" />
          ))}
        </div>
      </div>
    );
  }

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
        <span className="chip">{filtered.length} of {(data.activity || []).length} runs shown</span>
      </div>
      {health?.hint && !health.llm_connected && (
        <p className="sub">{health.hint} Then use New Run → Multi-agent graph (20+ node labs) or Loop Designer.</p>
      )}
      <div className="kpis dense">
        <Kpi title="Live now" value={k?.running ?? 0} hint={`${k?.running_graphs ?? 0} graphs · ${k?.running_loops ?? 0} loops`} />
        <Kpi title="Graph runs" value={k?.graph_count ?? 0} />
        <Kpi title="Loop runs" value={k?.loop_count ?? 0} />
        <Kpi title="Loop success" value={(k?.success_rate ?? 0) * 100} suffix="%" digits={0} />
        <Kpi title="Mean quality" value={k?.average_quality ?? 0} digits={2} />
        <Kpi title="Mean iters" value={k?.average_iterations ?? 0} digits={1} />
        <Kpi title="Mean latency" value={k?.latency ?? 0} suffix="s" digits={2} hint={`max ${(k?.max_latency ?? 0).toFixed(2)}s`} />
        <Kpi title="Tokens" value={k?.tokens ?? 0} hint={`avg ${Math.round(k?.avg_tokens ?? 0)}`} />
        <Kpi title="Memory rows" value={k?.memory ?? 0} />
        <Kpi title="Agents" value={k?.agents ?? 0} />
        <Kpi title="Templates" value={k?.templates ?? 0} />
        <Kpi title="Activity rows" value={(data.activity || []).length} />
      </div>
      <div className="grid3">
        <div className="card">
          <h3>Quality (recent activity with scores)</h3>
          <ScoreChart data={data.score_series || []} />
        </div>
        <div className="card">
          <h3>Tokens per run</h3>
          <MetricChart data={data.token_series || []} dataKey="tokens" />
        </div>
        <div className="card">
          <h3>Latency (s)</h3>
          <MetricChart data={data.latency_series || []} dataKey="latency" color="#3dd68c" />
        </div>
      </div>
      <div className="grid3" style={{ marginTop: 12 }}>
        <div className="card">
          <h3>Passes / iterations</h3>
          <MetricChart data={data.pass_series || []} dataKey="passes" color="#f5c542" />
        </div>
        <div className="card">
          <h3>Status mix</h3>
          <CountBar data={data.status_counts || []} nameKey="status" valueKey="count" />
        </div>
        <div className="card">
          <h3>Provider mix</h3>
          <CountBar data={data.provider_counts || []} nameKey="provider" valueKey="count" color="#8b7cff" />
        </div>
      </div>
      <div className="grid2" style={{ marginTop: 12 }}>
        <div className="card">
          <h3>Graph labs (node count)</h3>
          <table>
            <thead><tr><th>Template</th><th>Nodes</th><th>Edges</th></tr></thead>
            <tbody>
              {(data.templates || []).map((t) => (
                <tr key={t.id}>
                  <td><Link to="/new">{t.name}</Link></td>
                  <td>{t.nodes}</td>
                  <td>{t.edges}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Search activity</h3>
          <input placeholder="Filter name, status, provider, prompt…" value={q} onChange={(e) => setQ(e.target.value)} />
          <p className="sub search-count">{filtered.length} matching</p>
          <div className="results-fade">
            <table>
              <thead>
                <tr><th>Name</th><th>Type</th><th>Status</th><th>Score</th><th>Iters</th><th>Tok</th><th>s</th></tr>
              </thead>
              <tbody>
                {filtered.slice(0, 24).map((run) => (
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
                    <td>{run.tokens ?? 0}</td>
                    <td>{(run.latency_seconds ?? 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
