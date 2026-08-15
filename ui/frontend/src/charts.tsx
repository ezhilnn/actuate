import { useEffect, useRef } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const tooltip = { background: "#10131a", border: "1px solid #232a36", color: "#e8edf5" };

function useDrawOnChange<T>(data: T[]) {
  const prev = useRef(0);
  const len = data.length;
  const animate = len !== prev.current;
  useEffect(() => {
    prev.current = len;
  }, [len]);
  return animate;
}

export function ScoreChart({ data }: { data: { iteration: number; score: number }[] }) {
  const animate = useDrawOnChange(data);
  if (!data.length) return <p className="sub">No score series yet.</p>;
  return (
    <div style={{ width: "100%", height: 200 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#232a36" />
          <XAxis dataKey="iteration" stroke="#8b96a8" />
          <YAxis domain={[0, 1]} stroke="#8b96a8" />
          <Tooltip contentStyle={tooltip} />
          <Line type="monotone" dataKey="score" stroke="#3d8bfd" strokeWidth={2} dot isAnimationActive={animate} animationDuration={280} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MetricChart({
  data,
  dataKey,
  color = "#8b7cff",
}: {
  data: Record<string, number>[];
  dataKey: string;
  color?: string;
}) {
  const animate = useDrawOnChange(data);
  if (!data.length) return <p className="sub">No series yet.</p>;
  return (
    <div style={{ width: "100%", height: 200 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid stroke="#232a36" />
          <XAxis dataKey="iteration" stroke="#8b96a8" />
          <YAxis stroke="#8b96a8" />
          <Tooltip contentStyle={tooltip} />
          <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} isAnimationActive={animate} animationDuration={280} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CountBar({
  data,
  nameKey,
  valueKey,
  color = "#3d8bfd",
}: {
  data: Record<string, string | number>[];
  nameKey: string;
  valueKey: string;
  color?: string;
}) {
  const animate = useDrawOnChange(data);
  if (!data.length) return <p className="sub">No breakdown yet.</p>;
  return (
    <div style={{ width: "100%", height: 200 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 24 }}>
          <CartesianGrid stroke="#232a36" />
          <XAxis type="number" stroke="#8b96a8" />
          <YAxis type="category" dataKey={nameKey} stroke="#8b96a8" width={88} />
          <Tooltip contentStyle={tooltip} />
          <Bar dataKey={valueKey} fill={color} radius={[0, 4, 4, 0]} isAnimationActive={animate} animationDuration={240} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
