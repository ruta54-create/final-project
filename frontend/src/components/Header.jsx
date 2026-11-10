import { useEffect, useState } from "react";
import { CalendarDays, Camera, Cpu } from "lucide-react";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";

export default function Header({ title, subtitle, children }) {
  const { bins, bin, setBinId } = useBin();
  const { t, fmt } = useI18n();
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="header-meta">
        {children}
        {bins?.length > 1 && (
          <select className="bin-select" value={bin?.id} onChange={(e) => setBinId(Number(e.target.value))}>
            {bins.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        )}
        {bin && (
          <>
            <span className={`conn ${bin.is_online ? "on" : "off"}`} title="ESP32">
              <Cpu size={17} /> {t(bin.is_online ? "common.controllerOnline" : "common.controllerOffline")}
            </span>
            <span className={`conn ${bin.cam_online ? "on" : "off"}`} title="ESP32-CAM">
              <Camera size={17} /> {t(bin.cam_online ? "common.cameraOnline" : "common.cameraOffline")}
            </span>
          </>
        )}
        <span className="clock">
          <CalendarDays size={17} />
          {fmt.longDate(now)} {fmt.time(now)}
        </span>
      </div>
    </header>
  );
}
