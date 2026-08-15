import { Handle, Position, NodeProps } from "reactflow";

const LABEL: Record<string, string> = {
  waiting: "not run",
  queued: "waiting",
  running: "running",
  completed: "ran",
  skipped: "frozen",
  failed: "failed",
  idle: "not run",
};

export default function AgentFlowNode({ data, selected }: NodeProps) {
  const status = String(data.status || "ready");
  const showPill = Boolean(LABEL[status]);
  return (
    <div
      className={`agent-node ${data.kind} ${selected ? "sel" : ""} ${status}`}
      style={{ ["--node-accent" as string]: data.color || "#3d8bfd" }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="agent-node-top">
        <span className="k">{data.kind}</span>
        {showPill && <span className={`run-pill ${status}`}>{LABEL[status]}</span>}
      </div>
      <strong>{data.title}</strong>
      {data.score != null && <em>score {Number(data.score).toFixed(3)}</em>}
      {status === "completed" && data.tokens != null && <em>{data.tokens} tok</em>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
