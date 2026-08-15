import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactFlow, { Background, Controls, Edge, MiniMap, Node, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { api } from "../api";
import { MetricChart, ScoreChart } from "../charts";
import AgentFlowNode from "../graph/AgentFlowNode";

const nodeTypes = { agent: AgentFlowNode };

type Trace = {
  node_id: string;
  agent: string;
  inputs: string[];
  outputs: string[];
  scores: number[];
  feedback: string[];
  latency_seconds: number;
  tokens: number;
  passes: number;
};

type GraphRun = {
  id: string;
  status: string;
  prompt: string;
  output: string;
  traces: Trace[];
  logs: { kind: string }[];
  graph: {
    name?: string;
    nodes: { id: string; agent: string; x: number; y: number; label?: string }[];
    edges: { id: string; source: string; target: string }[];
  };
  plant?: string;
  provider?: string;
  model?: string;
  tokens?: number;
  latency_seconds?: number;
  passes?: number;
};

function wsUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  if (import.meta.env.DEV) return `${proto}://127.0.0.1:8000/ws/runs/${runId}`;
  return `${proto}://${location.host}/ws/runs/${runId}`;
}

function GraphRunInner() {
  const { runId } = useParams();
  const [run, setRun] = useState<GraphRun | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [tab, setTab] = useState(0);

  useEffect(() => {
    if (!runId) return;
    let timer: number;
    const tick = async () => {
      const data = await api<GraphRun>(`/api/graph-runs/${runId}`);
      setRun(data);
      if (data.status === "running") timer = window.setTimeout(tick, 700);
    };
    tick();
    const ws = new WebSocket(wsUrl(runId));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      setLogs((prev) => [`${msg.kind} ${msg.node_id || msg.status || ""}`.trim(), ...prev].slice(0, 200));
    };
    return () => {
      window.clearTimeout(timer);
      ws.close();
    };
  }, [runId]);

  const traces = useMemo(() => {
    const map: Record<string, Trace> = {};
    for (const t of run?.traces || []) map[t.node_id] = t;
    return map;
  }, [run]);

  const nodes: Node[] = useMemo(() => {
    return (run?.graph?.nodes || []).map((n) => {
      const t = traces[n.id];
      const lastScore = t?.scores[t.scores.length - 1];
      const status = t?.outputs.length ? (run?.status === "running" ? "hot" : "done") : "";
      return {
        id: n.id,
        type: "agent",
        position: { x: n.x, y: n.y },
        data: {
          agent: n.agent,
          title: n.label || n.agent,
          kind: n.agent.startsWith("judge") ? "judge" : n.agent === "ingress" || n.agent === "egress" ? "io" : "agent",
          color: lastScore != null && lastScore < 0.8 ? "#ff6b7a" : "#3d8bfd",
          score: lastScore,
          passes: t?.passes,
          status,
        },
      };
    });
  }, [run, traces]);

  const edges: Edge[] = useMemo(
    () => (run?.graph?.edges || []).map((e) => ({ id: e.id, source: e.source, target: e.target, animated: run?.status === "running" })),
    [run],
  );

  const picked = pick ? traces[pick] : undefined;
  const scoreChart = (run?.traces || [])
    .filter((t) => t.scores.length)
    .map((t, i) => ({ iteration: i + 1, score: t.scores[t.scores.length - 1] }));
  const tokenChart = (run?.traces || []).map((t, i) => ({ iteration: i + 1, tokens: t.tokens }));

  return (
    <>
      <h1>{run?.graph?.name || "Graph run"}</h1>
      <div className="chips">
        <span className={`chip ${run?.plant === "stub" ? "bad" : "ok"}`}>
          {run?.plant === "stub" ? "MOCK" : `LIVE LLM · ${run?.provider || ""}`}
        </span>
        <span className="chip">{run?.status}</span>
        <span className="chip">{run?.passes ?? 0} passes</span>
        <span className="chip">{(run?.latency_seconds ?? 0).toFixed(2)}s</span>
        <span className="chip">{run?.tokens ?? 0} tok</span>
        <Link className="chip" to="/designer">Edit graph</Link>
      </div>
      <div className="designer-shell run">
        <div className="rf canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => setPick(n.id)}
            fitView
            nodesDraggable={false}
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <aside className="inspector">
          <h3>Final output</h3>
          <pre className="out">{run?.output || (run?.status === "running" ? "Agents are still working…" : "—")}</pre>
          <h3>Scores / tokens</h3>
          <ScoreChart data={scoreChart} />
          <MetricChart data={tokenChart} dataKey="tokens" />
          <h3>Node inspector</h3>
          <p className="sub">Click a node after (or during) the run to see every input and output pass.</p>
          {!picked && <p className="sub">No node selected.</p>}
          {picked && (
            <>
              <div className="chips">
                <span className="chip">{picked.agent}</span>
                <span className="chip">{picked.tokens} tok</span>
                <span className="chip">{picked.latency_seconds.toFixed(2)}s</span>
              </div>
              <div className="tabs">
                {picked.outputs.map((_, i) => (
                  <button key={i} className={tab === i ? "on" : ""} onClick={() => setTab(i)}>
                    pass {i + 1}
                  </button>
                ))}
              </div>
              <p className="sub">Input {tab + 1} of {picked.inputs.length}</p>
              <pre>{picked.inputs[tab] || picked.inputs[picked.inputs.length - 1]}</pre>
              <p className="sub">Output {tab + 1} of {picked.outputs.length}</p>
              <pre>{picked.outputs[tab]}</pre>
              {picked.feedback[tab] && (
                <>
                  <p className="sub">Judge feedback</p>
                  <pre>{picked.feedback[tab]}</pre>
                </>
              )}
            </>
          )}
          <h3>Log</h3>
          <div className="log mono">{logs.join("\n") || "waiting for events"}</div>
        </aside>
      </div>
    </>
  );
}

export default function GraphRun() {
  return (
    <ReactFlowProvider>
      <GraphRunInner />
    </ReactFlowProvider>
  );
}
