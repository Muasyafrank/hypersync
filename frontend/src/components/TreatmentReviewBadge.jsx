import { Flag } from 'lucide-react';

const LABELS = { sustained_elevated_high: 'Review: high BP', sustained_low: 'Review: low BP' };

/** Small pill in the patient list for patients flagged for a clinician treatment review. */
export default function TreatmentReviewBadge({ review }) {
  if (!review) return null;
  return (
    <span className={`hs-review-badge is-${review.level}`} title="Flagged for a clinician treatment review">
      <Flag size={12} aria-hidden="true" /> {LABELS[review.kind] ?? 'Review'}
      {review.level === 'priority' && ' · priority'}
    </span>
  );
}
