import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, RunSummary } from "../api";
import { MetricChart, ScoreChart } from "../charts";

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
  events: { kind: string; at: number }[];
  best_score: number | null;
  latency_seconds: number;
  tokens: number;
  metadata: Record<string, string>;
};

function wsUrl(runId: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  if (import.meta.env.DEV) return `${proto}://127.0.0.1:8000/ws/runs/${runId}`;
  return `${proto}://${location.host}/ws/runs/${runId}`;
}

export default function LiveSession() {
  const { runId } = useParams();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [tab, setTab] = useState("output");
  const [open, setOpen] = useState<number | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    api<{ runs: RunSummary[] }>("/api/runs").then((d) => setRuns(d.runs)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!runId) return;
    let timer: number;
    const tick = async () => {
      const data = await api<Detail>(`/api/runs/${runId}`);
      setDetail(data);
      if (data.status === "running" || data.status === "pending") {
        timer = window.setTimeout(tick, 600);
      }
    };
    tick();
    const ws = new WebSocket(wsUrl(runId));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      setLogs((prev) => [`${new Date().toLocaleTimeString()}  ${msg.kind}`, ...prev].slice(0, 100));
    };
    return () => {
      window.clearTimeout(timer);
      ws.close();
    };
  }, [runId]);

  const last = detail?.iterations[detail.iterations.length - 1];
  const isStub = detail?.metadata?.plant === "stub" || detail?.metadata?.provider === "stub";
  const plantLabel = !detail
    ? "connecting…"
    : isStub
      ? "MOCK plant"
      : `LIVE LLM · ${detail.metadata?.provider || "llm"}`;
  const chart = useMemo(
    () =>
      (detail?.iterations || [])
        .filter((it) => it.score != null)
        .map((it) => ({ iteration: it.index, score: it.score as number })),
    [detail],
  );
  const tokenChart = useMemo(
    () =>
      (detail?.iterations || []).map((it) => ({
        iteration: it.index,
        tokens: it.tokens || 0,
        latency: it.latency_seconds || 0,
      })),
    [detail],
  );

  if (!runId) {
    return (
      <>
        <h1>Live session</h1>
        <p className="sub">Pick a run. This console streams a real control loop against an LLM plant — not a mock.</p>
        <div className="card">
          <table>
            <thead>
              <tr><th>Run</th><th>Status</th><th>Score</th><th>Iters</th></tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="mono"><Link to={`/live/${run.id}`}>{run.id.slice(0, 12)}</Link></td>
                  <td><span className={`status ${run.status}`}>{run.status}</span></td>
                  <td>{run.best_score?.toFixed(3) ?? "—"}</td>
                  <td>{run.iterations}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runs.length && <p className="sub">No runs yet. Configure an LLM in Settings, then start from New Run or Loop Designer.</p>}
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Live session</h1>
      <div className="chips">
        <span className={`chip ${!detail ? "" : isStub ? "bad" : "ok"}`}>{plantLabel}</span>
        <span className="chip">{detail?.metadata?.model || "—"}</span>
        <span className="chip">status {detail?.status || "…"}</span>
        <span className="chip">iteration {detail?.iterations.length ?? 0}</span>
        <span className="chip">score {detail?.best_score?.toFixed(3) ?? "—"}</span>
        <span className="chip">{(detail?.latency_seconds ?? 0).toFixed(2)}s · {detail?.tokens ?? 0} tok</span>
      </div>
      <div className="hero">
        <div className="card">
          <h3>Control loop</h3>
          {["plant (LLM)", "sensor", "error", "controller", "actuator"].map((name, i) => (
            <div key={name}>
              <div className={`loop-node ${i === (detail?.status === "running" ? 0 : 4) ? "active" : ""}`}>{name}</div>
              {i < 4 && <div className="arrow">↓</div>}
            </div>
          ))}
          <div className="arrow">↺ feedback to plant</div>
        </div>
        <div className="card" style={{ overflow: "auto" }}>
          <h3>Iterations</h3>
          {(detail?.iterations || []).map((it) => (
            <div className="iter" key={it.index}>
              <header onClick={() => setOpen(open === it.index ? null : it.index)}>
                <span>Iteration {it.index}</span>
                <span className="mono">score {it.score == null ? "…" : it.score.toFixed(3)}</span>
              </header>
              {open === it.index && (
                <>
                  <p className="sub">Prompt</p>
                  <pre>{it.prompt}</pre>
                  <p className="sub">LLM output</p>
                  <pre>{it.output}</pre>
                  <p className="sub">Sensor feedback</p>
                  <pre>{it.feedback.join("\n")}</pre>
                  {it.correction && (
                    <>
                      <p className="sub">Actuator (next prompt)</p>
                      <pre>{it.correction}</pre>
                    </>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
        <div className="card">
          <h3>Score trajectory</h3>
          <ScoreChart data={chart} />
          <h3>Tokens / iteration</h3>
          <MetricChart data={tokenChart} dataKey="tokens" color="#8b7cff" />
          <div className="tabs">
            {["output", "evaluation", "prompt", "logs"].map((t) => (
              <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>
          {tab === "output" && <pre>{last?.output || "waiting for plant…"}</pre>}
          {tab === "evaluation" && <pre>{last?.feedback.join("\n") || "waiting"}</pre>}
          {tab === "prompt" && <pre>{last?.prompt || "waiting"}</pre>}
          {tab === "logs" && <div className="log mono">{logs.join("\n") || "websocket idle"}</div>}
        </div>
      </div>
    </>
  );
}
