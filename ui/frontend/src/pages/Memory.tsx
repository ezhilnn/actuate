import { useEffect, useState } from "react";
import { api } from "../api";
import { ScoreChart } from "../charts";

type Rec = { text: string; score: number; kind: string };

export default function Memory() {
  const [records, setRecords] = useState<Rec[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<{ records: Rec[] }>("/api/memory").then((d) => setRecords(d.records)).catch(console.error);
  }, []);
  const shown = records.filter((r) => !q || r.text.toLowerCase().includes(q.toLowerCase()));
  const chart = shown.map((r, i) => ({ iteration: i + 1, score: r.score }));
  return (
    <>
      <h1>Memory explorer</h1>
      <p className="sub">
        After a live LLM run converges, the trajectory is indexed here and recalled into the next PromptCorrector.
      </p>
      <input placeholder="Search recalled context" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Converged scores</h3>
        <ScoreChart data={chart} />
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        {!shown.length && <p className="sub">Empty until a live LLM run converges.</p>}
        {shown.map((r, i) => (
          <div key={i} className="iter">
            <header>
              <span>{r.kind}</span>
              <span className="mono">score {r.score.toFixed(3)}</span>
            </header>
            <pre>{r.text}</pre>
          </div>
        ))}
      </div>
    </>
  );
}
