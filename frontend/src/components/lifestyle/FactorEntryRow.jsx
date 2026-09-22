import {
  Check, Cigarette, Coffee, Droplet, Footprints, Frown, Meh, Moon, Pill, Smile, Utensils, Wine, X,
} from 'lucide-react';
import { DataRow } from '../ui';
import { formatFullDate } from '../../utils/format';

const STRESS_ICONS = { low: Smile, moderate: Meh, high: Frown };
const INTAKE_LEVELS = { none: 0, low: 1, moderate: 2, high: 3 };

/** Three icons, filled up to the logged intake level. */
function IntakeDots({ level, icon: Icon, label }) {
  const filled = INTAKE_LEVELS[level];
  if (filled === undefined) return null;
  return (
    <span className="d-inline-flex align-items-center gap-1" title={`${label}: ${level}`}>
      {Array.from({ length: 3 }, (_, i) => (
        <Icon key={i} size={13} style={{ opacity: i < filled ? 1 : 0.25 }} />
      ))}
    </span>
  );
}

function YesNo({ value }) {
  return value
    ? <Check size={14} color="#16A34A" aria-label="Yes" />
    : <X size={14} color="#DC2626" aria-label="No" />;
}

/** One saved lifestyle entry in the history list. */
export default function FactorEntryRow({ entry, onDelete }) {
  const StressIcon = STRESS_ICONS[entry.stress_level];

  return (
    <DataRow
      trailing={
        <button
          type="button"
          className="hs-icon-action hs-icon-action-danger"
          onClick={onDelete}
          aria-label={`Delete entry from ${formatFullDate(entry.logged_date)}`}
        >
          <X size={18} />
        </button>
      }
    >
      <div className="hs-reading-value" style={{ fontSize: '0.9rem' }}>
        {formatFullDate(entry.logged_date)}
      </div>
      <div className="d-flex gap-3 mt-1 flex-wrap align-items-center hs-factor-tags">
        {StressIcon && <StressIcon size={16} aria-label={`${entry.stress_level} stress`} />}
        {entry.sleep_hours != null && <span className="d-flex align-items-center gap-1"><Moon size={14} />{entry.sleep_hours}h</span>}
        <IntakeDots level={entry.salt_intake} icon={Droplet} label="Salt" />
        <IntakeDots level={entry.caffeine_intake} icon={Coffee} label="Caffeine" />
        {entry.alcohol_consumed != null && <span className="d-flex align-items-center gap-1"><Wine size={14} /><YesNo value={entry.alcohol_consumed} /></span>}
        {entry.smoked != null && <span className="d-flex align-items-center gap-1"><Cigarette size={14} /><YesNo value={entry.smoked} /></span>}
        {entry.physical_activity_minutes != null && <span className="d-flex align-items-center gap-1"><Footprints size={14} />{entry.physical_activity_minutes}m</span>}
        {entry.diet_adherence != null && <span className="d-flex align-items-center gap-1"><Utensils size={14} /><YesNo value={entry.diet_adherence} /></span>}
        {entry.medication_taken != null && <span className="d-flex align-items-center gap-1"><Pill size={14} /><YesNo value={entry.medication_taken} /></span>}
      </div>
    </DataRow>
  );
}
