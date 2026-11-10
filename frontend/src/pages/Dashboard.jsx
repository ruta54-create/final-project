import { Link } from "react-router-dom";
import { Leaf, Package, Recycle, Wind } from "lucide-react";
import { COMPARTMENTS, usePolling } from "../api.js";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import CameraCard from "../components/CameraCard.jsx";
import Compartments, { StatusPill } from "../components/Compartments.jsx";
import TrendChart from "../components/TrendChart.jsx";
import Recommendations from "../components/Recommendations.jsx";
import ActivityList from "../components/ActivityList.jsx";
import { Card, ErrorBox, Loading, Stat } from "../components/ui.jsx";

const TONE = { success: "green", warning: "yellow", danger: "red", muted: "blue" };

export default function Dashboard() {
  const { bin } = useBin();
  const { t, fmt } = useI18n();
  const { data, error, reload } = usePolling(`/bins/${bin.id}/overview/`, 3000);
  const latest = data?.latest;

  return (
    <>
      <Header title={t("dash.title")} subtitle={t("dash.subtitle")} />
      <ErrorBox error={data && error ? t("common.liveFailed", { msg: error }) : !data ? error : null} />
      {!data ? (
        !error && <Loading />
      ) : (
        <>
          <section className="stats">
            {COMPARTMENTS.map((c) => {
              const p = data.compartments[c];
              return (
                <Stat key={c} tone={TONE[p.status.tone]} icon={c === "organic" ? Leaf : Package}
                  label={t("dash.compartment", { cat: t(`cat.${c}`), comp: t(`catLower.${c}`) })}
                  value={fmt.level(p.level)}
                  sub={<>
                    <StatusPill status={p.status} />{" "}
                    {p.hours_to_full ? t("dash.fullIn", { d: fmt.duration(p.hours_to_full) }) : ""}
                  </>} />
              );
            })}
            <Stat tone="purple" icon={Recycle} label={t("dash.itemsToday")} value={data.today.total}
              sub={t("dash.itemsTodaySub", { o: data.today.organic, i: data.today.inorganic, u: data.today.uncertain })} />
            <Stat tone={latest?.gas_ppm >= data.bin.gas_threshold_ppm ? "red" : "blue"} icon={Wind}
              label={t("dash.airQuality")}
              value={latest?.gas_ppm != null ? `${Math.round(latest.gas_ppm)} ppm` : "—"}
              sub={latest ? t("dash.climate", { temp: latest.temperature ?? "—", hum: latest.humidity ?? "—" }) : t("dash.noSensor")} />
          </section>

          <section className="grid">
            <div className="area-camera"><CameraCard detection={data.last_detection} /></div>
            <div className="area-bins"><Compartments compartments={data.compartments} bin={data.bin} /></div>
            <div className="area-recs">
              <Card title={t("dash.recommendations")} extra={<Link to="/alerts" className="link">{t("common.allAlerts")}</Link>}>
                <Recommendations items={data.recommendations} binId={bin.id} onDone={reload} />
              </Card>
            </div>
            <div className="area-trend">
              <Card title={t("dash.trend")} extra={<span className="muted-title">{t("common.last24h")}</span>}>
                <TrendChart points={data.trend} fullLevel={data.bin.full_level} height={250} />
              </Card>
            </div>
            <div className="area-activity">
              <Card title={t("dash.activity")} extra={<Link to="/detections" className="link">{t("common.seeAll")}</Link>}>
                <ActivityList items={data.recent_detections} />
              </Card>
            </div>
            <div className="area-system">
              <Card title={t("dash.systemInfo")}>
                <ul className="sysinfo">
                  <li><span>{t("dash.mode")}</span><strong>{t(`mode.${data.bin.mode}`)}</strong></li>
                  <li><span>{t("dash.lid")}</span><strong>{t(data.bin.lid_open ? "common.open" : "common.closed")}</strong></li>
                  <li><span>{t("dash.aiModel")}</span><strong>{data.bin.model_version || "—"}</strong></li>
                  <li><span>{t("dash.avgConfidence")}</span><strong>{fmt.pct(data.today.avg_confidence)}</strong></li>
                  <li><span>{t("dash.controller")}</span><strong>{data.bin.ip_main || "—"} · fw {data.bin.firmware_main || "—"}</strong></li>
                  <li><span>{t("dash.camera")}</span><strong>{data.bin.ip_cam || "—"} · fw {data.bin.firmware_cam || "—"}</strong></li>
                  <li><span>{t("dash.wifi")}</span><strong>{data.bin.wifi_rssi ? `${data.bin.wifi_rssi} dBm` : "—"}</strong></li>
                  <li><span>{t("dash.uptime")}</span><strong>{fmt.uptime(data.uptime_seconds)}</strong></li>
                </ul>
              </Card>
            </div>
          </section>
        </>
      )}
    </>
  );
}
