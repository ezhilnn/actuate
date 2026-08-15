import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../api";

export default function AuthGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [need, setNeed] = useState(false);
  const [token, setLocal] = useState(getToken());
  const [err, setErr] = useState("");

  useEffect(() => {
    const boot = async () => {
      try {
        const health = await fetch("/api/health").then((r) => r.json());
        if (health.console_token) setToken(health.console_token);
        if (health.auth_required && !getToken() && !health.console_token) setNeed(true);
        else setNeed(false);
      } catch {
        setNeed(false);
      } finally {
        setReady(true);
      }
    };
    boot();
    const onAuth = () => setNeed(true);
    window.addEventListener("actuate-auth", onAuth);
    return () => window.removeEventListener("actuate-auth", onAuth);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ token }) });
      setToken(token);
      setNeed(false);
    } catch {
      setErr("Token rejected.");
    }
  }

  if (!ready) return <div className="boot inline"><div className="boot-orb" /><p>Connecting…</p></div>;
  if (need) {
    return (
      <div className="auth-gate">
        <img src="/logo.png" alt="" className="brand-mark lg" />
        <h1>Actuate console</h1>
        <p className="sub">This API requires a console token. On the same machine it is issued via /api/health. Otherwise paste the token from the server keychain (provider console_auth).</p>
        <form className="card" onSubmit={onSubmit} style={{ maxWidth: 420 }}>
          <label>Console token</label>
          <input value={token} onChange={(e) => setLocal(e.target.value)} autoComplete="off" />
          {err && <p className="sub" style={{ color: "var(--red)" }}>{err}</p>}
          <button className="primary btn-press" type="submit">Unlock</button>
        </form>
      </div>
    );
  }
  return <>{children}</>;
}
