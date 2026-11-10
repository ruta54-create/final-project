/*
 * Internationalisation (i18n) for the dashboard: English, Français, Kinyarwanda.
 *
 *   const { t, lang, setLang, fmt } = useI18n();
 *   t("nav.dashboard")                       -> "Dashboard" / "Tableau de bord" / "Ikibaho"
 *   t("dash.fullIn", { d: fmt.duration(8) }) -> "full in ~8 h"
 *   fmt.dateTime(iso), fmt.time(iso), fmt.ago(iso), fmt.duration(hours), fmt.when(iso)
 *
 * The server sends language-neutral codes (status, recommendation, alert kind...) and the
 * dashboard translates them here. To add a language: copy locales/en.js, translate it,
 * and add it to LANGUAGES below. `node tools/check_i18n.mjs` verifies no key is missing.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import en from "./locales/en.js";
import fr from "./locales/fr.js";
import rw from "./locales/rw.js";

export const LANGUAGES = [
  { code: "en", name: "English", short: "EN" },
  { code: "fr", name: "Français", short: "FR" },
  { code: "rw", name: "Kinyarwanda", short: "RW" },
];
const DICTS = { en, fr, rw };
const STORAGE_KEY = "smartbin.lang";

// Browsers have little or no Kinyarwanda date data, so its names are defined here.
const RW_MONTHS = ["Mutarama", "Gashyantare", "Werurwe", "Mata", "Gicurasi", "Kamena",
  "Nyakanga", "Kanama", "Nzeri", "Ukwakira", "Ugushyingo", "Ukuboza"];
const RW_MONTHS_SHORT = ["Mut", "Gas", "Wer", "Mat", "Gic", "Kam", "Nya", "Kan", "Nze", "Ukw", "Ugu", "Uku"];
const RW_DAYS = ["Ku cyumweru", "Kuwa mbere", "Kuwa kabiri", "Kuwa gatatu", "Kuwa kane", "Kuwa gatanu", "Kuwa gatandatu"];
const INTL_LOCALE = { en: "en-GB", fr: "fr-FR" };

function lookup(dict, key) {
  return key.split(".").reduce((node, part) => (node == null ? undefined : node[part]), dict);
}

function interpolate(text, params) {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (m, name) => (params[name] ?? params[name] === 0 ? String(params[name]) : m));
}

function initialLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && DICTS[saved]) return saved;
  } catch {
    /* storage blocked: fall through */
  }
  const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
  return DICTS[browser] ? browser : "en";
}

export function makeI18n(lang) {
  const dict = DICTS[lang] || en;

  /** Translate a key. `{name}` placeholders are filled from params.
   *  If params.count is given, "key_one" is used when count === 1 (if it exists). */
  function t(key, params) {
    let text;
    if (params && params.count === 1) text = lookup(dict, `${key}_one`) ?? lookup(en, `${key}_one`);
    if (text === undefined) text = lookup(dict, key);
    if (text === undefined) {
      text = lookup(en, key);
      if (import.meta.env.DEV) console.warn(`[i18n] missing "${key}" in ${lang}`);
    }
    if (text === undefined) return key;
    return typeof text === "string" ? interpolate(text, params) : text;
  }

  /** Translate a code from the server, e.g. tc("status", "almost_full"), falling back to `fallback`. */
  function tc(group, code, params, fallback) {
    const text = lookup(dict, `${group}.${code}`) ?? lookup(en, `${group}.${code}`);
    return text === undefined ? fallback ?? code : interpolate(text, params);
  }

  const pad = (n) => String(n).padStart(2, "0");
  const toDate = (v) => (v instanceof Date ? v : new Date(v));

  const fmt = {
    time(iso) {
      if (!iso) return "—";
      const d = toDate(iso);
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },
    /** "9 Nov, 14:06" / "9 nov., 14:06" / "9 Ugu, 14:06" */
    dateTime(iso) {
      if (!iso) return "—";
      const d = toDate(iso);
      const month = lang === "rw"
        ? RW_MONTHS_SHORT[d.getMonth()]
        : d.toLocaleString(INTL_LOCALE[lang], { month: "short" });
      return `${d.getDate()} ${month}, ${fmt.time(d)}`;
    },
    /** long date for the header clock: "9 November 2026" */
    longDate(value) {
      const d = toDate(value);
      if (lang === "rw") return `${d.getDate()} ${RW_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
      return d.toLocaleDateString(INTL_LOCALE[lang], { day: "numeric", month: "short", year: "numeric" });
    },
    shortDay(isoDate) { // "2026-11-05" -> "5 Nov"
      const [y, m, day] = isoDate.split("-").map(Number);
      return fmt.dateTime(new Date(y, m - 1, day)).split(",")[0];
    },
    weekday(d) {
      return lang === "rw" ? RW_DAYS[d.getDay()] : d.toLocaleDateString(INTL_LOCALE[lang], { weekday: "long" });
    },
    /** "today at 14:00" / "tomorrow at 04:30" / "Thursday at 09:00" */
    when(iso) {
      const d = toDate(iso);
      const today = new Date();
      const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
      const time = fmt.time(d);
      if (d.toDateString() === today.toDateString()) return t("time.todayAt", { time });
      if (d.toDateString() === tomorrow.toDateString()) return t("time.tomorrowAt", { time });
      return t("time.dayAt", { day: fmt.weekday(d), time });
    },
    ago(iso) {
      if (!iso) return t("time.never");
      const s = Math.max(0, Math.round((Date.now() - toDate(iso)) / 1000));
      if (s < 60) return t("time.secondsAgo", { n: s });
      if (s < 3600) return t("time.minutesAgo", { n: Math.round(s / 60) });
      if (s < 86400) return t("time.hoursAgo", { n: Math.round(s / 3600), count: Math.round(s / 3600) });
      const days = Math.round(s / 86400);
      return t("time.daysAgo", { n: days, count: days });
    },
    duration(hours) {
      if (hours === null || hours === undefined) return "—";
      if (hours === 0) return t("time.fullNow");
      if (hours < 1) return t("time.minutes", { n: Math.max(1, Math.round(hours * 60)) });
      if (hours < 48) return t("time.hours", { n: Math.round(hours) });
      const days = Math.round(hours / 24);
      return t("time.days", { n: days, count: days });
    },
    uptime(sec) {
      if (sec === null || sec === undefined) return "—";
      const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
      return d ? t("time.uptimeDays", { d, h }) : t("time.uptimeHours", { h, m });
    },
    pct(v, digits = 0) {
      return v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;
    },
    level(v) {
      return v === null || v === undefined ? "—" : `${Math.round(v)}%`;
    },
  };

  /** Name of an AI label ("fruit_peel") in this language, or a readable fallback. */
  function itemLabel(code) {
    const text = lookup(dict, `items.${code}`) ?? lookup(en, `items.${code}`);
    return text ?? (code || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  }

  return { lang, t, tc, fmt, itemLabel };
}

const I18nCtx = createContext(makeI18n("en"));

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(initialLanguage);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo(() => {
    const setLang = (code) => {
      if (!DICTS[code]) return;
      setLangState(code);
      try {
        localStorage.setItem(STORAGE_KEY, code);
      } catch {
        /* private mode: the choice lasts for this visit only */
      }
    };
    return { ...makeI18n(lang), setLang };
  }, [lang]);

  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);
