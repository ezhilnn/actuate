import { useEffect, useState } from "react";
import { api, Provider } from "../api";
import AgentGuide, { Agent } from "../graph/AgentGuide";

export default function Models() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [pick, setPick] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([
      api<{ providers: Provider[] }>("/api/models"),
      api<{ agents: Agent[] }>("/api/agents"),
    ]).then(([m, a]) => {
      setProviders(m.providers);
      setAgents(a.agents);
    }).finally(() => setLoading(false));
  }, []);
  const agent = agents.find((a) => a.id === pick);
  return (
    <>
      <h1>Models and agents</h1>
      <p className="sub">LLM plants plus every specialist. Click an agent to see its prompt and how to use it.</p>
      {loading && <div className="boot inline"><div className="boot-orb" /><p>Loading catalog…</p></div>}
      <h3 className="section-title">LLM plants</h3>
      <div className="provider-grid">
        {providers.map((p) => (
          <div className="card" key={p.id}>
            <h3>{p.name}</h3>
            <div className={p.configured ? "badge" : "badge off"}>{p.configured ? "configured" : "needs key"}</div>
            <p className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>
              {p.models.join(" · ")}
            </p>
          </div>
        ))}
      </div>
      <h3 className="section-title">Specialist agents</h3>
      <div className="split-guide">
        <div className="provider-grid">
          {agents.map((a) => (
            <button
              type="button"
              className={`card clickable ${pick === a.id ? "sel" : ""}`}
              key={a.id}
              onClick={() => setPick(a.id)}
            >
              <h3>{a.title}</h3>
              <div className="badge">{a.kind}</div>
              <p className="sub" style={{ margin: "8px 0 0" }}>{a.blurb}</p>
            </button>
          ))}
        </div>
        <div className="card">
          <AgentGuide agent={agent} />
        </div>
      </div>
    </>
  );
}
