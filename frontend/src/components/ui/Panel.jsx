/** White card with an optional heading, description and header action. */
export default function Panel({ title, description, action, children, className = '' }) {
  const hasHeader = title || description || action;
  return (
    <section className={`hs-panel ${className}`.trim()}>
      {hasHeader && (
        <div className="hs-panel-header">
          <div>
            {title && <h5 className="hs-title mb-1">{title}</h5>}
            {description && <p className="hs-subtitle hs-panel-description mb-0">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
