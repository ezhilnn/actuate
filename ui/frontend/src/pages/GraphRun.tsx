import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactFlow, { Background, Controls, Edge, MiniMap, Node, ReactFlowProvider } from "reactflow";
import "reactflow/dist/style.css";
import { api, getToken } from "../api";
import { MetricChart, ScoreChart } from "../charts";
import AgentFlowNode from "../graph/AgentFlowNode";
import AgentGuide, { Agent } from "../graph/AgentGuide";
import { StatusChip } from "../motion/Kpi";
import { useToast } from "../motion/Toasts";

const nodeTypes = { agent: AgentFlowNode };

type Trace = {
  node_id: string;
  agent: string;
  title?: string;
  frozen?: boolean;
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
  parent_run_id?: string;
  rerun_from?: string;
  max_tokens?: number;
  provider?: string;
  model?: string;
  name?: string;
  tokens?: number;
  latency_seconds?: number;
  passes?: number;
};

function wsUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getToken();
  const q = token ? `?token=${encodeURIComponent(token)}` : "";
  if (import.meta.env.DEV) return `${proto}://127.0.0.1:8000/ws/runs/${runId}${q}`;
  return `${proto}://${location.host}/ws/runs/${runId}${q}`;
}

function formatLog(msg: Record<string, unknown>): string {
  const kind = String(msg.kind || "");
  const title = String(msg.title || msg.agent || msg.node_id || "");
  if (kind === "NodeStarted") {
    return `▶ ${title} started\n  input: ${String(msg.input || "").slice(0, 500)}`;
  }
  if (kind === "NodeCompleted") {
    const kids = Array.isArray(msg.delivered_in_parallel_to) ? msg.delivered_in_parallel_to.join(", ") : "";
    return `✓ ${title} completed · ${msg.tokens || 0} tok · ${msg.latency_seconds || 0}s${kids ? `\n  fan-out → ${kids}` : ""}\n  input: ${String(msg.input || "").slice(0, 400)}\n  output: ${String(msg.output || "").slice(0, 400)}`;
  }
  if (kind === "NodeSkipped") return `⏭ ${title} frozen (${msg.reason})`;
  if (kind === "BudgetExceeded") return `✗ token budget ${msg.tokens} > ${msg.cap}`;
  return `${kind} ${title} ${msg.status || ""}`.trim();
}

function GraphRunInner() {
  const { runId } = useParams();
  const nav = useNavigate();
  const [run, setRun] = useState<GraphRun | null>(null);
  const [pick, setPick] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [tab, setTab] = useState(0);
  const [draft, setDraft] = useState("");
  const [maxTok, setMaxTok] = useState(250000);
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
      if (data.max_tokens) setMaxTok(data.max_tokens);
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
      setLogs((prev) => [formatLog(msg), ...prev].slice(0, 80));
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
    const started = new Set(
      (run?.logs || []).filter((l) => l.kind === "NodeStarted").map((l) => (l as { node_id?: string }).node_id),
    );
    const skipped = new Set(
      (run?.logs || []).filter((l) => l.kind === "NodeSkipped").map((l) => (l as { node_id?: string }).node_id),
    );
    return (run?.graph?.nodes || []).map((n) => {
      const t = traces[n.id];
      const lastScore = t?.scores[t.scores.length - 1];
      const ran = Boolean(t?.outputs?.length);
      let status = "waiting";
      if (skipped.has(n.id) || t?.frozen) status = "skipped";
      else if (run?.status === "running") {
        if (ran) status = "completed";
        else if (started.has(n.id) || (t?.inputs?.length && !ran)) status = "running";
        else status = "queued";
      } else if (ran) {
        status = lastScore != null && lastScore < 0.8 ? "failed" : "completed";
      } else {
        status = "waiting";
      }
      return {
        id: n.id,
        type: "agent",
        position: { x: n.x, y: n.y },
        data: {
          agent: n.agent,
          title: n.label || n.agent,
          kind: n.agent.startsWith("judge") ? "judge" : n.agent === "ingress" || n.agent === "egress" ? "io" : "agent",
          color: status === "failed" ? "#ff6b7a" : status === "completed" ? "#3dd68c" : "#3d8bfd",
          score: lastScore,
          tokens: t?.tokens,
          passes: t?.passes,
          status,
        },
      };
    });
  }, [run, traces]);

  const doneIds = useMemo(
    () => new Set(nodes.filter((n) => n.data.status === "completed" || n.data.status === "skipped").map((n) => n.id)),
    [nodes],
  );
  const waitingCount = nodes.filter((n) => n.data.status === "waiting" || n.data.status === "queued").length;
  const ranCount = nodes.filter((n) => n.data.status === "completed" || n.data.status === "skipped").length;
  const runningCount = nodes.filter((n) => n.data.status === "running").length;

  const edges: Edge[] = useMemo(() => {
    return (run?.graph?.edges || []).map((e) => {
      const srcDone = doneIds.has(e.source);
      const tgtRun = nodes.find((n) => n.id === e.target)?.data.status;
      const live = tgtRun === "running" || (run?.status === "running" && srcDone && tgtRun === "queued");
      const selectedPath = Boolean(pick && (e.source === pick || e.target === pick));
      let className = "edge-wait";
      if (selectedPath) className = "edge-live";
      else if (live) className = "edge-flow";
      else if (srcDone) className = "edge-done";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        animated: live,
        className,
        style: selectedPath
          ? { stroke: "#3d8bfd", strokeWidth: 2 }
          : srcDone && !live
            ? { stroke: "#2e6b50", strokeWidth: 1.4 }
            : { stroke: "#2a3140", strokeWidth: 1, opacity: 0.55 },
      };
    });
  }, [run, nodes, doneIds, pick]);

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
        <span className="chip">{run?.tokens ?? 0} / {run?.max_tokens ?? maxTok} tok</span>
        <span className="chip">{ranCount} ran</span>
        <span className="chip">{runningCount ? `${runningCount} running` : `${waitingCount} not run`}</span>
        <Link className="chip" to="/designer">Edit graph</Link>
        <button
          type="button"
          className="chip btn-press"
          onClick={async () => {
            if (!runId) return;
            const pack = await api<unknown>(`/api/graph-runs/${runId}/pack`);
            const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `${run?.name || "run"}-pack.json`;
            a.click();
          }}
        >
          Export pack
        </button>
      </div>
      <div className="designer-shell run">
        <div className="rf canvas graph-run-canvas">
          <div className="graph-legend" aria-hidden>
            <span><i className="lg waiting" /> not run</span>
            <span><i className="lg queued" /> waiting</span>
            <span><i className="lg running" /> running</span>
            <span><i className="lg completed" /> ran</span>
            <span><i className="lg skipped" /> frozen</span>
            <span><i className="lg failed" /> failed</span>
          </div>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => {
              setPick(n.id);
              const t = traces[n.id];
              setDraft(t?.inputs[t.inputs.length - 1] || "");
            }}
            fitView
            minZoom={0.15}
            maxZoom={1.75}
            zoomOnScroll
            panOnDrag
            nodesDraggable={false}
          >
            <Background />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const s = String(n.data?.status || "");
                if (s === "completed") return "#3dd68c";
                if (s === "failed") return "#ff6b7a";
                if (s === "running") return "#3d8bfd";
                if (s === "skipped") return "#8b9cb3";
                if (s === "queued") return "#c9b36a";
                return "#2a3140";
              }}
            />
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
                    <p className="sub">Input (edit to rerun this node + descendants as a new revision)</p>
                    <textarea value={draft} onChange={(e) => setDraft(e.target.value)} style={{ minHeight: 100 }} />
                    <label>Token budget</label>
                    <input type="number" min={1000} value={maxTok} onChange={(e) => setMaxTok(Number(e.target.value))} />
                    <button
                      type="button"
                      className="primary btn-press"
                      disabled={run?.status === "running"}
                      onClick={async () => {
                        if (!run || !pick) return;
                        const created = await api<{ run_id: string }>("/api/graphs/run", {
                          method: "POST",
                          body: JSON.stringify({
                            prompt: run.prompt,
                            name: `${run.name || "Graph"} · rerun ${pickedAgent?.title || pick}`,
                            graph: run.graph,
                            provider: run.provider || "nvidia",
                            model: run.model,
                            parent_run_id: run.id,
                            rerun_from: pick,
                            node_overrides: { [pick]: draft },
                            max_tokens: maxTok,
                          }),
                        });
                        toast("Revision started", "Frozen ancestors · this node and downstream re-run in parallel");
                        nav(`/graph/${created.run_id}`);
                      }}
                    >
                      Rerun from this node
                    </button>
                    <p className="sub">Input snapshot</p>
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
