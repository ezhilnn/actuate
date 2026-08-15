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

type LogEvent = {
  kind: string;
  node_id?: string;
  input?: string;
  output?: string;
  tokens?: number;
  error?: string;
  stop_reason?: string;
  status?: string;
};

type GraphRun = {
  id: string;
  status: string;
  prompt: string;
  output: string;
  traces: Trace[];
  logs?: LogEvent[];
  graph: {
    name?: string;
    nodes: { id: string; agent: string; x: number; y: number; label?: string }[];
    edges: { id: string; source: string; target: string }[];
    target_score?: number;
    max_passes?: number;
  };
  plant?: string;
  parent_run_id?: string;
  rerun_from?: string;
  max_tokens?: number;
  max_passes?: number;
  target_score?: number;
  stop_reason?: string;
  provider?: string;
  model?: string;
  name?: string;
  tokens?: number;
  latency_seconds?: number;
  passes?: number;
};

const LIVE_KEY = (id: string) => `actuate.graph-live.${id}`;

type LiveNode = {
  status: string;
  inputs?: string[];
  outputs?: string[];
  scores?: number[];
  tokens?: number;
  passes?: number;
};

function readLive(runId: string): Record<string, LiveNode> {
  try {
    return JSON.parse(localStorage.getItem(LIVE_KEY(runId)) || "{}") as Record<string, LiveNode>;
  } catch {
    return {};
  }
}

function writeLive(runId: string, nodes: Record<string, LiveNode>) {
  try {
    localStorage.setItem(LIVE_KEY(runId), JSON.stringify(nodes));
  } catch {
    /* quota */
  }
}

function clearLive(runId: string) {
  localStorage.removeItem(LIVE_KEY(runId));
}

function clip(text: string, n = 8000) {
  return text.length > n ? text.slice(0, n) : text;
}

function applyLogToLive(prev: Record<string, LiveNode>, msg: LogEvent): Record<string, LiveNode> {
  const nid = msg.node_id;
  if (!nid) return prev;
  const cur = { ...(prev[nid] || { status: "waiting" }) };
  if (msg.kind === "NodeStarted") {
    cur.status = "running";
    if (msg.input) cur.inputs = [clip(msg.input)];
  } else if (msg.kind === "NodeCompleted") {
    cur.status = "completed";
    if (msg.input) cur.inputs = [clip(msg.input)];
    if (msg.output) cur.outputs = [clip(msg.output)];
    if (msg.tokens != null) cur.tokens = Number(msg.tokens);
  } else if (msg.kind === "NodeSkipped") {
    cur.status = "skipped";
  } else if (msg.kind === "NodeFailed") {
    cur.status = "failed";
  } else {
    return prev;
  }
  return { ...prev, [nid]: cur };
}

function nodeStatus(
  nodeId: string,
  agent: string,
  runStatus: string,
  logs: LogEvent[],
  trace: Trace | undefined,
  live: LiveNode | undefined,
  target: number,
): string {
  const kinds = logs.filter((l) => l.node_id === nodeId).map((l) => l.kind);
  const skipped = kinds.includes("NodeSkipped") || Boolean(trace?.frozen);
  const completed = kinds.includes("NodeCompleted") || Boolean(trace?.outputs?.length) || live?.status === "completed";
  const failedEvt = kinds.includes("NodeFailed") || live?.status === "failed";
  const started =
    kinds.includes("NodeStarted") || Boolean(trace?.inputs?.length) || live?.status === "running";
  if (skipped) return "skipped";
  if (completed) {
    const lastScore = trace?.scores[trace.scores.length - 1];
    if (agent.startsWith("judge") && lastScore != null && lastScore < target) return "failed";
    return "completed";
  }
  if (failedEvt) return "failed";
  if (started) return runStatus === "running" ? "running" : "failed";
  if (runStatus === "running") return "queued";
  return "waiting";
}

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
  if (kind === "NodeFailed") return `✗ ${title} failed\n  ${String(msg.error || "")}`;
  if (kind === "GraphFinished") return `■ graph ${msg.status} · ${msg.stop_reason || ""}`.trim();
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
  const [live, setLive] = useState<Record<string, LiveNode>>({});
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
    setLive(readLive(runId));
    let timer: number;
    const tick = async () => {
      const data = await api<GraphRun>(`/api/graph-runs/${runId}`);
      setRun(data);
      setLogs((data.logs || []).slice().reverse().map((ev) => formatLog(ev as Record<string, unknown>)).slice(0, 80));
      if (data.max_tokens) setMaxTok(data.max_tokens);
      if (data.status === "running") {
        let merged = readLive(runId);
        for (const ev of data.logs || []) merged = applyLogToLive(merged, ev);
        writeLive(runId, merged);
        setLive(merged);
      } else {
        clearLive(runId);
        const historic: Record<string, LiveNode> = {};
        for (const ev of data.logs || []) Object.assign(historic, applyLogToLive(historic, ev));
        setLive(historic);
      }
      if (lastStatus.current && lastStatus.current === "running" && data.status !== "running") {
        const n = (data.traces || []).length;
        toast(
          data.status === "converged" || data.status === "completed" ? "✓ Execution completed" : `Run ${data.status}`,
          data.stop_reason || `${data.passes ?? n} passes · ${(data.latency_seconds ?? 0).toFixed(2)}s`,
        );
      }
      lastStatus.current = data.status;
      if (data.status === "running") timer = window.setTimeout(tick, 700);
    };
    tick();
    const ws = new WebSocket(wsUrl(runId));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as LogEvent;
      setLogs((prev) => [formatLog(msg as Record<string, unknown>), ...prev].slice(0, 80));
      setRun((prev) => (prev ? { ...prev, logs: [...(prev.logs || []), msg] } : prev));
      if (msg.node_id) {
        setLive((prev) => {
          const next = applyLogToLive(prev, msg);
          writeLive(runId, next);
          return next;
        });
      }
    };
    return () => {
      window.clearTimeout(timer);
      ws.close();
    };
  }, [runId]);

  const traces = useMemo(() => {
    const map: Record<string, Trace> = {};
    for (const t of run?.traces || []) map[t.node_id] = t;
    for (const ev of run?.logs || []) {
      const nid = ev.node_id;
      if (!nid) continue;
      const cur = map[nid] || {
        node_id: nid,
        agent: "",
        inputs: [] as string[],
        outputs: [] as string[],
        scores: [] as number[],
        feedback: [] as string[],
        latency_seconds: 0,
        tokens: 0,
        passes: 0,
      };
      if (ev.input && !cur.inputs.length) cur.inputs = [ev.input];
      if (ev.output && !cur.outputs.length) cur.outputs = [ev.output];
      if (ev.tokens != null) cur.tokens = Math.max(cur.tokens || 0, Number(ev.tokens));
      map[nid] = cur;
    }
    for (const [id, snap] of Object.entries(live)) {
      const cur = map[id];
      if (!cur) {
        map[id] = {
          node_id: id,
          agent: "",
          inputs: snap.inputs || [],
          outputs: snap.outputs || [],
          scores: snap.scores || [],
          feedback: [],
          latency_seconds: 0,
          tokens: snap.tokens || 0,
          passes: snap.passes || 0,
        };
      } else if (!cur.outputs?.length && snap.outputs?.length) {
        map[id] = { ...cur, outputs: snap.outputs, inputs: snap.inputs || cur.inputs, tokens: snap.tokens ?? cur.tokens };
      }
    }
    return map;
  }, [run, live]);

  const target = run?.target_score ?? run?.graph?.target_score ?? 0.85;

  const nodes: Node[] = useMemo(() => {
    const logRows = run?.logs || [];
    return (run?.graph?.nodes || []).map((n) => {
      const t = traces[n.id];
      const lastScore = t?.scores[t.scores.length - 1];
      const status = nodeStatus(n.id, n.agent, run?.status || "", logRows, t, live[n.id], target);
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
  }, [run, traces, live, target]);

  const waitingCount = nodes.filter((n) => n.data.status === "waiting" || n.data.status === "queued").length;
  const ranCount = nodes.filter((n) => n.data.status === "completed" || n.data.status === "skipped").length;
  const runningCount = nodes.filter((n) => n.data.status === "running").length;

  const edges: Edge[] = useMemo(() => {
    return (run?.graph?.edges || []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "smoothstep",
      className: "edge-run",
      style: { stroke: "#8b95a8", strokeWidth: 1.6 },
    }));
  }, [run]);

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
        <span className="chip">{run?.passes ?? 0} / {run?.max_passes ?? run?.graph?.max_passes ?? 4} passes</span>
        <span className="chip">{(run?.latency_seconds ?? 0).toFixed(2)}s</span>
        <span className="chip">{run?.tokens ?? 0} / {run?.max_tokens ?? maxTok} tok</span>
        <span className="chip">{ranCount} ran</span>
        <span className="chip">{runningCount ? `${runningCount} running` : `${waitingCount} not run`}</span>
        {run?.stop_reason && <span className="chip">{run.stop_reason}</span>}
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
            defaultEdgeOptions={{ type: "smoothstep", style: { stroke: "#8b95a8", strokeWidth: 1.6 } }}
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
          {!pick && <p className="sub">Click a node to inspect its stored input and output.</p>}
          {pick && !picked && <p className="sub">This node has no stored trace — it did not run.</p>}
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
          <div className="log mono">{logs.join("\n") || (run?.status === "running" ? "waiting for events" : "No stored events for this run.")}</div>
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
