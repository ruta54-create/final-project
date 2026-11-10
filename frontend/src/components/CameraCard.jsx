import { AlertTriangle, Camera, CheckCircle2, Leaf, Package } from "lucide-react";
import { CAT } from "../api.js";
import { useI18n } from "../i18n/index.jsx";
import { Card } from "./ui.jsx";

/** Last photo taken by the ESP32-CAM with the AI decision. */
export default function CameraCard({ detection }) {
  const { t, fmt, itemLabel } = useI18n();
  const d = detection;
  const Icon = d?.category === "organic" ? Leaf : Package;
  const to = d && { comp: t(`catLower.${d.sorted_to}`), cat: t(`cat.${d.sorted_to}`) };

  return (
    <Card title={t("camera.title")} extra={d && <small className="muted">{fmt.ago(d.created_at)}</small>}>
      <div className="camera-frame">
        {d?.image_url ? (
          <img src={d.image_url} alt={itemLabel(d.label)} />
        ) : (
          <div className="camera-empty">
            {d ? <Icon size={64} color={CAT[d.category].color} /> : <Camera size={48} />}
            <span>{t(d ? "camera.noPhoto" : "camera.noItem")}</span>
          </div>
        )}
        {d && (
          <span className="camera-tag" style={{ background: CAT[d.category].color }}>
            {itemLabel(d.label)} · {fmt.pct(d.confidence)}
          </span>
        )}
      </div>
      {d ? (
        <div className={`classified ${d.uncertain ? "warn" : d.sorted_to}`}>
          {d.uncertain ? <AlertTriangle size={26} /> : <CheckCircle2 size={26} />}
          <div>
            <strong>
              {t("camera.classifiedAs", { cat: t(`cat.${d.category}`) })}{" "}
              <span>{t("camera.confidence", { pct: fmt.pct(d.confidence) })}</span>
            </strong>
            <small>
              {t(d.uncertain ? "camera.uncertainSent" : "camera.tilted", to)}
              {d.inference_ms ? t("camera.aiTook", { ms: d.inference_ms }) : ""}
            </small>
          </div>
        </div>
      ) : (
        <div className="classified idle">{t("camera.waiting")}</div>
      )}
    </Card>
  );
}
