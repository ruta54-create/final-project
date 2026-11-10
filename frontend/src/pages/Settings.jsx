import { useEffect, useState } from "react";
import { Copy, KeyRound, RefreshCw } from "lucide-react";
import { api } from "../api.js";
import { useAuth, useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import { Card } from "../components/ui.jsx";
import EmailSettings from "../components/EmailSettings.jsx";

const FIELDS = [
  { name: "name" },
  { name: "location" },
  { name: "organic_depth_cm", type: "number" },
  { name: "inorganic_depth_cm", type: "number" },
  { name: "warning_level", type: "number" },
  { name: "full_level", type: "number" },
  { name: "gas_threshold_ppm", type: "number" },
  { name: "min_confidence", type: "number", step: "0.01" },
];

/** Same rules as the server, checked in the browser so the message is in the user's language. */
function validate(body) {
  if (!String(body.name || "").trim()) return "errors.nameRequired";
  if (!(body.warning_level > 0 && body.warning_level < body.full_level && body.full_level <= 100)) return "errors.levels";
  if (!(body.min_confidence >= 0 && body.min_confidence <= 1)) return "errors.confidence";
  if (!(body.organic_depth_cm >= 10 && body.inorganic_depth_cm >= 10)) return "errors.depth";
  return null;
}

/** msg = { ok: boolean, text: string } */
function Msg({ msg }) {
  if (!msg) return null;
  return <span className={msg.ok ? "ok" : "err"} role="status">{msg.text}</span>;
}

function BinForm({ bin, onSaved }) {
  const { t } = useI18n();
  const [form, setForm] = useState(bin);
  const [msg, setMsg] = useState(null);
  useEffect(() => setForm(bin), [bin.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e) {
    e.preventDefault();
    setMsg(null);
    const body = Object.fromEntries(FIELDS.map((f) => [f.name, f.type === "number" ? Number(form[f.name]) : form[f.name]]));
    const problem = validate(body);
    if (problem) return setMsg({ ok: false, text: t("common.error", { msg: t(problem) }) });
    try {
      await api(`/bins/${bin.id}/`, { method: "PATCH", body });
      setMsg({ ok: true, text: t("set.saved") });
      onSaved();
    } catch (err) {
      setMsg({ ok: false, text: t("common.error", { msg: err.message }) });
    }
  }

  return (
    <form className="form" onSubmit={save} noValidate>
      <div className="form-grid">
        {FIELDS.map((f) => (
          <label key={f.name}>
            <span>{t(`set.field.${f.name}`)}</span>
            <input id={`bin-${f.name}`} name={f.name} type={f.type || "text"} step={f.step || "any"} value={form[f.name] ?? ""}
              onChange={(e) => setForm({ ...form, [f.name]: e.target.value })} />
          </label>
        ))}
      </div>
      <div className="form-actions">
        <button className="btn">{t("set.save")}</button>
        <Msg msg={msg} />
      </div>
    </form>
  );
}

function ApiKey({ bin, onChanged }) {
  const { t } = useI18n();
  const [show, setShow] = useState(false);
  const [msg, setMsg] = useState(null);

  async function regenerate() {
    if (!window.confirm(t("set.confirmNewKey"))) return;
    try {
      await api(`/bins/${bin.id}/regenerate-key/`, { method: "POST" });
      setMsg({ ok: true, text: t("set.newKeyDone") });
      onChanged();
    } catch (e) {
      setMsg({ ok: false, text: t("common.error", { msg: e.message }) });
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(bin.api_key);
      setMsg({ ok: true, text: t("set.copied") });
    } catch {
      setMsg({ ok: false, text: t("set.copyFailed") });
    }
  }

  return (
    <>
      <p className="muted small-text">{t("set.apiKeyNote")}</p>
      <div className="key-row">
        <KeyRound size={18} />
        <code className="key">{show ? bin.api_key : "•".repeat(24)}</code>
        <button type="button" className="btn-outline small" data-role="show-key" onClick={() => setShow(!show)}>{t(show ? "set.hide" : "set.show")}</button>
        <button type="button" className="btn-outline small" onClick={copy}><Copy size={14} /> {t("set.copy")}</button>
        <button type="button" className="btn-outline small danger" onClick={regenerate}><RefreshCw size={14} /> {t("set.newKey")}</button>
      </div>
      <Msg msg={msg} />
    </>
  );
}

function AddBin({ onCreated }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ name: "", location: "" });
  const [msg, setMsg] = useState(null);
  async function create(e) {
    e.preventDefault();
    if (!form.name.trim()) return setMsg({ ok: false, text: t("errors.nameRequired") });
    try {
      const b = await api("/bins/", { method: "POST", body: form });
      setMsg({ ok: true, text: t("set.created", { name: b.name }) });
      setForm({ name: "", location: "" });
      onCreated(b.id);
    } catch (err) {
      setMsg({ ok: false, text: t("common.error", { msg: err.message }) });
    }
  }
  return (
    <form className="form" onSubmit={create} noValidate>
      <div className="form-grid">
        <label><span>{t("set.name")}</span><input id="new-bin-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label><span>{t("set.location")}</span><input id="new-bin-location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></label>
      </div>
      <div className="form-actions"><button className="btn" data-role="add-bin">{t("set.addBinButton")}</button><Msg msg={msg} /></div>
    </form>
  );
}

function ChangePassword() {
  const { t } = useI18n();
  const [form, setForm] = useState({ old_password: "", new_password: "", confirm: "" });
  const [msg, setMsg] = useState(null);
  async function save(e) {
    e.preventDefault();
    if (form.new_password.length < 8) return setMsg({ ok: false, text: t("errors.too_short") });
    if (form.new_password !== form.confirm) return setMsg({ ok: false, text: t("set.passwordsDiffer") });
    try {
      await api("/auth/change-password/", { method: "POST", body: form });
      setMsg({ ok: true, text: t("set.passwordChanged") });
      setForm({ old_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setMsg({ ok: false, text: err.code ? t(`errors.${err.code}`) : t("common.error", { msg: err.message }) });
    }
  }
  return (
    <form className="form" onSubmit={save} noValidate>
      <div className="form-grid three">
        <label><span>{t("set.currentPassword")}</span><input id="old-password" type="password" autoComplete="current-password" value={form.old_password} onChange={(e) => setForm({ ...form, old_password: e.target.value })} /></label>
        <label><span>{t("set.newPassword")}</span><input id="new-password" type="password" autoComplete="new-password" value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} /></label>
        <label><span>{t("set.repeatPassword")}</span><input id="repeat-password" type="password" autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} /></label>
      </div>
      <div className="form-actions"><button className="btn" data-role="change-password">{t("set.changePassword")}</button><Msg msg={msg} /></div>
    </form>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { bin, reloadBins, setBinId } = useBin();
  const { t } = useI18n();

  return (
    <>
      <Header title={t("set.title")} subtitle={t("set.subtitle")} />
      {bin && user.is_staff && (
        <>
          <Card title={t("set.binSettings", { name: bin.name })}><BinForm bin={bin} onSaved={reloadBins} /></Card>
          <Card title={t("set.apiKey")}><ApiKey bin={bin} onChanged={reloadBins} /></Card>
        </>
      )}
      {bin && !user.is_staff && <div className="note">{t("set.viewerOnly")}</div>}
      {user.is_staff && (
        <Card title={t("set.addBin")}><AddBin onCreated={(id) => { reloadBins(); setBinId(id); }} /></Card>
      )}
      <EmailSettings />
      <Card title={t("set.account")}><ChangePassword /></Card>
      {user.is_staff && (
        <p className="muted small-text">
          {t("set.manageUsers")} <a href="/admin/" target="_blank" rel="noreferrer">{t("set.adminPanel")}</a>.
        </p>
      )}
    </>
  );
}
