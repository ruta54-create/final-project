import { useCallback, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ HTTP */

function cookie(name) {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : "";
}

function errorText(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([k, v]) => `${k === "non_field_errors" ? "" : k + ": "}${[].concat(v).join(" ")}`)
    .join(" · ");
}

/** Call the Django API. Sends the session cookie + CSRF token automatically.
 *  Errors carry `.code` when the server sends one, so the UI can translate them. */
export async function api(path, { method = "GET", body } = {}) {
  const opts = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
  if (method !== "GET") opts.headers["X-CSRFToken"] = cookie("csrftoken");
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`/api${path}`, opts);
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 403 && /credentials were not provided/i.test(data?.detail || "")) {
      window.dispatchEvent(new Event("auth:expired"));
    }
    const err = new Error(errorText(data) || `${res.status} ${res.statusText}`);
    err.status = res.status;
    err.code = data?.code;
    throw err;
  }
  return data;
}

/** Fetch `path` now and every `ms` milliseconds (null path = paused). */
export function usePolling(path, ms = 5000) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const data = await api(path);
      if (alive.current) setState({ data, error: null, loading: false });
    } catch (e) {
      if (alive.current) setState((s) => ({ ...s, error: e.message, loading: false }));
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    setState((s) => ({ ...s, loading: true }));
    load();
    const id = ms ? setInterval(load, ms) : null;
    return () => {
      alive.current = false;
      if (id) clearInterval(id);
    };
  }, [load, ms]);

  return { ...state, reload: load };
}

/* ------------------------------------------------------------------ constants (text lives in src/i18n) */

export const COMPARTMENTS = ["organic", "inorganic"];

export const CAT = {
  organic: { color: "#16a34a", bg: "#dcfce7", text: "#166534" },
  inorganic: { color: "#2563eb", bg: "#dbeafe", text: "#1e40af" },
};

export const MODE_KEYS = ["auto", "manual", "maintenance"];
