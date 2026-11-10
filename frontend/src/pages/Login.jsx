import { useState } from "react";
import { useAuth } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import { ErrorBox } from "../components/ui.jsx";
import LanguageSwitcher from "../components/LanguageSwitcher.jsx";

export default function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(form.username, form.password);
    } catch (err) {
      setError(err.code ? { code: err.code } : { text: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-lang"><LanguageSwitcher variant="dark" /></div>
      <form className="card login-card" onSubmit={submit}>
        <img src="/logo.png" alt={t("app.name")} className="login-logo" />
        <h1>{t("app.name")}</h1>
        <p className="muted">{t("app.tagline")}</p>
        <ErrorBox error={error && (error.code ? t(`errors.${error.code}`) : error.text)} />
        <label>
          <span>{t("login.username")}</span>
          <input id="username" autoFocus autoComplete="username" value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })} required />
        </label>
        <label>
          <span>{t("login.password")}</span>
          <input id="password" type="password" autoComplete="current-password" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        </label>
        <button className="btn wide" disabled={busy}>{t(busy ? "login.signingIn" : "login.signIn")}</button>
      </form>
    </div>
  );
}
