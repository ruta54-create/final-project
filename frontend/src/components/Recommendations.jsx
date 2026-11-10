import { useState } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { api } from "../api.js";
import { useAuth } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";

const ICON = { danger: AlertOctagon, warning: AlertTriangle, info: Info, success: CheckCircle2 };

/** Turn a recommendation from the server ({code, params}) into translated title + detail. */
export function useRecommendationText() {
  const { t, fmt } = useI18n();
  return (r) => {
    const p = r.params || {};
    const values = {
      ...p,
      comp: p.compartment ? t(`catLower.${p.compartment}`) : undefined,
      when: p.full_at ? fmt.when(p.full_at) : undefined,
      share: p.share !== undefined ? fmt.pct(p.share) : undefined,
    };
    const known = r.code && t(`rec.title.${r.code}`) !== `rec.title.${r.code}`;
    return known
      ? { title: t(`rec.title.${r.code}`, values), detail: t(`rec.detail.${r.code}`, values) }
      : { title: r.title, detail: r.detail }; // older server: English fallback
  };
}

/** List of recommendations, each with an optional one-click action. */
export default function Recommendations({ items, binId, onDone }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const text = useRecommendationText();
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);

  async function run(r, i) {
    setBusy(i);
    setMsg(null);
    try {
      if (r.action.type === "collect") {
        await api(`/bins/${binId}/collections/`, { method: "POST", body: { compartment: r.action.compartment } });
        setMsg({ ok: true, text: t("rec.recorded", { comp: t(`catLower.${r.action.compartment}`) }) });
      } else {
        await api(`/bins/${binId}/commands/`, { method: "POST", body: { action: r.action.action, payload: r.action.payload || {} } });
        setMsg({ ok: true, text: t("rec.commandSent") });
      }
      onDone?.();
    } catch (e) {
      setMsg({ ok: false, text: t("common.error", { msg: e.message }) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <ul className="recs">
        {items.map((r, i) => {
          const Icon = ICON[r.tone] || Info;
          const { title, detail } = text(r);
          const canRun = r.action && (r.action.type === "collect" || user.is_staff);
          return (
            <li key={`${r.code}-${i}`} className={`rec ${r.tone}`}>
              <Icon size={20} />
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
                {canRun && (
                  <button className="btn small" disabled={busy !== null} onClick={() => run(r, i)}>
                    {busy === i
                      ? t("common.working")
                      : r.action.type === "collect"
                        ? t("rec.markEmptied", { comp: t(`catLower.${r.action.compartment}`) })
                        : t("rec.switchTo", { mode: t(`mode.${r.action.payload?.mode}`) })}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {msg && <p className={msg.ok ? "ok" : "err"}>{msg.text}</p>}
    </>
  );
}
