import { useEffect, useState } from "react";
import { AlertTriangle, Check, Download, Leaf, Package, Undo2 } from "lucide-react";
import { api, CAT } from "../api.js";
import { useAuth, useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import { Chips, ErrorBox, Loading } from "../components/ui.jsx";

const PAGE = 24;
const MATERIALS = ["organic", "paper", "plastic", "metal", "other"];

/** "Was the AI right?" - a person confirms or corrects the material ("teach the AI"). */
function Review({ d, onChange }) {
  const { t, itemLabel } = useI18n();
  const [busy, setBusy] = useState(false);

  async function send(true_label) {
    setBusy(true);
    try {
      onChange(await api(`/detections/${d.id}/review/`, { method: "POST", body: { true_label } }));
    } finally {
      setBusy(false);
    }
  }

  if (d.true_label) {
    return (
      <div className={`review done ${d.is_correct ? "ok" : "bad"}`}>
        <span>
          {d.is_correct ? <><Check size={14} /> {t("review.verified")}</> :
            t("review.actually", { material: itemLabel(d.true_label).toLowerCase() })}
          {!d.is_correct && <small> · {t(d.right_compartment ? "review.rightBin" : "review.wrongBin")}</small>}
        </span>
        <button type="button" className="link-btn" disabled={busy} onClick={() => send("")} title={t("review.undo")}>
          <Undo2 size={14} />
        </button>
      </div>
    );
  }
  return (
    <div className="review">
      <small className="muted">{t("review.question")}</small>
      <div className="review-buttons">
        <button type="button" className="chip ok-chip" disabled={busy} data-review="correct" onClick={() => send(d.label)}>
          <Check size={13} /> {t("review.correct")}
        </button>
        <small className="muted">{t("review.itWas")}</small>
        {MATERIALS.filter((m) => m !== d.label).map((m) => (
          <button key={m} type="button" className="chip" disabled={busy} data-review={m} onClick={() => send(m)}>
            {itemLabel(m)}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Detections() {
  const { bin } = useBin();
  const { user } = useAuth();
  const { t, fmt, itemLabel } = useI18n();
  const [filter, setFilter] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const filters = [
    { value: "", label: t("det.all") },
    { value: "organic", label: t("det.organic") },
    { value: "inorganic", label: t("det.inorganic") },
    { value: "uncertain", label: t("det.uncertainOnly") },
    { value: "toreview", label: t("review.toReview") },
    { value: "wrong", label: t("review.mistakes") },
  ];

  const query = (offset) => {
    const q = new URLSearchParams({ bin: bin.id, limit: PAGE, offset });
    if (filter === "uncertain") q.set("uncertain", "1");
    else if (filter === "toreview") q.set("reviewed", "0");
    else if (filter === "wrong") q.set("wrong", "1");
    else if (filter) q.set("category", filter);
    return `/detections/?${q}`;
  };

  async function load(offset = 0) {
    setLoading(true);
    try {
      const data = await api(query(offset));
      setItems((old) => (offset ? [...old, ...data.results] : data.results));
      setTotal(data.count);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, bin.id]);

  const replace = (updated) => setItems((list) => list.map((x) => (x.id === updated.id ? updated : x)));

  return (
    <>
      <Header title={t("det.title")} subtitle={t("det.subtitle")} />
      <div className="row-between">
        <Chips options={filters} value={filter} onChange={setFilter} />
        <span className="muted">{t("det.count", { n: total, count: total })}</span>
      </div>
      {user.is_staff && (
        <div className="note export-row">
          <span>{t("review.exportHint")}</span>
          <a className="btn-outline small" href={`/api/bins/${bin.id}/training-photos/`} data-role="export-photos">
            <Download size={14} /> {t("review.export")}
          </a>
        </div>
      )}
      <ErrorBox error={error} />
      <div className="gallery">
        {items.map((d) => {
          const c = CAT[d.category];
          const Icon = d.category === "organic" ? Leaf : Package;
          return (
            <article key={d.id} className="card shot" data-id={d.id}>
              <div className="shot-img" style={{ background: c.bg }}>
                {d.image_url ? <img src={d.image_url} alt={itemLabel(d.label)} loading="lazy" /> : <Icon size={48} color={c.color} />}
                {d.uncertain && <span className="shot-flag"><AlertTriangle size={13} /> {t("det.uncertain")}</span>}
              </div>
              <div className="shot-body">
                <strong>{itemLabel(d.label)}</strong>
                <span className="pill" data-cat={d.category} style={{ background: c.bg, color: c.text }}>
                  {t(`cat.${d.category}`)} · {fmt.pct(d.confidence)}
                </span>
                <small className="muted">
                  {t("det.sortedTo", { date: fmt.dateTime(d.created_at), comp: t(`catLower.${d.sorted_to}`), cat: t(`cat.${d.sorted_to}`) })}
                </small>
                <Review d={d} onChange={replace} />
              </div>
            </article>
          );
        })}
      </div>
      {loading && <Loading />}
      {!loading && !items.length && <p className="empty">{t("det.none")}</p>}
      {!loading && items.length < total && (
        <button className="btn-outline center" onClick={() => load(items.length)}>{t("common.loadMore")}</button>
      )}
    </>
  );
}
