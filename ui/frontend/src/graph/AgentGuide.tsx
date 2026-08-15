type Agent = {
  id: string;
  kind: string;
  title: string;
  color: string;
  blurb: string;
  system?: string;
  how_to?: string;
  receives?: string;
  produces?: string;
};

export default function AgentGuide({ agent }: { agent: Agent | null | undefined }) {
  if (!agent) {
    return (
      <div className="guide empty">
        <h3>Agent guide</h3>
        <p className="sub">Click any agent in the list or on the canvas to see what it does, the prompt it uses, and how to wire it.</p>
      </div>
    );
  }
  return (
    <div className="guide">
      <div className="guide-head">
        <i style={{ background: agent.color }} />
        <div>
          <h3>{agent.title}</h3>
          <span className="chip">{agent.kind}</span>
        </div>
      </div>
      <p className="sub">{agent.blurb}</p>
      <label>What it can do</label>
      <p className="guide-p">{agent.blurb}</p>
      <label>How to use it</label>
      <p className="guide-p">{agent.how_to}</p>
      <label>What it receives</label>
      <p className="guide-p">{agent.receives}</p>
      <label>What it produces</label>
      <p className="guide-p">{agent.produces}</p>
      <label>System prompt (sent to the LLM)</label>
      <pre className="prompt-box">{agent.system || "(passthrough — no extra system prompt)"}</pre>
    </div>
  );
}

export type { Agent };
