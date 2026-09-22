/**
 * The repeated list-row layout: optional colour accent, a main block and
 * a trailing block. Renders as a button when `onClick` is supplied so the
 * row stays keyboard-accessible (the old version used a clickable div).
 */
export default function DataRow({ accent, onClick, align = 'center', children, trailing, className = '' }) {
  const interactive = typeof onClick === 'function';
  const Tag = interactive ? 'button' : 'div';

  return (
    <Tag
      type={interactive ? 'button' : undefined}
      onClick={onClick}
      className={`hs-reading-row ${interactive ? 'hs-reading-row-interactive' : ''} ${className}`.trim()}
      style={{ alignItems: align === 'start' ? 'flex-start' : 'center' }}
    >
      <div className="hs-reading-row-main" style={{ alignItems: align === 'start' ? 'flex-start' : 'center' }}>
        {accent && <span className="hs-reading-row-accent" style={{ backgroundColor: accent }} aria-hidden="true" />}
        <div className="flex-grow-1 text-start">{children}</div>
      </div>
      {trailing && <div className="hs-reading-row-trailing">{trailing}</div>}
    </Tag>
  );
}
