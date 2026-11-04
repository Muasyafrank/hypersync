import { Button, Container } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Calendar, HeartPulse, Plus, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import ReadingConditions from '../components/ReadingConditions';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { deleteReading, getMyReadings } from '../api/readings';
import { statusInfo } from '../utils/bpStatus';
import { errorMessage, formatDateTime } from '../utils/format';

export default function ReadingsHistory() {
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();

  const { data: readings, loading, error, reload } = useAsync(getMyReadings, [], []);

  async function handleDelete(reading) {
    const confirmed = await confirm({
      title: 'Delete this reading?',
      message: `The ${reading.systolic}/${reading.diastolic} mmHg reading will be permanently removed.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await deleteReading(reading.reading_id);
      toast.success('Reading deleted.');
      reload();
    } catch (err) {
      toast.error(errorMessage(err, 'Could not delete this reading.'));
    }
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
