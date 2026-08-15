import { useEffect, useState } from "react";
import { api } from "../api";

type Cap = {
  kind: string;
  name: string;
  version: string;
  author: string;
  description: string;
};

export default function Plugins() {
  const [caps, setCaps] = useState<Cap[]>([]);
  useEffect(() => {
    api<{ capabilities: Cap[] }>("/api/capabilities").then((d) => setCaps(d.capabilities));
  }, []);
  return (
    <>
      <h1>Capability registry</h1>
      <p className="sub">Every replaceable layer — plants, sensors, actuators, controllers, retry, fusion.</p>
      <div className="card">
        <table>
          <thead><tr><th>Kind</th><th>Name</th><th>Version</th><th>Description</th></tr></thead>
          <tbody>
            {caps.map((c) => (
              <tr key={`${c.kind}:${c.name}`}>
                <td className="mono">{c.kind}</td>
                <td>{c.name}</td>
                <td>{c.version}</td>
                <td>{c.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
