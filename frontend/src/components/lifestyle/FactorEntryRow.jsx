import { X } from 'lucide-react';
import { DataRow } from '../ui';
import { formatFullDate } from '../../utils/format';

const LEVEL_LABELS = { none: 'None', low: 'Low', moderate: 'Moderate', high: 'High' };

/** "Stress: Moderate" — plain text, matching how the wizard now records it. */
function LevelTag({ label, level }) {
  if (!level) return null;
  return <span>{label}: {LEVEL_LABELS[level] ?? level}</span>;
}

function YesNoTag({ label, value }) {
  if (value == null) return null;
  return <span>{label}: {value ? 'Yes' : 'No'}</span>;
}

/** One saved lifestyle entry in the history list — plain text throughout. */
export default function FactorEntryRow({ entry, onDelete }) {
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
      <div className="hs-reading-value hs-reading-value-sm">
        {formatFullDate(entry.logged_date)}
      </div>
      <div className="d-flex gap-3 mt-1 flex-wrap align-items-center hs-factor-tags">
        <LevelTag label="Stress" level={entry.stress_level} />
        {entry.sleep_hours != null && <span>Sleep: {entry.sleep_hours}h</span>}
        <LevelTag label="Salt" level={entry.salt_intake} />
        <LevelTag label="Caffeine" level={entry.caffeine_intake} />
        <YesNoTag label="Alcohol" value={entry.alcohol_consumed} />
        <YesNoTag label="Smoked" value={entry.smoked} />
        {entry.physical_activity_minutes != null && <span>Activity: {entry.physical_activity_minutes} min</span>}
        <YesNoTag label="Diet followed" value={entry.diet_adherence} />
        <YesNoTag label="Meds taken" value={entry.medication_taken} />
      </div>
    </DataRow>
  );
}
