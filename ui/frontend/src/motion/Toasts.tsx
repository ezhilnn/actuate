import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Toast = { id: number; title: string; detail?: string };

const Ctx = createContext<(title: string, detail?: string) => void>(() => undefined);

export function ToastHost({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((title: string, detail?: string) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, title, detail }].slice(-4));
    window.setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4200);
  }, []);
  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="toast">
            <strong>{t.title}</strong>
            {t.detail && <span>{t.detail}</span>}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
