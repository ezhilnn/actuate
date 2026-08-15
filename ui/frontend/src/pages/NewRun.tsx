import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Provider } from "../api";
import SlidingTabs from "../motion/SlidingTabs";

type Template = {
  id: string;
  name: string;
  blurb: string;
  nodes: unknown[];
  edges: unknown[];
  target_score: number;
  max_passes: number;
};

export default function NewRun() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"graph" | "loop">("graph");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [provider, setProvider] = useState("nvidia");
  const [model, setModel] = useState("meta/llama-3.1-8b-instruct");
  const [name, setName] = useState("Water advisory brief");
  const [prompt, setPrompt] = useState(
    "A coastal town of 40,000 people has had three boil-water advisories in 18 months. Write a cautious public brief: known vs unknown, 72-hour actions, higher-risk groups, what to measure next. NEED SOURCE if unsupported. Not medical advice.",
  );
  const [temperature, setTemperature] = useState(0.2);
  const [maxIterations, setMaxIterations] = useState(6);
  const [minIterations, setMinIterations] = useState(3);
  const [target, setTarget] = useState(0.95);
  const [gain, setGain] = useState(0.6);
  const [retry, setRetry] = useState("exponential");
  const [sensor, setSensor] = useState("llm_judge");
  const [actuator, setActuator] = useState("prompt");
  const [controller, setController] = useState("rule");
  const [phrases, setPhrases] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [maxTokens, setMaxTokens] = useState(250000);

  useEffect(() => {
    Promise.all([
      api<{ providers: Provider[] }>("/api/models"),
      api<{ templates: Template[] }>("/api/graph-templates"),
    ]).then(([data, t]) => {
      setProviders(data.providers);
      setTemplates(t.templates);
      const complex = t.templates.find((x) => x.id === "data_science_lab") || t.templates[0];
      if (complex) setTemplateId(complex.id);
      const first = data.providers.find((p) => p.configured) || data.providers[0];
      if (first) {
        setProvider(first.id);
        setModel(first.default);
        setApiBase(first.api_base || "");
      }
    }).catch((err: Error) => setError(err.message)).finally(() => setLoading(false));
  }, []);

  const current = providers.find((p) => p.id === provider);
  const selectedTpl = templates.find((t) => t.id === templateId);
  const customizable = provider === "custom" || provider === "nvidia";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (mode === "graph") {
        if (!selectedTpl) throw new Error("Pick a graph template (or build one in Loop Designer).");
        const created = await api<{ run_id: string }>("/api/graphs/run", {
          method: "POST",
          body: JSON.stringify({
            prompt,
            name,
            graph: selectedTpl,
            provider,
            model,
            temperature,
            api_base: apiBase || undefined,
            api_key: apiKey || undefined,
            max_tokens: maxTokens,
          }),
        });
        nav(`/graph/${created.run_id}`);
        return;
      }
      const created = await api<{ run_id: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          prompt,
          name,
          provider,
          model,
          temperature,
          max_iterations: maxIterations,
          min_iterations: minIterations,
          target_score: target,
          gain,
          retry_strategy: retry,
          sensor,
          actuator,
          controller,
          required_phrases: phrases.split(",").map((s) => s.trim()).filter(Boolean),
          min_length: 80,
          control_system_name: name,
          api_base: apiBase.trim() || undefined,
          api_key: apiKey.trim() || undefined,
        }),
      });
      nav(`/live/${created.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    }
  }

  if (loading) {
    return <div className="boot inline"><div className="boot-orb" /><p>Loading run studio…</p></div>;
  }

  return (
    <div className="fade-in">
      <h1>New run</h1>
      <p className="sub">
        Run a multi-agent graph (20+ specialists + judges) or a classic control loop. Both use a live LLM. Give the run a name you will recognize later.
      </p>
      <SlidingTabs
        tabs={[
          { id: "graph", label: "Multi-agent graph" },
          { id: "loop", label: "Control loop" },
        ]}
        value={mode}
        onChange={(id) => setMode(id as "graph" | "loop")}
      />
      {error && <p className="sub" style={{ color: "var(--red)" }}>{error}</p>}
      <form className="form-grid" onSubmit={onSubmit}>
        <div className="card">
          <label>Run name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Water advisory v2" />
          <label>Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <div className="card">
          {mode === "graph" && (
            <>
              <label>Graph template</label>
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.nodes.length} nodes)
                  </option>
                ))}
              </select>
              {selectedTpl && <p className="sub">{selectedTpl.blurb} · {selectedTpl.nodes.length} nodes. Or design your own in Loop Designer.</p>}
            </>
          )}
          <label>LLM plant</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>{p.name} {p.configured ? "" : "(key missing)"}</option>
            ))}
          </select>
          <label>Model</label>
          {provider === "custom" ? (
            <input value={model} onChange={(e) => setModel(e.target.value)} />
          ) : (
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {(current?.models || [model]).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          )}
          {customizable && (
            <>
              <label>API base</label>
              <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
              <label>API key for this run</label>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            </>
          )}
          {mode === "loop" && (
            <>
              <label>Min iterations (quality loop will not stop before this)</label>
              <input type="number" min={1} value={minIterations} onChange={(e) => setMinIterations(Number(e.target.value))} />
              <label>Max iterations</label>
              <input type="number" value={maxIterations} onChange={(e) => setMaxIterations(Number(e.target.value))} />
              <label>Target {target}</label>
              <input type="range" min={0.5} max={1} step={0.01} value={target} onChange={(e) => setTarget(Number(e.target.value))} />
              <label>Sensor</label>
              <select value={sensor} onChange={(e) => setSensor(e.target.value)}>
                <option value="llm_judge">LLM judge (recommended — forces real scoring)</option>
                <option value="rule">Rule evaluator</option>
                <option value="similarity">Similarity</option>
              </select>
              <select value={actuator} onChange={(e) => setActuator(e.target.value)}>
                <option value="prompt">Prompt corrector</option>
                <option value="output">Output corrector</option>
                <option value="strategy">Strategy corrector</option>
              </select>
              <select value={controller} onChange={(e) => setController(e.target.value)}>
                <option value="rule">Rule</option>
                <option value="pid">PID</option>
              </select>
              <label>Retry</label>
              <select value={retry} onChange={(e) => setRetry(e.target.value)}>
                <option value="exponential">exponential</option>
                <option value="diversity">diversity</option>
                <option value="none">none</option>
              </select>
              <label>Required phrases</label>
              <input value={phrases} onChange={(e) => setPhrases(e.target.value)} />
            </>
          )}
          <label>Token budget (hard stop)</label>
          <input type="number" min={2000} value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
          <button className="primary btn-press" type="submit">{mode === "graph" ? "Run graph" : "Start loop"}</button>
        </div>
      </form>
    </div>
  );
}
