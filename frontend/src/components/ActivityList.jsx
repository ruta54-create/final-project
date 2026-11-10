import { AlertTriangle, Leaf, Package } from "lucide-react";
import { CAT } from "../api.js";
import { useI18n } from "../i18n/index.jsx";

export default function ActivityList({ items }) {
  const { t, fmt, itemLabel } = useI18n();
  if (!items.length) return <p className="empty">{t("activity.none")}</p>;
  return (
    <ul className="activity">
      {items.map((d) => {
        const c = CAT[d.category];
        const Icon = d.category === "organic" ? Leaf : Package;
        return (
          <li key={d.id}>
            <span className="activity-icon" style={{ background: c.bg, color: c.color }}>
              <Icon size={22} />
            </span>
            <div className="activity-text">
              <strong>
                {itemLabel(d.label)} <span className="muted">→ {t(`cat.${d.sorted_to}`)}</span>
              </strong>
              <small>
                {t("activity.confidence", { pct: fmt.pct(d.confidence) })}
                {d.uncertain && (
                  <span className="uncertain">
                    <AlertTriangle size={12} /> {t("activity.uncertain")}
                  </span>
                )}
              </small>
            </div>
            <time>{fmt.time(d.created_at)}</time>
          </li>
        );
      })}
    </ul>
  );
}
