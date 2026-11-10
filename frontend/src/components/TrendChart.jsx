import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CAT } from "../api.js";
import { useI18n } from "../i18n/index.jsx";

/** Fill levels of both compartments over time (+ optional gas line on a 2nd axis). */
export default function TrendChart({ points, fullLevel, height = 240, showGas = false }) {
  const { t, fmt } = useI18n();
  if (!points?.length) return <p className="empty">{t("chart.noReadings")}</p>;
  // real time axis: readings are placed by their timestamp, not evenly spaced
  const data = points.map((p) => ({ ...p, t: new Date(p.created_at).getTime() }));
  const gasName = t("chart.gas");

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: showGas ? 4 : 16, left: -14, bottom: 0 }}>
        <CartesianGrid stroke="#eef1f5" />
        <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tickFormatter={(v) => fmt.dateTime(new Date(v))} tick={{ fontSize: 11, fill: "#475569" }} minTickGap={40} />
        <YAxis yAxisId="lvl" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`}
          tick={{ fontSize: 11, fill: "#475569" }} />
        {showGas && <YAxis yAxisId="gas" orientation="right" tick={{ fontSize: 11, fill: "#a16207" }} width={40} />}
        <Tooltip
          labelFormatter={(v) => fmt.dateTime(new Date(v))}
          formatter={(v, name) => [name === gasName ? `${v} ppm` : `${v}%`, name]}
        />
        <Legend wrapperStyle={{ fontSize: 13 }} />
        {fullLevel && <ReferenceLine yAxisId="lvl" y={fullLevel} stroke="#ef4444" strokeDasharray="4 4" />}
        <Line yAxisId="lvl" type="monotone" dataKey="organic_level" name={t("cat.organic")} stroke={CAT.organic.color}
          strokeWidth={2.2} dot={false} isAnimationActive={false} connectNulls />
        <Line yAxisId="lvl" type="monotone" dataKey="inorganic_level" name={t("cat.inorganic")} stroke={CAT.inorganic.color}
          strokeWidth={2.2} dot={false} isAnimationActive={false} connectNulls />
        {showGas && (
          <Line yAxisId="gas" type="monotone" dataKey="gas_ppm" name={gasName} stroke="#eab308"
            strokeWidth={1.5} strokeDasharray="5 3" dot={false} isAnimationActive={false} connectNulls />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
