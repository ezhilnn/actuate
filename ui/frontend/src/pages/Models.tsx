import { useEffect, useState } from "react";
import { api, Provider } from "../api";

export default function Models() {
  const [providers, setProviders] = useState<Provider[]>([]);
  useEffect(() => {
    api<{ providers: Provider[] }>("/api/models").then((d) => setProviders(d.providers));
  }, []);
  return (
    <>
      <h1>Model manager</h1>
      <p className="sub">Choose a provider and model on New Run. Keys are stored in Settings / Postgres.</p>
      <div className="provider-grid">
        {providers.map((p) => (
          <div className="card" key={p.id}>
            <h3>{p.name}</h3>
            <div className={p.configured ? "badge" : "badge off"}>{p.configured ? "configured" : "needs key"}</div>
            <p className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>
              {p.models.join(" · ")}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}
