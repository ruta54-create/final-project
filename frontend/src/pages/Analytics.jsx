import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download } from "lucide-react";
import { CAT, COMPARTMENTS, usePolling } from "../api.js";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import TrendChart from "../components/TrendChart.jsx";
import { Card, Chips, ErrorBox, Loading, Stat } from "../components/ui.jsx";

export default function Analytics() {
  const { bin } = useBin();
  const { t, fmt, itemLabel } = useI18n();
  const [days, setDays] = useState(7);
  const { data, error } = usePolling(`/bins/${bin.id}/analytics/?days=${days}`, 30000);
  const { data: readings } = usePolling(`/bins/${bin.id}/readings/?hours=${days * 24}`, 30000);

  const ranges = [1, 7, 30].map((d) => ({ value: d, label: t(`ana.range.${d}`) }));
  const share = data?.total ? data.organic / data.total : null;
  const pie = data ? COMPARTMENTS.map((c) => ({ name: t(`cat.${c}`), value: data[c], color: CAT[c].color })) : [];
  const bars = (key) => (
    <Bar key={key} dataKey={key} name={t(`cat.${key}`)} stackId="a" fill={CAT[key].color} isAnimationActive={false} />
  );

  return (
    <>
      <Header title={t("ana.title")} subtitle={t("ana.subtitle")} />
      <div className="row-between">
        <Chips options={ranges} value={days} onChange={setDays} />
        <div className="toolbar">
          {["detections", "readings", "collections"].map((type) => (
            <a key={type} className="btn-outline small" href={`/api/bins/${bin.id}/export/?type=${type}&days=${days}`}>
              <Download size={14} /> {t(`ana.csv.${type}`)}
            </a>
          ))}
        </div>
      </div>
      <ErrorBox error={error} />
      {!data ? <Loading /> : (
        <>
          <section className="stats">
            <Stat tone="blue" label={t("ana.itemsSorted")} value={data.total}
              sub={t("ana.inLast", { range: t(`ana.range.${days}`) })} />
            <Stat tone="green" label={t("ana.organicShare")} value={fmt.pct(share)}
              sub={t("ana.split", { o: data.organic, i: data.inorganic })} />
            <Stat tone="purple" label={t("ana.avgConfidence")} value={fmt.pct(data.avg_confidence)}
              sub={t("ana.confSplit", { o: fmt.pct(data.confidence_by_category.organic), i: fmt.pct(data.confidence_by_category.inorganic) })} />
            <Stat tone="yellow" label={t("ana.uncertainItems")} value={fmt.pct(data.total ? data.uncertain / data.total : null)}
              sub={t("ana.uncertainSub", { n: data.uncertain })} />
          </section>

          <section className="grid-2">
            <Card title={t("ana.perDay")}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data.per_day} margin={{ left: -18 }}>
                  <CartesianGrid stroke="#eef1f5" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} tickFormatter={(d) => fmt.shortDay(d)} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={(d) => fmt.shortDay(d)} />
                  <Legend />
                  {bars("organic")}
                  {bars("inorganic")}
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title={t("ana.busiest")}>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data.per_hour} margin={{ left: -18 }}>
                  <CartesianGrid stroke="#eef1f5" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 11 }} tickFormatter={(h) => t("ana.hourTick", { h })} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip labelFormatter={(h) => t("ana.hourRange", { h })} />
                  {bars("organic")}
                  {bars("inorganic")}
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </section>

          <section className="grid-3">
            <Card title={t("ana.split2")}>
              <div className="donut">
                <ResponsiveContainer width="100%" height={210}>
                  <PieChart>
                    <Pie data={pie} dataKey="value" innerRadius={60} outerRadius={95} startAngle={90} endAngle={-270}
                      stroke="#fff" isAnimationActive={false}>
                      {pie.map((p) => <Cell key={p.name} fill={p.color} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center"><small>{t("common.total")}</small><strong>{data.total}</strong><small>{t("common.items")}</small></div>
              </div>
            </Card>
            <Card title={t("ana.common")}>
              <ul className="conf-bars">
                {data.top_labels.map((row) => (
                  <li key={row.label}>
                    <span>{itemLabel(row.label)}</span>
                    <div className="progress"><div className="progress-bar" style={{ width: `${(row.count / data.top_labels[0].count) * 100}%` }} /></div>
                    <strong>{row.count}</strong>
                  </li>
                ))}
                {!data.top_labels.length && <p className="empty">{t("ana.noItems")}</p>}
              </ul>
            </Card>
            <Card title={t("ana.collections")}>
              <ul className="sysinfo">
                {COMPARTMENTS.map((c) => {
                  const col = data.collections[c];
                  return (
                    <li key={c}>
                      <span style={{ color: CAT[c].text }}>{t(`cat.${c}`)}</span>
                      <strong>
                        {t("ana.times", { n: col.count, count: col.count })}
                        {col.avg_hours_between ? t("ana.every", { h: Math.round(col.avg_hours_between) }) : ""}
                      </strong>
                    </li>
                  );
                })}
              </ul>
              <p className="muted small-text">{t("ana.collectionsNote")}</p>
            </Card>
          </section>

          <Card title={t("ana.history")}>
            <TrendChart points={readings?.points} fullLevel={bin.full_level} height={300} showGas />
          </Card>
        </>
      )}
    </>
  );
}
