import { useState } from 'react';
import { Container } from 'react-bootstrap';
import { useNavigate, useParams } from 'react-router-dom';
import { Brain, Calendar, Moon, Pill, Salad } from 'lucide-react';
import Layout from '../components/Layout';
import BPTrendChart from '../components/BPTrendChart';
import PeriodSelect from '../components/PeriodSelect';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { getPatient, getPatientFactors, getPatientReadings, getPatientTrend } from '../api/clinician';
import { statusInfo } from '../utils/bpStatus';
import { formatDateTime, formatFullDate } from '../utils/format';

const EMPTY = { patient: null, readings: [], trend: null, factors: [] };

/** One lifestyle entry's tags, skipping anything the patient didn't log. */
function factorTags(factor) {
  const tags = [];
  if (factor.stress_level) tags.push({ icon: Brain, text: `${factor.stress_level} stress` });
  if (factor.sleep_hours != null) tags.push({ icon: Moon, text: `${factor.sleep_hours}h sleep` });
  if (factor.diet_adherence != null) tags.push({ icon: Salad, text: factor.diet_adherence ? 'Diet followed' : 'Diet missed' });
  if (factor.medication_taken != null) tags.push({ icon: Pill, text: factor.medication_taken ? 'Meds taken' : 'Meds missed' });
  return tags;
}

export default function ClinicianPatientDetail() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [periodDays, setPeriodDays] = useState(30);

  const { data, loading, error, reload } = useAsync(
    async () => {
      // Fetched by id rather than by listing every patient and filtering.
      const [patient, readings, trend, factors] = await Promise.all([
        getPatient(patientId),
        getPatientReadings(patientId),
        getPatientTrend(patientId, periodDays),
        getPatientFactors(patientId).catch(() => []),
      ]);
      return { patient, readings, trend, factors };
    },
    [patientId, periodDays],
    EMPTY,
  );

  const { patient, readings, trend, factors } = data ?? EMPTY;

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

        <Panel
          title="Blood pressure trend"
          className="mb-4"
          action={<PeriodSelect value={periodDays} onChange={setPeriodDays} />}
        >
          {trend?.daily_breakdown?.length ? (
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
                {reading.notes && <div className="hs-reading-note">“{reading.notes}”</div>}
              </DataRow>
            ))
          )}
        </Panel>

        <Panel title="Lifestyle &amp; environmental factors" className="mt-4">
          {factors.length === 0 ? (
            <EmptyState message="No lifestyle entries logged yet." />
          ) : (
            factors.map((factor) => (
              <DataRow key={factor.factor_id}>
                <div className="hs-reading-value" style={{ fontSize: '0.9rem' }}>
                  {formatFullDate(factor.logged_date)}
                </div>
                <div className="d-flex gap-3 mt-1 flex-wrap hs-factor-tags">
                  {factorTags(factor).map(({ icon: Icon, text }) => (
                    <span key={text} className="d-flex align-items-center gap-1">
                      <Icon size={13} /> {text}
                    </span>
                  ))}
                </div>
              </DataRow>
            ))
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
