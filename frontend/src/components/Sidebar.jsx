import { NavLink } from "react-router-dom";
import { Bell, Camera, Gamepad2, Home, LineChart, LogOut, Settings } from "lucide-react";
import { useAuth, useBin } from "../context.jsx";
import { usePolling } from "../api.js";
import { useI18n } from "../i18n/index.jsx";
import LanguageSwitcher from "./LanguageSwitcher.jsx";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { bin } = useBin();
  const { t, fmt } = useI18n();
  const { data: alerts } = usePolling(bin ? `/alerts/?active=1&bin=${bin.id}&limit=1` : null, 15000);
  const count = alerts?.count || 0;

  const links = [
    { to: "/", key: "dashboard", icon: Home },
    { to: "/detections", key: "detections", icon: Camera },
    { to: "/analytics", key: "analytics", icon: LineChart },
    { to: "/alerts", key: "alerts", icon: Bell, badge: count },
    { to: "/control", key: "control", icon: Gamepad2 },
    { to: "/settings", key: "settings", icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/logo.png" alt={t("app.name")} className="brand-logo" />
        <div className="brand-text">
          <span>Edge-AI</span>
          <span>Smart Dustbin</span>
        </div>
      </div>

      <nav className="nav">
        {links.map(({ to, key, icon: Icon, badge }) => (
          <NavLink key={to} to={to} end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon size={20} />
            <span>{t(`nav.${key}`)}</span>
            {badge > 0 && <span className="badge">{badge}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <LanguageSwitcher />
        {bin && (
          <div className="sys-status">
            <span className={`dot ${bin.is_online ? "on" : "off"}`} />
            <div>
              <div>{t(bin.is_online ? "common.systemOnline" : "common.systemOffline")}</div>
              <small>{t("common.lastUpdate", { ago: fmt.ago(bin.last_seen) })}</small>
            </div>
          </div>
        )}
        <div className="user-row">
          <div>
            <strong>{user.name}</strong>
            <small>{t(user.is_staff ? "role.admin" : "role.viewer")}</small>
          </div>
          <button className="icon-btn" title={t("common.logout")} aria-label={t("common.logout")} onClick={logout}>
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}
