/** Placeholder shown when a list has no items yet. */
export default function EmptyState({ icon: Icon, iconColor = '#CBD5E1', title, message, action }) {
  return (
    <div className="hs-empty-state">
      {Icon && <Icon size={28} color={iconColor} className="mb-2" />}
      {title && <div className="hs-empty-state-title">{title}</div>}
      {message && <p className="hs-subtitle mb-0">{message}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
