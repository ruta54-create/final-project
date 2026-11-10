import { CAT } from "../api.js";
import { useI18n } from "../i18n/index.jsx";
import { Card, Pill } from "./ui.jsx";

/** Translated status pill for a compartment ({code, label, tone} from the server). */
export function StatusPill({ status }) {
  const { tc } = useI18n();
  return <Pill tone={status.tone}>{tc("status", status.code, null, status.label)}</Pill>;
}

function Tank({ comp, p, bin }) {
  const { t, fmt } = useI18n();
  const c = CAT[comp];
  const level = p.level ?? 0;
  return (
    <div className="tank-wrap">
      <div className="tank" title={`${t(`cat.${comp}`)}: ${fmt.level(p.level)}`}>
        <div className="tank-mark" style={{ bottom: `${bin.full_level}%` }} />
        <div className="tank-mark warn" style={{ bottom: `${bin.warning_level}%` }} />
        <div className="tank-fill" style={{ height: `${Math.min(level, 100)}%`, background: c.color }} />
        <span className="tank-value">{fmt.level(p.level)}</span>
      </div>
      <strong style={{ color: c.text }}>{t(`cat.${comp}`)}</strong>
      <StatusPill status={p.status} />
      <small className="muted">
        {p.hours_to_full === 0
          ? t("comp.emptyNow")
          : p.hours_to_full
            ? t("comp.fullIn", { d: fmt.duration(p.hours_to_full) })
            : t("comp.notFilling")}
      </small>
      {p.rate_per_hour !== null && <small className="muted">{t("comp.rate", { r: p.rate_per_hour })}</small>}
    </div>
  );
}

/** Two-compartment bin with fill levels and predictions. */
export default function Compartments({ compartments, bin }) {
  const { t } = useI18n();
  return (
    <Card title={t("comp.title")}>
      <div className="tanks">
        <Tank comp="organic" p={compartments.organic} bin={bin} />
        <Tank comp="inorganic" p={compartments.inorganic} bin={bin} />
      </div>
      <p className="legend-note">
        <span className="line-sample warn" /> {t("comp.almostFullLine", { n: bin.warning_level })} &nbsp;
        <span className="line-sample" /> {t("comp.fullLine", { n: bin.full_level })}
      </p>
    </Card>
  );
}
