import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

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
  useEffect(() => {
    api<{ runs: Row[] }>("/api/activity")
      .then((d) => setRuns(d.runs))
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <div className="boot inline"><div className="boot-orb" /><p>Loading runs…</p></div>;
  return (
    <div className="fade-in">
      <h1>Runs</h1>
      <p className="sub">Every loop and graph, by name. Open one to inspect every node’s input and output.</p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th><th>Type</th><th>Status</th><th>Steps</th><th>Score</th><th>Duration</th><th>Tokens</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const href = run.href || (run.kind === "graph" ? `/graph/${run.id}` : `/live/${run.id}`);
              return (
                <tr key={`${run.kind}-${run.id}`}>
                  <td><Link to={href}>{run.name || "Untitled"}</Link></td>
                  <td>{run.kind === "graph" ? "graph" : "loop"}</td>
                  <td><span className={`status ${run.status}`}>{run.status}</span></td>
                  <td>{run.iterations ?? run.passes ?? 0}</td>
                  <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                  <td>{Number(run.latency_seconds || 0).toFixed(2)}s</td>
                  <td>{run.tokens}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!runs.length && <p className="sub">No runs yet. Use New Run → Multi-agent graph.</p>}
      </div>
    </div>
  );
}
