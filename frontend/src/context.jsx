import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api.js";

/* ------------------------------------------------------------------ logged-in user */

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = still checking

  useEffect(() => {
    api("/auth/csrf/")
      .then(() => api("/auth/me/"))
      .then((me) => setUser(me.authenticated ? me : null))
      .catch(() => setUser(null));
    const expired = () => setUser(null);
    window.addEventListener("auth:expired", expired);
    return () => window.removeEventListener("auth:expired", expired);
  }, []);

  const login = async (username, password) => {
    await api("/auth/csrf/");
    setUser(await api("/auth/login/", { method: "POST", body: { username, password } }));
  };
  const logout = async () => {
    await api("/auth/logout/", { method: "POST" }).catch(() => {});
    setUser(null);
  };

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

/* ------------------------------------------------------------------ selected bin */

const BinCtx = createContext(null);
const KEY = "smartbin.selected";

export function BinProvider({ children }) {
  const [bins, setBins] = useState(null);
  const [binId, setBinIdState] = useState(() => {
    try {
      return Number(localStorage.getItem(KEY)) || null;
    } catch {
      return null;
    }
  });

  const reloadBins = useCallback(async () => {
    try {
      setBins(await api("/bins/"));
    } catch {
      setBins([]);
    }
  }, []);

  useEffect(() => {
    reloadBins();
    const id = setInterval(reloadBins, 15000);
    return () => clearInterval(id);
  }, [reloadBins]);

  const setBinId = (id) => {
    setBinIdState(id);
    try {
      localStorage.setItem(KEY, String(id));
    } catch {
      /* private mode: ignore */
    }
  };

  const bin = bins?.find((b) => b.id === binId) || bins?.[0] || null;
  return <BinCtx.Provider value={{ bins, bin, setBinId, reloadBins }}>{children}</BinCtx.Provider>;
}

export const useBin = () => useContext(BinCtx);
