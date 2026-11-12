import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, ImageUp, Images, Leaf, Package, Send, XCircle } from "lucide-react";
import { apiUpload, CAT, usePolling } from "../api.js";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import { Card, Chips, ErrorBox, Loading, Pill } from "../components/ui.jsx";

const ORDER = ["organic", "paper", "plastic", "metal"];

/** Draw the centre square the AI actually looks at (same crop as the ESP32 camera). */
function aiView(blob, size) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(img.width, img.height);
      const c = document.createElement("canvas");
      c.width = c.height = size;
      c.getContext("2d").drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, size, size);
      URL.revokeObjectURL(img.src);
      resolve(c.toDataURL("image/jpeg", 0.9));
    };
    img.src = URL.createObjectURL(blob);
  });
}

function Webcam({ onPhoto }) {
  const { t } = useI18n();
  const video = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let stream;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(t("lab.camHttps"));
      return undefined;
    }
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      .then((s) => { stream = s; if (video.current) video.current.srcObject = s; })
      .catch(() => setError(t("lab.camDenied")));
    return () => stream?.getTracks().forEach((tr) => tr.stop());
  }, [t]);

  function snap() {
    const v = video.current;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => b && onPhoto(b, null), "image/jpeg", 0.92);
  }

  if (error) return <p className="err">{error}</p>;
  return (
    <div className="webcam">
      <div className="webcam-frame">
        <video ref={video} autoPlay playsInline muted />
        <div className="crop-guide" aria-hidden="true" />
      </div>
      <button type="button" className="btn" data-role="snap" onClick={snap}><Camera size={16} /> {t("lab.snap")}</button>
      <small className="muted">{t("lab.camHint")}</small>
    </div>
  );
}

export default function AiLab() {
  const { bin } = useBin();
  const { t, fmt, itemLabel } = useI18n();
  const status = usePolling("/ai/status/", 10000);
  const [mode, setMode] = useState("samples");
  const [samples, setSamples] = useState([]);
  const [photo, setPhoto] = useState(null);        // {blob, url, aiUrl, expected}
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(null);
  const [drag, setDrag] = useState(false);
  const info = status.data;
  const size = info?.online ? Number(String(info.input).split("x")[0]) : 128;

  useEffect(() => {
    fetch("/samples/samples.json").then((r) => r.json()).then(setSamples).catch(() => setSamples([]));
  }, []);

  async function classify(blob, expected) {
    setError("");
    setResult(null);
    setSaved(null);
    if (photo?.url) URL.revokeObjectURL(photo.url);
    setPhoto({ blob, url: URL.createObjectURL(blob), aiUrl: await aiView(blob, size), expected });
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", blob, "photo.jpg");
      fd.append("bin", bin.id);
      setResult(await apiUpload("/ai/classify/", fd));
    } catch (e) {
      setError(e.code ? t(`errors.${e.code}`) : e.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendToBin() {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", photo.blob, "photo.jpg");
      fd.append("bin", bin.id);
      fd.append("save", "1");
      const r = await apiUpload("/ai/classify/", fd);
      setSaved(r.saved);
    } catch (e) {
      setError(e.code ? t(`errors.${e.code}`) : e.message);
    } finally {
      setBusy(false);
    }
  }

  const pickFile = (file) => file && file.type.startsWith("image/") && classify(file, null);
  const loadSample = async (s) => classify(await (await fetch(`/samples/${s.file}`)).blob(), s.label);

  const modes = [
    { value: "samples", label: t("lab.samples") },
    { value: "upload", label: t("lab.upload") },
    { value: "webcam", label: t("lab.webcam") },
  ];
  const expectedOk = result && photo?.expected ? result.label === photo.expected : null;

  return (
    <>
      <Header title={t("lab.title")} subtitle={t("lab.subtitle")} />

      <Card title={t("lab.model")} extra={info && (
        <Pill tone={info.online ? "success" : "danger"}>{t(info.online ? "lab.online" : "lab.offline")}</Pill>)}>
        {!info ? <Loading /> : info.online ? (
          <ul className="sysinfo lab-info">
            <li><span>{t("lab.network")}</span><strong>{info.model}</strong></li>
            <li><span>{t("lab.input")}</span><strong>{info.input} · int8 · {info.size_kb} KB</strong></li>
            <li><span>{t("lab.classes")}</span><strong>{info.labels.map((l) => itemLabel(l)).join(", ")}</strong></li>
            <li><span>{t("lab.testAcc")}</span>
              <strong>{fmt.pct(info.test_accuracy, 1)} · {t("lab.rightBin")} {fmt.pct(info.test_compartment_accuracy, 1)} ({info.test_images})</strong></li>
          </ul>
        ) : <div className="note">{t("errors.ai_offline")}</div>}
        <p className="muted small-text">{t("lab.sameModel")}</p>
      </Card>

      <section className="grid-2 lab">
        <Card title={t("lab.photo")} extra={<Chips options={modes} value={mode} onChange={setMode} />}>
          {mode === "samples" && (
            <>
              <div className="samples">
                {samples.map((s) => (
                  <button key={s.file} type="button" className="sample" data-sample={s.file} disabled={busy}
                    onClick={() => loadSample(s)} title={`${itemLabel(s.label)} · ${s.source}`}>
                    <img src={`/samples/${s.file}`} alt={itemLabel(s.label)} />
                    <span>{itemLabel(s.label)}</span>
                  </button>
                ))}
              </div>
              <small className="muted">{t("lab.samplesNote")}</small>
            </>
          )}
          {mode === "upload" && (
            <label className={`dropzone ${drag ? "over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); pickFile(e.dataTransfer.files[0]); }}>
              <ImageUp size={34} />
              <strong>{t("lab.drop")}</strong>
              <small className="muted">{t("lab.dropHint")}</small>
              <input id="lab-file" type="file" accept="image/*" capture="environment" hidden
                onChange={(e) => { pickFile(e.target.files[0]); e.target.value = ""; }} />
            </label>
          )}
          {mode === "webcam" && <Webcam onPhoto={classify} />}
          <p className="muted small-text">{t("lab.tips")}</p>
        </Card>

        <Card title={t("lab.result")}>
          <ErrorBox error={error} />
          {!photo && !error && <p className="empty"><Images size={18} /> {t("lab.empty")}</p>}
          {photo && (
            <div className="lab-images">
              <figure><img src={photo.url} alt="" /><figcaption>{t("lab.yourPhoto")}</figcaption></figure>
              <figure><img src={photo.aiUrl} alt="" className="ai-view" />
                <figcaption>{t("lab.aiSees", { size })}</figcaption></figure>
            </div>
          )}
          {busy && !result && <Loading />}
          {result && (
            <>
              <ul className="scores">
                {ORDER.filter((l) => l in result.scores).map((l) => (
                  <li key={l} className={l === result.label ? "best" : ""}>
                    <span>{itemLabel(l)}</span>
                    <div className="progress"><div className="progress-bar"
                      style={{ width: `${result.scores[l] * 100}%`, background: CAT[l === "organic" || l === "paper" ? "organic" : "inorganic"].color }} /></div>
                    <strong>{fmt.pct(result.scores[l])}</strong>
                  </li>
                ))}
              </ul>
              <div className={`classified ${result.uncertain ? "warn" : result.sorted_to}`} data-role="decision">
                {result.uncertain ? <AlertTriangle size={26} /> : result.sorted_to === "organic" ? <Leaf size={26} /> : <Package size={26} />}
                <div>
                  <strong>{t("lab.decision", { material: itemLabel(result.label), pct: fmt.pct(result.confidence) })}</strong>
                  <small>
                    {result.uncertain
                      ? t("lab.unsure", { min: fmt.pct(result.min_confidence) })
                      : t("lab.goesTo", { comp: t(`catLower.${result.sorted_to}`) })}
                    {t("lab.time", { ms: result.inference_ms })}
                  </small>
                </div>
              </div>
              {expectedOk !== null && (
                <p className={expectedOk ? "ok" : "err"}>
                  {expectedOk ? <CheckCircle2 size={15} /> : <XCircle size={15} />}{" "}
                  {t(expectedOk ? "lab.expectedOk" : "lab.expectedBad", { material: itemLabel(photo.expected) })}
                </p>
              )}
              <div className="form-actions">
                <button type="button" className="btn-outline" data-role="send-to-bin" disabled={busy || !!saved} onClick={sendToBin}>
                  <Send size={15} /> {t("lab.send")}
                </button>
                {saved && <span className="ok">{t("lab.sent", { name: bin.name })}</span>}
              </div>
            </>
          )}
        </Card>
      </section>
    </>
  );
}
