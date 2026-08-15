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
  const status = data.status ? String(data.status) : "";
  const showRun = Boolean(status && LABEL[status]);
  return (
    <div
      className={`agent-node ${data.kind} ${selected ? "sel" : ""} ${showRun ? status : "ready"}`}
      style={{ ["--node-accent" as string]: data.color || "#3d8bfd" }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="agent-node-top">
        <span className="k">{data.kind}</span>
        {showRun && <span className={`run-pill ${status}`}>{LABEL[status]}</span>}
      </div>
      <strong>{data.title}</strong>
      {showRun && data.score != null && <em>score {Number(data.score).toFixed(3)}</em>}
      {showRun && status === "completed" && data.tokens != null && <em>{data.tokens} tok</em>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
