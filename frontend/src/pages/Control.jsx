import { useState } from "react";
import {
  ArrowLeftCircle, ArrowRightCircle, BellRing, Camera, DoorClosed, DoorOpen, Leaf, Package, Power, Ruler,
} from "lucide-react";
import { api, CAT, COMPARTMENTS, MODE_KEYS, usePolling } from "../api.js";
import { useAuth, useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import { Card, ErrorBox, Loading, Pill } from "../components/ui.jsx";

const ACTIONS = [
  { action: "open_lid", icon: DoorOpen },
  { action: "close_lid", icon: DoorClosed },
  { action: "sort_organic", icon: ArrowLeftCircle },
  { action: "sort_inorganic", icon: ArrowRightCircle },
  { action: "capture", icon: Camera },
  { action: "buzzer", icon: BellRing },
  { action: "calibrate", icon: Ruler, confirm: "ctl.confirmCalibrate" },
  { action: "reboot", icon: Power, confirm: "ctl.confirmReboot" },
];

const STATUS_TONE = { pending: "muted", sent: "info", done: "success", failed: "danger", expired: "warning" };

export default function Control() {
  const { user } = useAuth();
  const { bin, reloadBins } = useBin();
  const { t, tc, fmt } = useI18n();
  const overview = usePolling(`/bins/${bin.id}/overview/`, 3000);
  const commands = usePolling(`/bins/${bin.id}/commands/`, 2000);
  const collections = usePolling(`/bins/${bin.id}/collections/`, 10000);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const staff = user.is_staff;

  /** Server messages have a code we translate; device messages are shown as sent. */
  const commandMessage = (c) => {
    if (!c.message_code) return c.message;
    const p = c.message_params || {};
    return t(`ctl.cmdMsg.${c.message_code}`, { ...p, comp: p.compartment ? t(`catLower.${p.compartment}`) : undefined });
  };

  async function send(action, payload = {}, confirmKey) {
    if (confirmKey && !window.confirm(t(confirmKey))) return;
    setError("");
    setMsg("");
    try {
      await api(`/bins/${bin.id}/commands/`, { method: "POST", body: { action, payload } });
      setMsg(t(bin.is_online ? "ctl.sentOnline" : "ctl.sentOffline"));
      commands.reload();
      if (action === "set_mode") { reloadBins(); overview.reload(); }
    } catch (e) {
      setError(e.message);
    }
  }

  async function emptied(compartment) {
    const comp = t(`catLower.${compartment}`);
    if (!window.confirm(t("ctl.confirmEmptied", { comp }))) return;
    try {
      await api(`/bins/${bin.id}/collections/`, { method: "POST", body: { compartment } });
      setMsg(t("ctl.recorded", { comp }));
      collections.reload();
      overview.reload();
    } catch (e) {
      setError(e.message);
    }
  }

  const o = overview.data;
  const onlinePill = (on) => <Pill tone={on ? "success" : "danger"}>{t(on ? "common.online" : "common.offline")}</Pill>;

  return (
    <>
      <Header title={t("ctl.title")} subtitle={t("ctl.subtitle")} />
      {!staff && <div className="note">{t("ctl.viewerNote")}</div>}
      <ErrorBox error={error} />
      {msg && <div className="note ok-note">{msg}</div>}

      <section className="grid-2">
        <Card title={t("ctl.mode")}>
          <div className="modes">
            {MODE_KEYS.map((key) => (
              <button key={key} disabled={!staff} data-mode={key}
                className={`mode-btn ${bin.mode === key ? "active" : ""}`}
                onClick={() => bin.mode !== key && send("set_mode", { mode: key })}>
                <strong>{t(`mode.${key}`)}</strong>
                <small>{t(`modeHint.${key}`)}</small>
              </button>
            ))}
          </div>
          {o ? (
            <ul className="sysinfo">
              <li><span>{t("ctl.controller")}</span><strong>{onlinePill(o.bin.is_online)}</strong></li>
              <li><span>{t("ctl.camera")}</span><strong>{onlinePill(o.bin.cam_online)}</strong></li>
              <li data-row="lid"><span>{t("ctl.lid")}</span><strong>{t(o.bin.lid_open ? "common.open" : "common.closed")}</strong></li>
              <li><span>{t("ctl.organicLevel")}</span><strong>{fmt.level(o.compartments.organic.level)}</strong></li>
              <li><span>{t("ctl.inorganicLevel")}</span><strong>{fmt.level(o.compartments.inorganic.level)}</strong></li>
              <li><span>{t("ctl.climate")}</span>
                <strong>{o.latest ? `${Math.round(o.latest.gas_ppm ?? 0)} ppm · ${o.latest.temperature ?? "—"} °C · ${o.latest.humidity ?? "—"}%` : "—"}</strong></li>
            </ul>
          ) : <Loading />}
        </Card>

        <Card title={t("ctl.commands")}>
          <div className="actions">
            {ACTIONS.map(({ action, icon: Icon, confirm }) => (
              <button key={action} data-action={action} className="action-btn" disabled={!staff}
                onClick={() => send(action, {}, confirm)}>
                <Icon size={22} />
                {t(`ctl.button.${action}`)}
              </button>
            ))}
          </div>
          <p className="muted small-text">{t("ctl.commandsNote")}</p>
        </Card>
      </section>

      <section className="grid-2">
        <Card title={t("ctl.collection")}>
          <div className="actions two">
            {COMPARTMENTS.map((c) => (
              <button key={c} data-emptied={c} className="action-btn big" style={{ borderColor: CAT[c].color, color: CAT[c].text }}
                onClick={() => emptied(c)}>
                {c === "organic" ? <Leaf size={26} /> : <Package size={26} />}
                {t("ctl.emptied", { cat: t(`cat.${c}`), comp: t(`catLower.${c}`) })}
              </button>
            ))}
          </div>
          <div className="table-scroll short">
            <table className="table">
              <thead><tr><th>{t("ctl.time")}</th><th>{t("ctl.compartment")}</th><th>{t("ctl.levelBefore")}</th><th>{t("ctl.by")}</th></tr></thead>
              <tbody>
                {collections.data?.map((c) => (
                  <tr key={c.id}>
                    <td>{fmt.dateTime(c.created_at)}</td>
                    <td>{t(`cat.${c.compartment}`)}</td>
                    <td>{fmt.level(c.level_before)}</td>
                    <td>{c.created_by || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title={t("ctl.log")}>
          <div className="table-scroll short command-log">
            <table className="table">
              <thead><tr><th>{t("ctl.time")}</th><th>{t("ctl.command")}</th><th>{t("ctl.status")}</th><th>{t("ctl.by")}</th></tr></thead>
              <tbody>
                {commands.data?.map((c) => (
                  <tr key={c.id} data-action={c.action} data-status={c.status}>
                    <td>{fmt.dateTime(c.created_at)}</td>
                    <td>
                      {tc("ctl.action", c.action, null, c.action_label)}
                      {c.payload?.mode ? ` (${t(`mode.${c.payload.mode}`)})` : ""}
                      {(c.message || c.message_code) && <small className="muted block">{commandMessage(c)}</small>}
                    </td>
                    <td><Pill tone={STATUS_TONE[c.status]}>{tc("ctl.cmdStatus", c.status)}</Pill></td>
                    <td>{c.created_by || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {commands.data && !commands.data.length && <p className="empty">{t("ctl.noCommands")}</p>}
          </div>
        </Card>
      </section>
    </>
  );
}
