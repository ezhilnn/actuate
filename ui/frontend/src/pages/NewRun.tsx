import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Provider } from "../api";

export default function NewRun() {
  const nav = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [provider, setProvider] = useState("nvidia");
  const [model, setModel] = useState("meta/llama-3.1-8b-instruct");
  const [prompt, setPrompt] = useState("Write a concise design for a closed-loop AI controller.");
  const [temperature, setTemperature] = useState(0.2);
  const [maxIterations, setMaxIterations] = useState(6);
  const [target, setTarget] = useState(0.95);
  const [gain, setGain] = useState(0.6);
  const [retry, setRetry] = useState("exponential");
  const [sensor, setSensor] = useState("rule");
  const [actuator, setActuator] = useState("prompt");
  const [controller, setController] = useState("rule");
  const [phrases, setPhrases] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ providers: Provider[] }>("/api/models")
      .then((data) => {
        setProviders(data.providers);
        const first = data.providers.find((p) => p.configured) || data.providers[0];
        if (first) {
          setProvider(first.id);
          setModel(first.default);
          setApiBase(first.api_base || "");
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const current = providers.find((p) => p.id === provider);
  const customizable = provider === "custom" || provider === "nvidia";

  useEffect(() => {
    if (!current) return;
    setModel(current.default);
    setApiBase(current.api_base || "");
  }, [provider, current]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const body: Record<string, unknown> = {
      prompt,
      provider,
      model,
      temperature,
      max_iterations: maxIterations,
      target_score: target,
      gain,
      retry_strategy: retry,
      sensor,
      actuator,
      controller,
      required_phrases: phrases.split(",").map((s) => s.trim()).filter(Boolean),
      min_length: 80,
      control_system_name: "console",
    };
    if (apiBase.trim()) body.api_base = apiBase.trim();
    if (apiKey.trim()) body.api_key = apiKey.trim();
    try {
      const created = await api<{ run_id: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify(body),
      });
      nav(`/live/${created.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    }
  }

  return (
    <>
      <h1>New run</h1>
      <p className="sub">
        Starts a real LLM plant. Save an API key in Settings first. The LIVE LLM badge on Live Session
        confirms the plant is not a mock.
      </p>
      {error && <p className="sub" style={{ color: "var(--red)" }}>{error}</p>}
      <form className="form-grid" onSubmit={onSubmit}>
        <div className="card">
          <label>Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <div className="card">
          <label>Provider</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} {p.configured ? "" : "(key missing)"}
              </option>
            ))}
          </select>
          <label>Model</label>
          {provider === "custom" ? (
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="llama-3.1-8b-instruct" />
          ) : (
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {(current?.models || [model]).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}
          {customizable && (
            <>
              <label>API base URL (OpenAI-compatible)</label>
              <input
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="https://integrate.api.nvidia.com/v1"
              />
              <label>API key for this run</label>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="nvapi-… or bearer token" />
            </>
          )}
          <label>Temperature {temperature}</label>
          <input type="range" min={0} max={1.2} step={0.05} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} />
          <label>Max iterations</label>
          <input type="number" value={maxIterations} onChange={(e) => setMaxIterations(Number(e.target.value))} />
          <label>Target score {target}</label>
          <input type="range" min={0.5} max={1} step={0.01} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
          <label>Gain {gain}</label>
          <input type="range" min={0} max={1} step={0.05} value={gain} onChange={(e) => setGain(Number(e.target.value))} />
          <label>Retry</label>
          <select value={retry} onChange={(e) => setRetry(e.target.value)}>
            <option value="none">none</option>
            <option value="exponential">exponential</option>
            <option value="diversity">diversity</option>
            <option value="temperature_sweep">temperature sweep</option>
            <option value="model_switch">model switch</option>
            <option value="prompt_perturbation">prompt perturbation</option>
          </select>
          <label>Sensor / actuator / controller</label>
          <select value={sensor} onChange={(e) => setSensor(e.target.value)}>
            <option value="rule">RuleEvaluator</option>
            <option value="llm_judge">LLMJudgeEvaluator</option>
            <option value="similarity">SimilarityEvaluator</option>
          </select>
          <select value={actuator} onChange={(e) => setActuator(e.target.value)}>
            <option value="prompt">PromptCorrector</option>
            <option value="output">OutputCorrector</option>
            <option value="strategy">StrategyCorrector</option>
            <option value="context">ContextCorrector</option>
          </select>
          <select value={controller} onChange={(e) => setController(e.target.value)}>
            <option value="rule">Rule-based</option>
            <option value="pid">PID</option>
          </select>
          <label>Required phrases (rule sensor)</label>
          <input value={phrases} onChange={(e) => setPhrases(e.target.value)} />
          <button className="primary" type="submit">Start loop</button>
        </div>
      </form>
    </>
  );
}
