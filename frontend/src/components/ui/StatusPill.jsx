import { statusInfo } from '../../utils/bpStatus';

/**
 * Coloured status badge. Pass a BP status key ("high", "controlled", …)
 * or an explicit {bg, text, label} for non-BP badges such as user roles.
 */
export default function StatusPill({ status, label, colors, size = 'md', className = '' }) {
  const info = colors || statusInfo(status);
  return (
    <span className={`hs-pill hs-pill-${size} ${className}`.trim()} style={{ backgroundColor: info.bg, color: info.text }}>
      {label || info.label}
    </span>
  );
}
