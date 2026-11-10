import { Languages } from "lucide-react";
import { LANGUAGES, useI18n } from "../i18n/index.jsx";

/** EN | FR | RW toggle. The choice is saved in the browser and applied instantly. */
export default function LanguageSwitcher({ variant = "dark" }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div className={`lang-switch ${variant}`} role="group" aria-label={t("lang.label")}>
      <Languages size={16} aria-hidden="true" />
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          lang={l.code}
          title={l.name}
          aria-pressed={lang === l.code}
          className={lang === l.code ? "active" : ""}
          onClick={() => setLang(l.code)}
        >
          {l.short}
        </button>
      ))}
    </div>
  );
}
