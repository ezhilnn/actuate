import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const DEST = [
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

export default function CommandPalette() {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setQ("");
        setI(0);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const hits = useMemo(() => {
    const n = q.trim().toLowerCase();
    return DEST.filter(([, label]) => !n || label.toLowerCase().includes(n) || n.split(" ").every((p) => label.toLowerCase().includes(p)));
  }, [q]);

  if (!open) return null;
  return (
    <div className="cmdk-back" onClick={() => setOpen(false)}>
      <div
        className="cmdk"
        role="dialog"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setI((x) => Math.min(hits.length - 1, x + 1));
          }
          if (e.key === "ArrowUp") {
            e.preventDefault();
            setI((x) => Math.max(0, x - 1));
          }
          if (e.key === "Enter" && hits[i]) {
            nav(hits[i][0]);
            setOpen(false);
          }
        }}
      >
        <input
          autoFocus
          placeholder="Go to a workspace…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setI(0);
          }}
        />
        <ul>
          {hits.map(([to, label], idx) => (
            <li key={to}>
              <button
                type="button"
                className={idx === i ? "on" : ""}
                onMouseEnter={() => setI(idx)}
                onClick={() => {
                  nav(to);
                  setOpen(false);
                }}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
        <p className="sub">Ctrl/Cmd + K · Enter to jump</p>
      </div>
    </div>
  );
}
