import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, RunSummary } from "../api";
import { MetricChart, ScoreChart } from "../charts";
import { StatusChip } from "../motion/Kpi";
import SlidingTabs from "../motion/SlidingTabs";
import { useToast } from "../motion/Toasts";

type Iteration = {
  index: number;
  prompt: string | null;
  output: string | null;
  score: number | null;
  error: number | null;
  feedback: string[];
  correction: string | null;
  latency_seconds: number | null;
  tokens?: number;
};

type Detail = {
  id: string;
  status: string;
  iterations: Iteration[];
  events: { kind: string; at: number; data?: Record<string, unknown> }[];
  best_score: number | null;
  latency_seconds: number;
  tokens: number;
  metadata: Record<string, string>;
  graph?: unknown;
};

function wsUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  if (import.meta.env.DEV) return `${proto}://127.0.0.1:8000/ws/runs/${runId}`;
  return `${proto}://${location.host}/ws/runs/${runId}`;
}

const STAGES = [
  { id: "plant", label: "plant (LLM)" },
  { id: "sensor", label: "sensor" },
  { id: "error", label: "error" },
  { id: "controller", label: "controller" },
  { id: "actuator", label: "actuator" },
] as const;

export default function LiveSession() {
  const { runId } = useParams();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [tab, setTab] = useState("output");
  const [open, setOpen] = useState<number | null>(1);
  const [stage, setStage] = useState<(typeof STAGES)[number]["id"]>("plant");
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();
  const lastStatus = useRef<string | null>(null);

  useEffect(() => {
    api<{ runs: RunSummary[] }>("/api/runs").then((d) => setRuns(d.runs)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!runId) {
      setLoading(false);
      return;
    }
    let timer: number;
    const tick = async () => {
      const data = await api<Detail>(`/api/runs/${runId}`);
      setDetail(data);
      setLoading(false);
      if (lastStatus.current && lastStatus.current !== data.status && data.status !== "running" && data.status !== "pending") {
        toast(
          data.status === "converged" ? "✓ Execution completed" : `Loop ${data.status}`,
          `${data.iterations?.length ?? 0} iterations · ${(data.latency_seconds ?? 0).toFixed(2)}s`,
        );
      }
      lastStatus.current = data.status;
      if (data.status === "running" || data.status === "pending") {
        timer = window.setTimeout(tick, 600);
      }
    };
    tick();
    const ws = new WebSocket(wsUrl(runId));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      setLogs((prev) => [`${new Date().toLocaleTimeString()}  ${msg.kind} ${JSON.stringify(msg.data || {}).slice(0, 180)}`, ...prev].slice(0, 200));
    };
    return () => {
      window.clearTimeout(timer);
      ws.close();
    };
  }, [runId]);

  const last = detail?.iterations[detail.iterations.length - 1];
  const view = detail?.iterations.find((it) => it.index === open) || last;
  const isStub = detail?.metadata?.plant === "stub" || detail?.metadata?.provider === "stub";
  const title = detail?.metadata?.name || "Loop run";
  const chart = useMemo(
    () => (detail?.iterations || []).filter((it) => it.score != null).map((it) => ({ iteration: it.index, score: it.score as number })),
    [detail],
  );
  const tokenChart = useMemo(
    () => (detail?.iterations || []).map((it) => ({ iteration: it.index, tokens: it.tokens || 0 })),
    [detail],
  );

  const stageIO = (it: Iteration | undefined, id: string) => {
    if (!it) return { input: "waiting…", output: "waiting…", extra: "" };
    if (id === "plant") return { input: it.prompt || "", output: it.output || "", extra: `${it.latency_seconds ?? 0}s · ${it.tokens ?? 0} tok` };
    if (id === "sensor") return { input: it.output || "", output: (it.feedback || []).join("\n"), extra: `score ${it.score ?? "—"}` };
    if (id === "error") return { input: `measured ${it.score}`, output: `error ${it.error}`, extra: "" };
    if (id === "controller") return { input: `error ${it.error}  score ${it.score}`, output: it.correction ? "revise prompt (actuate)" : "hold / publish", extra: "" };
    return { input: (it.feedback || []).join("\n"), output: it.correction || "(no correction — loop stopped)", extra: "" };
  };

  if (!runId) {
    return (
      <div className="fade-in">
        <h1>Live session</h1>
        <p className="sub">Open a named loop. Graph runs are under Runs → type Graph, or New Run → Multi-agent graph.</p>
        <div className="card">
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>Score</th><th>Iters</th></tr></thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td><Link to={`/live/${run.id}`}>{(run as RunSummary & { name?: string }).name || "Loop run"}</Link></td>
                  <td><span className={`status ${run.status}`}>{run.status}</span></td>
                  <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                  <td>{run.iterations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (loading && !detail) {
    return <div className="boot inline"><div className="boot-orb" /><p>Loading session…</p></div>;
  }

  const io = stageIO(view, stage);

  return (
    <div className="fade-in">
      <h1>{title}</h1>
      <p className="sub">{detail?.metadata?.prompt || "Closed-loop plant → sensor → controller → actuator."}</p>
      <div className="chips">
        <span className={`chip ${isStub ? "bad" : "ok"}`}>{isStub ? "MOCK" : `LIVE LLM · ${detail?.metadata?.provider}`}</span>
        <span className="chip">{detail?.metadata?.model}</span>
        <span className="chip"><StatusChip status={detail?.status} /></span>
        <span className="chip">{detail?.iterations.length} iterations</span>
        <span className="chip">score {detail?.best_score?.toFixed(3)}</span>
        <span className="chip">{(detail?.latency_seconds ?? 0).toFixed(2)}s · {detail?.tokens ?? 0} tok</span>
      </div>
      <div className="hero">
        <div className="card">
          <h3>Click a node</h3>
          {STAGES.map((s, i) => (
            <div key={s.id}>
              <button
                type="button"
                className={`loop-node ${stage === s.id ? "active" : ""}`}
                onClick={() => setStage(s.id)}
              >
                {s.label}
              </button>
              {i < STAGES.length - 1 && <div className="arrow">↓</div>}
            </div>
          ))}
          <div className="arrow">↺ feedback to plant</div>
        </div>
        <div className="card" style={{ overflow: "auto" }}>
          <h3>{STAGES.find((s) => s.id === stage)?.label} · iteration {view?.index ?? "—"}</h3>
          <p className="sub">{io.extra}</p>
          <p className="sub">Input into this node</p>
          <pre>{io.input}</pre>
          <p className="sub">Output from this node</p>
          <pre>{io.output}</pre>
          <h3>All iterations</h3>
          {(detail?.iterations || []).map((it) => (
            <div className={`iter ${open === it.index ? "open" : ""}`} key={it.index}>
              <header onClick={() => setOpen(it.index)}>
                <span>Iteration {it.index}</span>
                <span className="mono">score {it.score == null ? "…" : it.score.toFixed(3)} · {it.tokens ?? 0} tok · {(it.latency_seconds ?? 0).toFixed(2)}s</span>
              </header>
              {open === it.index && (
                <>
                  <p className="sub">Plant prompt</p>
                  <pre>{it.prompt}</pre>
                  <p className="sub">Plant output</p>
                  <pre>{it.output}</pre>
                  <p className="sub">Sensor</p>
                  <pre>{it.feedback.join("\n")}</pre>
                  <p className="sub">Actuator next prompt</p>
                  <pre>{it.correction || "(none — this was the last iteration)"}</pre>
                </>
              )}
            </div>
          ))}
        </div>
        <div className="card" style={{ overflow: "auto" }}>
          <h3>Metrics</h3>
          <ScoreChart data={chart} />
          <MetricChart data={tokenChart} dataKey="tokens" color="#8b7cff" />
          <SlidingTabs
            tabs={["output", "evaluation", "prompt", "events", "logs"].map((t) => ({ id: t, label: t }))}
            value={tab}
            onChange={setTab}
          />
          {tab === "output" && <pre>{last?.output}</pre>}
          {tab === "evaluation" && <pre>{last?.feedback.join("\n")}</pre>}
          {tab === "prompt" && <pre>{last?.prompt}</pre>}
          {tab === "events" && (
            <pre>{(detail?.events || []).map((e) => `${e.kind} ${JSON.stringify(e.data || {})}`).join("\n\n")}</pre>
          )}
          {tab === "logs" && <div className="log mono">{logs.join("\n")}</div>}
        </div>
      </div>
    </div>
  );
}
