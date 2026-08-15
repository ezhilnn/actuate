import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { StatusChip } from "../motion/Kpi";

type Row = {
  id: string;
  kind?: string;
  name?: string;
  status: string;
  iterations?: number;
  passes?: number;
  best_score: number | null;
  latency_seconds: number;
  tokens: number;
  href?: string;
  prompt?: string;
};

export default function Runs() {
  const [runs, setRuns] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<{ runs: Row[] }>("/api/activity")
      .then((d) => setRuns(d.runs))
      .finally(() => setLoading(false));
  }, []);
  const shown = runs.filter((r) => {
    const n = q.trim().toLowerCase();
    if (!n) return true;
    return [r.name, r.kind, r.status, r.prompt].join(" ").toLowerCase().includes(n);
  });
  if (loading) return <div className="boot inline"><div className="boot-orb" /><p>Fetching results…</p></div>;
  return (
    <div>
      <h1>Runs</h1>
      <p className="sub">Every loop and graph, by name. Search does not reload the page.</p>
      <input placeholder="Filter runs…" value={q} onChange={(e) => setQ(e.target.value)} />
      <p className="sub search-count">{shown.length} matching</p>
      <div className="card results-fade">
        <table>
          <thead>
            <tr>
              <th>Name</th><th>Type</th><th>Status</th><th>Steps</th><th>Score</th><th>Duration</th><th>Tokens</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((run) => {
              const href = run.href || (run.kind === "graph" ? `/graph/${run.id}` : `/live/${run.id}`);
              return (
                <tr key={`${run.kind}-${run.id}`} className="row-enter">
                  <td><Link to={href}>{run.name || "Untitled"}</Link></td>
                  <td>{run.kind === "graph" ? "graph" : "loop"}</td>
                  <td><StatusChip status={run.status} /></td>
                  <td>{run.iterations ?? run.passes ?? 0}</td>
                  <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                  <td>{Number(run.latency_seconds || 0).toFixed(2)}s</td>
                  <td>{run.tokens}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!shown.length && <p className="sub">No runs yet. Use New Run → Multi-agent graph.</p>}
      </div>
    </div>
  );
}
