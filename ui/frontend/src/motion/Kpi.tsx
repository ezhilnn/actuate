import { useEffect, useRef, useState } from "react";

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function useInterpolated(value: number, ms = 240) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  const start = useRef(0);
  useEffect(() => {
    from.current = shown;
    start.current = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start.current) / ms);
      const eased = 1 - (1 - t) * (1 - t);
      setShown(lerp(from.current, value, eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, ms]);
  return shown;
}

export function Kpi({
  title,
  value,
  suffix = "",
  hint,
  digits,
}: {
  title: string;
  value: number;
  suffix?: string;
  hint?: string;
  digits?: number;
}) {
  const shown = useInterpolated(value);
  const text =
    digits != null
      ? shown.toFixed(digits)
      : Number.isInteger(value)
        ? Math.round(shown).toLocaleString()
        : shown.toFixed(2);
  return (
    <div className="card kpi-card">
      <h3>{title}</h3>
      <div className="value">
        {text}
        {suffix}
      </div>
      {hint && <p className="sub kpi-hint">{hint}</p>}
    </div>
  );
}

export function StatusChip({ status }: { status?: string | null }) {
  const s = (status || "idle").toLowerCase();
  return <span className={`status ${s}`}>{s}</span>;
}
