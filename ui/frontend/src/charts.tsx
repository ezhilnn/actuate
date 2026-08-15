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

export function ScoreChart({ data }: { data: { iteration: number; score: number }[] }) {
  if (!data.length) return <p className="sub">No score series yet.</p>;
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#232a36" />
          <XAxis dataKey="iteration" stroke="#8b96a8" />
          <YAxis domain={[0, 1]} stroke="#8b96a8" />
          <Tooltip contentStyle={tooltip} />
          <Line type="monotone" dataKey="score" stroke="#3d8bfd" strokeWidth={2} dot />
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
  if (!data.length) return <p className="sub">No series yet.</p>;
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid stroke="#232a36" />
          <XAxis dataKey="iteration" stroke="#8b96a8" />
          <YAxis stroke="#8b96a8" />
          <Tooltip contentStyle={tooltip} />
          <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
