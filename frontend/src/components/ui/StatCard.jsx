/** Single metric tile used across the dashboards. */
export default function StatCard({ label, icon: Icon, value, sub, valueColor, children }) {
  return (
    <div className="hs-stat-card">
      <div className="hs-stat-label">
        <span>{label}</span>
        {Icon && <Icon size={16} color="#94A3B8" aria-hidden="true" />}
      </div>
      {children ?? <div className="hs-stat-value" style={valueColor ? { color: valueColor } : undefined}>{value}</div>}
      {sub && <div className="hs-stat-sub">{sub}</div>}
    </div>
  );
}
