import { useState } from 'react';
import { Button, Form } from 'react-bootstrap';
import { CheckCircle2, Flag } from 'lucide-react';
import { FormField, FormModal, Panel, StatusPill } from './ui';
import { markTreatmentReviewed } from '../api/clinician';
import { useToast } from '../context/ToastContext';
import { useSubmit } from '../hooks/useSubmit';
import { formatDateTime, formatDayMonth } from '../utils/format';
import { formatDailyAverage } from '../utils/chart';

const NOTE_LIMIT = 500;

/** Four weekly averages, oldest first, so the clinician sees the shape and not just a verdict. */
function WeekStrip({ weeks }) {
  return (
    <div className="hs-review-weeks" aria-label="Weekly average blood pressure">
      {weeks.map((week) => (
        <div key={week.start} className="hs-review-week">
          <div className="hs-reading-meta">{formatDayMonth(week.start)} – {formatDayMonth(week.end)}</div>
          <div className="hs-review-week-value">
            {week.avg_systolic == null ? '—' : `${formatDailyAverage(week.avg_systolic)}/${formatDailyAverage(week.avg_diastolic)}`}
          </div>
          <StatusPill status={week.status} size="sm" />
          <div className="hs-reading-meta">
            {week.status === 'no_data' ? `${week.reading_count} readings: too few` : `${week.reading_count} readings`}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReviewHistory({ reviews }) {
  if (!reviews.length) return null;
  return (
    <div className="hs-review-history">
      <div className="hs-form-label">Earlier reviews</div>
      {reviews.map((record) => (
        <div key={record.review_id} className="hs-reading-meta">
          {formatDateTime(record.reviewed_at)} · {record.clinician_name ?? 'a clinician'}
          {record.note ? `: ${record.note}` : ''}
        </div>
      ))}
    </div>
  );
}

/**
 * Clinician-only. Shows whether this patient is flagged for a treatment
 * review, why, and what to confirm first. It never suggests a drug or dose.
 */
export default function TreatmentReviewPanel({ patientId, review, onChanged }) {
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [note, setNote] = useState('');
  const { flagged, active } = review;

  const { submit, submitting, error, setError } = useSubmit(
    async () => {
      await markTreatmentReviewed(patientId, note);
      toast.success(
        flagged
          ? 'Review recorded. The matching flag is paused for 28 days.'
          : 'Review recorded. No current flag was paused.'
      );
      close();
      onChanged();
    },
    { fallback: 'Could not record the review.' },
  );

  function close() {
    setAsking(false);
    setNote('');
    setError('');
  }

  const state = !flagged ? 'none' : active ? review.level : 'paused';
  const reviewedBy = review.recent_reviews.find((record) => record.flag_kind === review.kind);

  return (
    <>
      <Panel
        title="Treatment review"
        className={`mb-4 hs-review-panel is-${state}`}
        description={
          !flagged
            ? 'Not flagged. The recent pattern does not meet the review criteria, or there are too few recent readings to say.'
            : undefined
        }
        action={
          flagged && active ? (
            <Button size="sm" className="btn-hs-primary" onClick={() => setAsking(true)}>
              <CheckCircle2 size={15} aria-hidden="true" /> Mark as reviewed
            </Button>
          ) : (
            !flagged && (
              <Button size="sm" variant="outline-secondary" onClick={() => setAsking(true)}>
                Record a review
              </Button>
            )
          )
        }
      >
        {flagged && (
          <>
            <p className="hs-review-headline">
              <Flag size={15} aria-hidden="true" />{' '}
              {review.level === 'priority' && active && <strong>Priority. </strong>}
              {review.headline}
            </p>

            {!active && review.last_reviewed_at && (
              <p className="hs-subtitle">
                Reviewed {formatDateTime(review.last_reviewed_at)} by {reviewedBy?.clinician_name ?? 'a clinician'}
                {reviewedBy?.note ? `: ${reviewedBy.note}` : ''}. The matching flag is paused until{' '}
                {formatDateTime(review.snoozed_until)} and returns if the same pattern remains active.
              </p>
            )}

            <div className="hs-form-label">Confirm first</div>
            <ul className="hs-review-list">
              {review.confirm_first.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </>
        )}

        <WeekStrip weeks={review.weeks} />
        <ReviewHistory reviews={review.recent_reviews} />
        <p className="hs-reading-meta mb-0 mt-3">{review.disclaimer}</p>
      </Panel>

      <FormModal
        show={asking}
        title="Record a treatment review"
        description={
          flagged
            ? 'Notes that you reviewed this patient. A matching flag is paused for a 28-day follow-up window; whether that window is suitable is a clinical judgement. Keep prescribing details in the clinic’s own records.'
            : 'Notes that you reviewed this patient. This review does not pause a future flag. Keep prescribing details in the clinic’s own records.'
        }
        error={error}
        submitLabel="Record review"
        submittingLabel="Saving…"
        submitting={submitting}
        onSubmit={submit}
        onHide={close}
      >
        <FormField
          id="review-note"
          label="Note (optional)"
          className="mb-0"
          hint={`${note.length}/${NOTE_LIMIT}`}
        >
          <Form.Control
            as="textarea"
            rows={3}
            maxLength={NOTE_LIMIT}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="e.g. Discussed with patient; recheck in 4 weeks"
          />
        </FormField>
      </FormModal>
    </>
  );
}
