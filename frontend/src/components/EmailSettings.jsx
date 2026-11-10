import { useEffect, useState } from "react";
import { Mail, Send } from "lucide-react";
import { api, usePolling } from "../api.js";
import { useBin } from "../context.jsx";
import { LANGUAGES, useI18n } from "../i18n/index.jsx";
import { Card, Loading, Pill } from "./ui.jsx";

const LEVELS = ["warning", "critical", "info"];
const STATUS_TONE = { pending: "muted", sent: "success", failed: "danger" };

/** Settings → Email notifications: address, on/off, language, which alerts, which bins, test + log. */
export default function EmailSettings() {
  const { t, fmt } = useI18n();
  const { bins } = useBin();
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const log = usePolling("/notifications/log/?limit=15", 10000);

  useEffect(() => {
    api("/notifications/settings/").then(setForm).catch((e) => setMsg({ ok: false, text: e.message }));
  }, []);

  const errorText = (e) => (e.code ? t(`errors.${e.code}`) : t("common.error", { msg: e.message }));

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    if (form.email_enabled && !form.email.trim()) return setMsg({ ok: false, text: t("errors.email_required") });
    try {
      setForm(await api("/notifications/settings/", { method: "PATCH", body: form }));
      setMsg({ ok: true, text: t("notif.saved") });
    } catch (err) {
      setMsg({ ok: false, text: errorText(err) });
    }
  }

  async function sendTest() {
    setMsg(null);
    setBusy(true);
    try {
      const r = await api("/notifications/test/", { method: "POST" });
      setMsg({ ok: true, text: t(r.delivery === "file" ? "notif.testSaved" : "notif.testSent", { to: r.to }) });
    } catch (err) {
      setMsg({ ok: false, text: err.status === 502 ? t("notif.testFailed", { error: err.message }) : errorText(err) });
    } finally {
      setBusy(false);
      log.reload();
    }
  }

  const toggleBin = (id) =>
    setForm((f) => ({ ...f, bins: f.bins.includes(id) ? f.bins.filter((b) => b !== id) : [...f.bins, id] }));

  if (!form) return <Card title={t("notif.title")}>{msg ? <p className="err">{msg.text}</p> : <Loading />}</Card>;

  return (
    <Card title={t("notif.title")} extra={<Mail size={20} className="muted" />}>
      <p className="muted small-text">{t("notif.intro")}</p>
      {form.delivery === "file" && <div className="note">{t("notif.deliveryFile")}</div>}

      <form className="form" onSubmit={save} noValidate>
        <label className="switch-row">
          <input id="notif-enabled" type="checkbox" checked={form.email_enabled}
            onChange={(e) => setForm({ ...form, email_enabled: e.target.checked })} />
          <span>{t("notif.enabled")}</span>
        </label>
        <div className="form-grid three">
          <label>
            <span>{t("notif.email")}</span>
            <input id="notif-email" type="email" autoComplete="email" placeholder="name@example.com" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label>
            <span>{t("notif.language")}</span>
            <select id="notif-language" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
            </select>
          </label>
          <label>
            <span>{t("notif.minSeverity")}</span>
            <select id="notif-level" value={form.min_severity} onChange={(e) => setForm({ ...form, min_severity: e.target.value })}>
              {LEVELS.map((l) => <option key={l} value={l}>{t(`notif.level.${l}`)}</option>)}
            </select>
          </label>
        </div>
        {bins?.length > 1 && (
          <fieldset className="bin-checks">
            <legend>{t("notif.bins")} <small className="muted">· {t("notif.binsHint")}</small></legend>
            {bins.map((b) => (
              <label key={b.id} className="switch-row">
                <input type="checkbox" checked={form.bins.includes(b.id)} onChange={() => toggleBin(b.id)} />
                <span>{b.name}</span>
              </label>
            ))}
          </fieldset>
        )}
        <div className="form-actions">
          <button className="btn" data-role="save-email">{t("notif.save")}</button>
          <button type="button" className="btn-outline" data-role="test-email" disabled={busy || !form.email} onClick={sendTest}>
            <Send size={15} /> {t(busy ? "common.working" : "notif.test")}
          </button>
          {msg && <span className={msg.ok ? "ok" : "err"} role="status">{msg.text}</span>}
        </div>
      </form>

      <h3 className="sub-title">{t("notif.log")}</h3>
      <div className="table-scroll short">
        <table className="table">
          <thead><tr><th>{t("ctl.time")}</th><th>{t("notif.to")}</th><th>{t("notif.subject")}</th><th>{t("ctl.status")}</th></tr></thead>
          <tbody>
            {log.data?.map((n) => (
              <tr key={n.id} data-status={n.status}>
                <td>{fmt.dateTime(n.created_at)}</td>
                <td>{n.to}</td>
                <td>{n.subject}{n.error && <small className="muted block">{n.error}</small>}</td>
                <td><Pill tone={STATUS_TONE[n.status]}>{t(`notif.status.${n.status}`)}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
        {log.data && !log.data.length && <p className="empty">{t("notif.logEmpty")}</p>}
      </div>
    </Card>
  );
}
