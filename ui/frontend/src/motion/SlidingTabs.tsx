import { useLayoutEffect, useRef, useState } from "react";

export default function SlidingTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState({ left: 0, width: 0 });

  useLayoutEffect(() => {
    const el = root.current?.querySelector<HTMLButtonElement>(`button[data-id="${value}"]`);
    if (!el || !root.current) return;
    setBar({ left: el.offsetLeft, width: el.offsetWidth });
  }, [value, tabs]);

  return (
    <div className="tabs sliding" ref={root}>
      <span className="tab-indicator" style={{ transform: `translateX(${bar.left}px)`, width: bar.width }} />
      {tabs.map((t) => (
        <button key={t.id} type="button" data-id={t.id} className={value === t.id ? "on" : ""} onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
