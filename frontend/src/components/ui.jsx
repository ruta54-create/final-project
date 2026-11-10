import { AlertTriangle, Loader2 } from "lucide-react";

export function Card({ title, extra, children, className = "" }) {
  return (
    <section className={`card panel ${className}`}>
      {(title || extra) && (
        <div className="panel-head">
          {title && <h2>{title}</h2>}
          {extra}
        </div>
      )}
      {children}
    </section>
  );
}

export function Loading({ full }) {
  return (
    <div className={full ? "loading full" : "loading"}>
      <Loader2 className="spin" size={28} />
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="card state">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div className="error-box">
      <AlertTriangle size={18} /> {error}
    </div>
  );
}

export function Pill({ tone = "muted", children }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Stat({ label, value, sub, tone = "blue", icon: Icon }) {
  return (
    <div className={`card stat tone-${tone}`}>
      {Icon && (
        <div className={`stat-icon ${tone}`}>
          <Icon size={24} />
        </div>
      )}
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <strong className="stat-value">{value}</strong>
        {sub && <span className="stat-sub">{sub}</span>}
      </div>
    </div>
  );
}

export function Chips({ options, value, onChange }) {
  return (
    <div className="toolbar">
      {options.map((o) => (
        <button key={o.value} className={`chip ${o.value === value ? "active" : ""}`} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
