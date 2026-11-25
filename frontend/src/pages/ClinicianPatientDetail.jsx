import { useState } from 'react';
import { Container } from 'react-bootstrap';
import { useNavigate, useParams } from 'react-router-dom';
import { Calendar } from 'lucide-react';
import Layout from '../components/Layout';
import FactorEntryRow from '../components/lifestyle/FactorEntryRow';
import ReadingConditions from '../components/ReadingConditions';
import BPTrendChart from '../components/BPTrendChart';
import PeriodSelect from '../components/PeriodSelect';
import TreatmentReviewPanel from '../components/TreatmentReviewPanel';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import {
  getPatient,
  getPatientFactors,
  getPatientReadings,
  getPatientTrend,
  getTreatmentReview,
} from '../api/clinician';
import { statusInfo } from '../utils/bpStatus';
import { formatDateTime } from '../utils/format';

const EMPTY = { patient: null, readings: [], factors: [], factorsError: null };

function TreatmentReviewSection({ patientId }) {
  const {
    data: review,
    loading,
    error,
    reload,
  } = useAsync(() => getTreatmentReview(patientId), [patientId]);

  if (loading) {
    return (
      <Panel title="Treatment review" className="mb-4">
        <Loader />
      </Panel>
    );
  }
  if (error) {
    return <ErrorState message="Could not load the treatment-review summary." onRetry={reload} />;
  }
  if (!review) return null;
  return <TreatmentReviewPanel patientId={patientId} review={review} onChanged={reload} />;
}

export default function ClinicianPatientDetail() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [periodDays, setPeriodDays] = useState(30);

  // The patient's record: loaded once per patient.
  const { data, loading, error, reload } = useAsync(
    async () => {
      // Fetched by id rather than by listing every patient and filtering.
      const [patient, readings, factorResult] = await Promise.all([
        getPatient(patientId),
        getPatientReadings(patientId),
        getPatientFactors(patientId)
          .then((factors) => ({ factors: factors ?? [], factorsError: null }))
          .catch((error) => ({ factors: [], factorsError: error })),
      ]);
      return { patient, readings, ...factorResult };
    },
    [patientId],
    EMPTY,
  );

  // The trend is its own request, so changing the period refetches only this
  // chart instead of reloading the whole page (and the patient's full history).
  const {
    data: trend,
    loading: trendLoading,
    error: trendError,
    reload: reloadTrend,
  } = useAsync(() => getPatientTrend(patientId, periodDays), [patientId, periodDays]);

  const { patient, readings, factors, factorsError } = data ?? EMPTY;

  if (loading) return <Layout><Loader className="py-5" /></Layout>;
  if (error) {
    return (
      <Layout>
        <ErrorState message="Could not load this patient's record." onRetry={reload} />
      </Layout>
    );
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader
          title={patient?.full_name || 'Patient'}
          subtitle={patient?.email}
          onBack={() => navigate('/clinician')}
        />

        <TreatmentReviewSection key={patientId} patientId={patientId} />

        <Panel
          title="Blood pressure trend"
          className="mb-4"
          action={<PeriodSelect value={periodDays} onChange={setPeriodDays} />}
        >
          {trendLoading ? (
            <Loader />
          ) : trendError ? (
            <ErrorState message="Could not load the trend for this period." onRetry={reloadTrend} />
          ) : trend?.daily_breakdown?.length ? (
            <BPTrendChart dailyBreakdown={trend.daily_breakdown} height={380} animate={false} />
          ) : (
            <EmptyState message="No readings in this period." />
          )}
        </Panel>

        <Panel title="Reading history">
          {readings.length === 0 ? (
            <EmptyState message="No readings logged yet." />
          ) : (
            readings.map((reading) => (
              <DataRow
                key={reading.reading_id}
                accent={statusInfo(reading.status).accent}
                trailing={<StatusPill status={reading.status} />}
              >
                <div className="hs-reading-value">
                  {reading.systolic}/{reading.diastolic} <span className="hs-reading-unit">mmHg</span>
                  {reading.heart_rate && <span className="hs-reading-unit"> · {reading.heart_rate} bpm</span>}
                </div>
                <div className="hs-reading-meta">
                  <Calendar size={13} /> {formatDateTime(reading.recorded_at)}
                </div>
                <ReadingConditions reading={reading} />
                {reading.notes && <div className="hs-reading-note">“{reading.notes}”</div>}
              </DataRow>
            ))
          )}
        </Panel>

        <Panel title="Lifestyle &amp; environmental factors" className="mt-4">
          {factorsError ? (
            <ErrorState message="Could not load this patient's lifestyle entries." onRetry={reload} />
          ) : factors.length === 0 ? (
            <EmptyState message="No lifestyle entries logged yet." />
          ) : (
            factors.map((factor) => <FactorEntryRow key={factor.factor_id} entry={factor} />)
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
