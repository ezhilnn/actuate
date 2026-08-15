import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ScoreChart } from "../charts";
import { Kpi } from "../motion/Kpi";

type Rec = { text: string; score: number; kind: string; metadata?: Record<string, string> };

function mark(text: string, q: string) {
  if (!q.trim()) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

export default function Memory() {
  const [records, setRecords] = useState<Rec[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<{ records: Rec[] }>("/api/memory").then((d) => setRecords(d.records)).catch(console.error);
  }, []);
  const shown = useMemo(
    () => records.filter((r) => !q || r.text.toLowerCase().includes(q.toLowerCase()) || r.kind.toLowerCase().includes(q.toLowerCase())),
    [records, q],
  );
  const chart = shown.map((r, i) => ({ iteration: i + 1, score: r.score }));
  const kinds = Object.entries(
    shown.reduce<Record<string, number>>((acc, r) => {
      acc[r.kind] = (acc[r.kind] || 0) + 1;
      return acc;
    }, {}),
  );
  const mean = shown.length ? shown.reduce((a, r) => a + r.score, 0) / shown.length : 0;
  return (
    <>
      <h1>Memory explorer</h1>
      <p className="sub">Indexed trajectories after a live loop converges. Search filters results in place — the input stays put.</p>
      <input placeholder="Search recalled context" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="kpis dense">
        <Kpi title="Indexed" value={records.length} />
        <Kpi title="Matching" value={shown.length} />
        <Kpi title="Mean score" value={mean} digits={3} />
        <Kpi title="Kinds" value={kinds.length} />
      </div>
      <div className="grid2">
        <div className="card">
          <h3>Converged scores</h3>
          <ScoreChart data={chart} />
        </div>
        <div className="card">
          <h3>By kind</h3>
          <table>
            <thead><tr><th>Kind</th><th>Count</th></tr></thead>
            <tbody>
              {kinds.map(([k, n]) => (
                <tr key={k}><td>{k}</td><td>{n}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card results-fade" style={{ marginTop: 12 }}>
        <p className="sub search-count">{shown.length} matching</p>
        {!shown.length && <p className="sub">Empty until a live LLM run converges.</p>}
        {shown.map((r, i) => (
          <div key={i} className="iter row-enter">
            <header>
              <span>{r.kind}</span>
              <span className="mono">score {r.score.toFixed(3)}</span>
            </header>
            <pre>{mark(r.text, q)}</pre>
          </div>
        ))}
      </div>
    </>
  );
}
