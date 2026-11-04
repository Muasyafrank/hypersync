import { Info } from 'lucide-react';
import { measurementFlags } from '../utils/format';

/** A small note under a reading taken in a way that can make it read high. Renders nothing otherwise. */
export default function ReadingConditions({ reading }) {
  const flags = measurementFlags(reading);
  if (flags.length === 0) return null;
  return (
    <div className="hs-reading-flag">
      <Info size={13} aria-hidden="true" /> {flags.join(' · ')}
    </div>
  );
}
