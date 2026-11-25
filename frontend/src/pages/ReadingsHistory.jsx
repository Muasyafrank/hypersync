import { useRef, useState } from 'react';
import { Alert, Button, Container } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Calendar, HeartPulse, Plus, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import ReadingConditions from '../components/ReadingConditions';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useRecommendations } from '../context/RecommendationsContext';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { deleteReading, getMyReadings } from '../api/readings';
import { statusInfo } from '../utils/bpStatus';
import { errorMessage, formatDateTime, isNotFoundError } from '../utils/format';

export default function ReadingsHistory() {
  const navigate = useNavigate();
  const toast = useToast();
  const {
    dataChanged,
    error: recommendationsError,
    refresh: refreshRecommendations,
  } = useRecommendations();
  const confirm = useConfirm();

  const { data: readings, loading, error, reload } = useAsync(getMyReadings, [], []);
  const [deleteFailure, setDeleteFailure] = useState(null);
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const deletingIdsRef = useRef(new Set());

  function setDeleting(readingId, pending) {
    const next = new Set(deletingIdsRef.current);
    if (pending) next.add(readingId);
    else next.delete(readingId);
    deletingIdsRef.current = next;
    setDeletingIds(next);
  }

  async function performDelete(reading, alreadyPending = false) {
    const readingId = reading.reading_id;
    if (!alreadyPending) {
      if (deletingIdsRef.current.has(readingId)) return;
      setDeleting(readingId, true);
    }

    try {
      try {
        await deleteReading(readingId);
      } catch (err) {
        // Another tab or request may already have removed it. The desired
        // state is already true, so do not show a false deletion failure.
        if (!isNotFoundError(err)) throw err;
      }
      setDeleteFailure(null);
      await reload();
      const refreshed = await dataChanged(); // the advice may no longer apply
      if (refreshed) {
        toast.success('Reading deleted, and your recommendations were updated.');
      } else {
        toast.warning('Reading deleted, but recommendations could not be refreshed. Use Try again above to retry.');
      }
    } catch (err) {
      const message = errorMessage(err, 'The server did not delete this reading.');
      setDeleteFailure({ reading, message });
      toast.error(message);
    } finally {
      setDeleting(readingId, false);
    }
  }

  async function handleDelete(reading) {
    const readingId = reading.reading_id;
    if (deletingIdsRef.current.has(readingId)) return;
    setDeleting(readingId, true);

    let confirmed = false;
    try {
      confirmed = await confirm({
        title: 'Delete this reading?',
        message: `The ${reading.systolic}/${reading.diastolic} mmHg reading will be permanently removed.`,
        confirmLabel: 'Delete',
        variant: 'danger',
      });
      if (!confirmed) return;
      await performDelete(reading, true);
    } finally {
      if (!confirmed) setDeleting(readingId, false);
    }
  }

  async function retryDelete() {
    if (deleteFailure?.reading) await performDelete(deleteFailure.reading);
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader
          title="Readings history"
          subtitle="A complete log of your blood pressure measurements."
          action={
            <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => navigate('/readings/new')}>
              <Plus size={16} /> New reading
            </Button>
          }
        />

        {recommendationsError && (
          <Alert variant="warning" role="alert" className="d-flex align-items-center justify-content-between gap-3">
            <span>Your recommendations could not be refreshed and may be out of date.</span>
            <Button variant="outline-warning" size="sm" onClick={() => refreshRecommendations().catch(() => {})}>
              Try again
            </Button>
          </Alert>
        )}

        {deleteFailure && (
          <Alert variant="danger" role="alert" className="d-flex align-items-center justify-content-between gap-3">
            <span>
              <strong>Reading not deleted.</strong>{' '}
              Could not delete the reading from {formatDateTime(deleteFailure.reading.recorded_at)}. {deleteFailure.message}
            </span>
            <Button
              variant="outline-danger"
              size="sm"
              onClick={retryDelete}
              disabled={deletingIds.has(deleteFailure.reading.reading_id)}
            >
              Try again
            </Button>
          </Alert>
        )}

        <Panel title="All readings" description="Sorted by most recent first.">
          {loading ? (
            <Loader />
          ) : error ? (
            <ErrorState message="Could not load your readings." onRetry={reload} />
          ) : readings.length === 0 ? (
            <EmptyState
              icon={HeartPulse}
              title="No readings yet"
              message="Log your first measurement to start tracking your trend."
              action={
                <Button className="btn-hs-primary" onClick={() => navigate('/readings/new')}>
                  Log a reading
                </Button>
              }
            />
          ) : (
            readings.map((reading) => (
              <DataRow
                key={reading.reading_id}
                accent={statusInfo(reading.status).accent}
                trailing={
                  <>
                    <StatusPill status={reading.status} />
                    <button
                      type="button"
                      className="hs-icon-action hs-icon-action-danger"
                      onClick={() => handleDelete(reading)}
                      aria-label={`Delete reading from ${formatDateTime(reading.recorded_at)}`}
                      disabled={deletingIds.has(reading.reading_id)}
                    >
                      <Trash2 size={18} />
                    </button>
                  </>
                }
              >
                <div className="hs-reading-value">
                  {reading.systolic}/{reading.diastolic} <span className="hs-reading-unit">mmHg</span>
                </div>
                <div className="hs-reading-meta">
                  <Calendar size={13} /> {formatDateTime(reading.recorded_at)}
                </div>
                <ReadingConditions reading={reading} />
              </DataRow>
            ))
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
