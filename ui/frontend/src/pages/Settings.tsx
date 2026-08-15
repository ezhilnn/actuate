import { FormEvent, useEffect, useState } from "react";
import { api, getToken, setToken } from "../api";

export default function Settings() {
  const [provider, setProvider] = useState("nvidia");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("https://integrate.api.nvidia.com/v1");
  const [msg, setMsg] = useState("");
  const [configured, setConfigured] = useState<Record<string, boolean>>({});
  const [health, setHealth] = useState<{ llm_connected: boolean; hint?: string | null } | null>(null);
  const [consoleTok, setConsoleTok] = useState(getToken());

  async function refresh() {
    const [keys, h] = await Promise.all([
      api<{ configured: Record<string, boolean> }>("/api/keys"),
      api<{ llm_connected: boolean; hint?: string | null }>("/api/health"),
    ]);
    setConfigured(keys.configured);
    setHealth(h);
  }

  useEffect(() => {
    refresh().catch(console.error);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await api("/api/keys", {
      method: "POST",
      body: JSON.stringify({
        provider,
        api_key: apiKey,
        api_base: apiBase || undefined,
      }),
    });
    setMsg(`Saved ${provider}. Dashboard will show LLM connected.`);
    setApiKey("");
    await refresh();
  }

  return (
    <>
      <h1>Settings</h1>
      <p className="sub">
        This product only talks to real LLM endpoints. There is no mock plant in the console.
        NVIDIA uses integrate.api.nvidia.com. Custom is any OpenAI-compatible /v1 chat/completions URL.
      </p>
      <div className="chips">
        <span className={`chip ${health?.llm_connected ? "ok" : "bad"}`}>
          {health?.llm_connected ? "LLM connected" : "Not connected"}
        </span>
        {Object.entries(configured).map(([id, ok]) => (
          <span className={`chip ${ok ? "ok" : ""}`} key={id}>{id}{ok ? "" : " — empty"}</span>
        ))}
      </div>
      <form
        className="card"
        style={{ maxWidth: 520, marginBottom: 16 }}
        onSubmit={(e) => {
          e.preventDefault();
          setToken(consoleTok);
          setMsg("Console token saved in this browser.");
        }}
      >
        <h3>API auth</h3>
        <p className="sub">Required when ACTUATE_AUTH is on. Localhost receives the token from health automatically.</p>
        <label>Console token</label>
        <input value={consoleTok} onChange={(e) => setConsoleTok(e.target.value)} autoComplete="off" />
        <button className="primary btn-press" type="submit">Save token</button>
      </form>
      <form className="card" onSubmit={onSubmit} style={{ maxWidth: 520 }}>
        <label>Provider</label>
        <select
          value={provider}
          onChange={(e) => {
            setProvider(e.target.value);
            if (e.target.value === "nvidia") setApiBase("https://integrate.api.nvidia.com/v1");
            if (e.target.value === "custom") setApiBase("");
            if (e.target.value === "ollama") setApiBase("http://localhost:11434");
          }}
        >
          <option value="nvidia">NVIDIA NIM</option>
          <option value="custom">Custom OpenAI-compatible</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="gemini">Gemini</option>
          <option value="groq">Groq</option>
          <option value="openrouter">OpenRouter</option>
          <option value="ollama">Ollama (local LLM)</option>
        </select>
        {(provider === "nvidia" || provider === "custom" || provider === "ollama") && (
          <>
            <label>API base URL</label>
            <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="https://host/v1" />
          </>
        )}
        <label>API key {provider === "ollama" ? "(use any placeholder like local)" : ""}</label>
        <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} required />
        <button className="primary" type="submit">Save</button>
        {msg && <p className="sub">{msg}</p>}
      </form>
    </>
  );
}
