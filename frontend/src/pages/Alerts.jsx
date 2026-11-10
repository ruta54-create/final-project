import { useState } from "react";
import { api, usePolling } from "../api.js";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import Recommendations from "../components/Recommendations.jsx";
import { Card, Chips, ErrorBox, Loading, Pill } from "../components/ui.jsx";

const SEV = { critical: "danger", warning: "warning", info: "info" };

/** Alert text in the current language, built from kind + params (English message as fallback). */
function useAlertText() {
  const { t, fmt } = useI18n();
  return (a) => {
    const p = a.params || {};
    if (!Object.keys(p).length) return a.message; // alert created before translations existed
    return t(`alerts.msg.${a.kind}`, {
      ...p,
      since: p.since ? fmt.dateTime(p.since) : undefined,
      ratio: p.ratio !== undefined ? fmt.pct(p.ratio) : undefined,
    });
  };
}

export default function Alerts() {
  const { bin } = useBin();
  const { t, tc, fmt } = useI18n();
  const alertText = useAlertText();
  const [active, setActive] = useState("1");
  const alerts = usePolling(`/alerts/?bin=${bin.id}&active=${active}&limit=100`, 5000);
  const overview = usePolling(`/bins/${bin.id}/overview/`, 10000);
  const [error, setError] = useState("");

  async function resolve(id) {
    try {
      await api(`/alerts/${id}/resolve/`, { method: "POST" });
      alerts.reload();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <>
      <Header title={t("alerts.title")} subtitle={t("alerts.subtitle")} />
      <section className="grid-2">
        <Card title={t("alerts.recommendations")}>
          {overview.data ? (
            <Recommendations items={overview.data.recommendations} binId={bin.id}
              onDone={() => { overview.reload(); alerts.reload(); }} />
          ) : <Loading />}
        </Card>
        <Card title={t("alerts.alerts")} extra={
          <Chips value={active} onChange={setActive}
            options={[{ value: "1", label: t("alerts.active") }, { value: "0", label: t("alerts.resolved") }]} />}>
          <ErrorBox error={error || alerts.error} />
          {!alerts.data ? <Loading /> : !alerts.data.results.length ? (
            <p className="empty">{t(active === "1" ? "alerts.noneActive" : "alerts.noneResolved")}</p>
          ) : (
            <ul className="alert-list">
              {alerts.data.results.map((a) => (
                <li key={a.id}>
                  <Pill tone={SEV[a.severity]}>{tc("severity", a.severity)}</Pill>
                  <div>
                    <strong>{tc("alerts.kind", a.kind, null, a.kind_label)}</strong>
                    <p>{alertText(a)}</p>
                    <small className="muted">
                      {fmt.dateTime(a.created_at)}
                      {a.resolved_at ? t("alerts.resolvedAt", { date: fmt.dateTime(a.resolved_at) }) : ""}
                    </small>
                  </div>
                  {a.is_active && <button className="btn-outline small" onClick={() => resolve(a.id)}>{t("alerts.resolve")}</button>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </>
  );
}
