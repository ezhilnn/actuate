import { Handle, Position, NodeProps } from "reactflow";

export default function AgentFlowNode({ data, selected }: NodeProps) {
  return (
    <div
      className={`agent-node ${data.kind} ${selected ? "sel" : ""} ${data.status || ""}`}
      style={{ borderColor: data.color }}
    >
      <Handle type="target" position={Position.Left} />
      <span className="k">{data.kind}</span>
      <strong>{data.title}</strong>
      {data.score != null && <em>score {Number(data.score).toFixed(3)}</em>}
      {data.passes != null && <em>{data.passes} pass(es)</em>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
