import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import NewRun from "./pages/NewRun";
import LiveSession from "./pages/LiveSession";
import Runs from "./pages/Runs";
import Designer from "./pages/Designer";
import GraphRun from "./pages/GraphRun";
import Models from "./pages/Models";
import Plugins from "./pages/Plugins";
import Settings from "./pages/Settings";
import Observability from "./pages/Observability";
import Memory from "./pages/Memory";
import Benchmarks from "./pages/Benchmarks";
import CommandPalette from "./motion/CommandPalette";
import { ToastHost } from "./motion/Toasts";

const links = [
  ["/", "Dashboard"],
  ["/new", "New Run"],
  ["/live", "Live Session"],
  ["/runs", "Runs"],
  ["/designer", "Loop Designer"],
  ["/benchmarks", "Benchmarks"],
  ["/memory", "Memory"],
  ["/models", "Models"],
  ["/plugins", "Plugins"],
  ["/observability", "Observability"],
  ["/settings", "Settings"],
];

export default function App() {
  const [boot, setBoot] = useState(true);
  const loc = useLocation();
  useEffect(() => {
    const t = window.setTimeout(() => setBoot(false), 640);
    return () => window.clearTimeout(t);
  }, []);
  return (
    <ToastHost>
      <div className="shell">
        {boot && (
          <div className="boot-full">
            <img src="/logo.png" alt="" className="brand-mark lg" />
            <p>Actuate</p>
            <span>Preparing workspace…</span>
          </div>
        )}
        <aside className="sidebar">
          <div className="brand">
            <img src="/logo.png" alt="Actuate" className="brand-mark" />
            ACTUATE
          </div>
          <p className="side-tag">Closed-loop agent console</p>
          <nav className="nav">
            {links.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
                {label}
              </NavLink>
            ))}
          </nav>
          <p className="side-hint">Ctrl/Cmd + K</p>
        </aside>
        <main className="workspace">
          <div key={loc.pathname} className="workspace-page">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/new" element={<NewRun />} />
              <Route path="/live" element={<LiveSession />} />
              <Route path="/live/:runId" element={<LiveSession />} />
              <Route path="/runs" element={<Runs />} />
              <Route path="/designer" element={<Designer />} />
              <Route path="/graph/:runId" element={<GraphRun />} />
              <Route path="/benchmarks" element={<Benchmarks />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="/models" element={<Models />} />
              <Route path="/plugins" element={<Plugins />} />
              <Route path="/observability" element={<Observability />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
        <CommandPalette />
      </div>
    </ToastHost>
  );
}
