import { NavLink, Route, Routes } from "react-router-dom";
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
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span /> ACTUATE</div>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="workspace">
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
      </main>
    </div>
  );
}
