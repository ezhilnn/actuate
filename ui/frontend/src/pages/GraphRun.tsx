import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactFlow, { Background, Controls, Edge, MiniMap, Node, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { api } from "../api";
import { MetricChart, ScoreChart } from "../charts";
import AgentFlowNode from "../graph/AgentFlowNode";
import AgentGuide, { Agent } from "../graph/AgentGuide";
import { StatusChip } from "../motion/Kpi";
import { useToast } from "../motion/Toasts";

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
  steps?: { pass: number; input: string; output: string; score: number | null; feedback: string | null; latency_seconds: number; tokens: number }[];
};

type GraphRun = {
  id: string;
  status: string;
  prompt: string;
  output: string;
  traces: Trace[];
  logs?: { kind: string; node_id?: string }[];
  graph: {
    name?: string;
    nodes: { id: string; agent: string; x: number; y: number; label?: string }[];
    edges: { id: string; source: string; target: string }[];
  };
  plant?: string;
  provider?: string;
  model?: string;
  name?: string;
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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [tab, setTab] = useState(0);
  const toast = useToast();
  const lastStatus = useRef<string | null>(null);

  useEffect(() => {
    api<{ agents: Agent[] }>("/api/agents").then((d) => setAgents(d.agents)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!runId) return;
    let timer: number;
    const tick = async () => {
      const data = await api<GraphRun>(`/api/graph-runs/${runId}`);
      setRun(data);
      if (lastStatus.current && lastStatus.current === "running" && data.status !== "running") {
        const n = (data.traces || []).length;
        toast(
          data.status === "converged" || data.status === "completed" ? "✓ Execution completed" : `Run ${data.status}`,
          `${data.passes ?? n} passes · ${(data.latency_seconds ?? 0).toFixed(2)}s`,
        );
      }
      lastStatus.current = data.status;
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
    const started = new Set((run?.logs || []).filter((l) => l.kind === "NodeStarted").map((l) => (l as { node_id?: string }).node_id));
    return (run?.graph?.nodes || []).map((n) => {
      const t = traces[n.id];
      const lastScore = t?.scores[t.scores.length - 1];
      let status = "idle";
      if (run?.status === "running") {
        if (t?.outputs.length) status = "completed";
        else if (started.has(n.id) || t?.inputs.length) status = "running";
        else status = "queued";
      } else if (t?.outputs.length) {
        status = lastScore != null && lastScore < 0.8 ? "failed" : "completed";
      }
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

  const edges: Edge[] = useMemo(() => {
    const hot = new Set(
      (run?.graph?.nodes || [])
        .filter((n) => {
          const t = traces[n.id];
          return run?.status === "running" && t && t.inputs.length && !t.outputs.length;
        })
        .map((n) => n.id),
    );
    if (pick) {
      hot.add(pick);
    }
    return (run?.graph?.edges || []).map((e) => {
      const live = hot.has(e.source) || hot.has(e.target);
      const selectedPath = Boolean(pick && (e.source === pick || e.target === pick));
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        animated: live,
        className: selectedPath ? "edge-live" : live ? "edge-flow" : "",
        style: selectedPath ? { stroke: "#3d8bfd", strokeWidth: 2 } : undefined,
      };
    });
  }, [run, traces, pick]);

  const picked = pick ? traces[pick] : undefined;
  const graphNode = run?.graph?.nodes.find((n) => n.id === pick);
  const pickedAgent = agents.find((a) => a.id === (picked?.agent || graphNode?.agent));
  const scoreChart = (run?.traces || [])
    .filter((t) => t.scores.length)
    .map((t, i) => ({ iteration: i + 1, score: t.scores[t.scores.length - 1] }));
  const tokenChart = (run?.traces || []).map((t, i) => ({ iteration: i + 1, tokens: t.tokens }));

  return (
    <>
      <h1>{run?.name || run?.graph?.name || "Graph run"}</h1>
      <div className="chips">
        <span className={`chip ${run?.plant === "stub" ? "bad" : "ok"}`}>
          {run?.plant === "stub" ? "MOCK" : `LIVE LLM · ${run?.provider || ""}`}
        </span>
        <span className="chip"><StatusChip status={run?.status} /></span>
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
            minZoom={0.15}
            maxZoom={1.75}
            zoomOnScroll
            panOnDrag
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
          <p className="sub">Click a node to see its role, system prompt, and every input/output with metrics.</p>
          <AgentGuide agent={pickedAgent || (picked ? { id: picked.agent, kind: "agent", title: picked.agent, color: "#3d8bfd", blurb: "" } : null)} />
          {!picked && <p className="sub">No run data on this node yet.</p>}
          {picked && (
            <>
              <div className="chips">
                <span className="chip">{picked.agent}</span>
                <span className="chip">{picked.tokens} tok</span>
                <span className="chip">{picked.latency_seconds.toFixed(2)}s</span>
                <span className="chip">{picked.passes} passes</span>
                {picked.scores.length > 0 && (
                  <span className="chip">score {picked.scores[picked.scores.length - 1].toFixed(3)}</span>
                )}
              </div>
              <div className="tabs">
                {(picked.steps?.length ? picked.steps : picked.outputs).map((_, i) => (
                  <button key={i} className={tab === i ? "on" : ""} onClick={() => setTab(i)}>
                    pass {i + 1}
                  </button>
                ))}
              </div>
              {(() => {
                const step = picked.steps?.[tab];
                const input = step?.input || picked.inputs[tab] || picked.inputs[picked.inputs.length - 1];
                const output = step?.output || picked.outputs[tab];
                return (
                  <>
                    {step && (
                      <div className="chips">
                        <span className="chip">{step.tokens} tok this pass</span>
                        <span className="chip">{step.latency_seconds.toFixed(2)}s this pass</span>
                        {step.score != null && <span className="chip">score {step.score.toFixed(3)}</span>}
                      </div>
                    )}
                    <p className="sub">Input</p>
                    <pre>{input}</pre>
                    <p className="sub">Output</p>
                    <pre>{output}</pre>
                    {(step?.feedback || picked.feedback[tab]) && (
                      <>
                        <p className="sub">Judge feedback</p>
                        <pre>{step?.feedback || picked.feedback[tab]}</pre>
                      </>
                    )}
                  </>
                );
              })()}
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
