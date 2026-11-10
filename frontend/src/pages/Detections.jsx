import { useEffect, useState } from "react";
import { AlertTriangle, Leaf, Package } from "lucide-react";
import { api, CAT } from "../api.js";
import { useBin } from "../context.jsx";
import { useI18n } from "../i18n/index.jsx";
import Header from "../components/Header.jsx";
import { Chips, ErrorBox, Loading } from "../components/ui.jsx";

const PAGE = 24;

export default function Detections() {
  const { bin } = useBin();
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
  ];

  const query = (offset) => {
    const q = new URLSearchParams({ bin: bin.id, limit: PAGE, offset });
    if (filter === "uncertain") q.set("uncertain", "1");
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
    const id = setInterval(() => load(0), 10000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, bin.id]);

  return (
    <>
      <Header title={t("det.title")} subtitle={t("det.subtitle")} />
      <div className="row-between">
        <Chips options={filters} value={filter} onChange={setFilter} />
        <span className="muted">{t("det.count", { n: total, count: total })}</span>
      </div>
      <ErrorBox error={error} />
      <div className="gallery">
        {items.map((d) => {
          const c = CAT[d.category];
          const Icon = d.category === "organic" ? Leaf : Package;
          return (
            <article key={d.id} className="card shot">
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
