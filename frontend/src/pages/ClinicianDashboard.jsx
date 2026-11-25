import { useMemo, useState } from 'react';
import { Col, Container, Form, Row } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Search, Users } from 'lucide-react';
import Layout from '../components/Layout';
import TreatmentReviewBadge from '../components/TreatmentReviewBadge';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatCard, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { getPatientSummaries } from '../api/clinician';
import { ALERT_ACCENTS } from '../utils/bpStatus';
import { pluralise } from '../utils/format';

export default function ClinicianDashboard() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);

  // Single request: the API returns each patient's latest reading and count.
  const { data: patients, loading, error, reload } = useAsync(getPatientSummaries, [], []);

  // Flagged patients first (priority, then routine); everyone else keeps the server's order.
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const rank = (p) => (p.treatment_review?.level === 'priority' ? 0 : p.treatment_review ? 1 : 2);
    return patients
      .filter((p) => !needsReviewOnly || p.treatment_review)
      .filter((p) => !term || p.full_name.toLowerCase().includes(term) || p.email.toLowerCase().includes(term))
      .map((p, index) => ({ p, index }))
      .sort((a, b) => rank(a.p) - rank(b.p) || a.index - b.index)
      .map(({ p }) => p);
  }, [patients, search, needsReviewOnly]);

  const counts = useMemo(
    () => ({
      high: patients.filter((p) => p.latest?.status === 'high').length,
      elevated: patients.filter((p) => p.latest?.status === 'elevated').length,
      review: patients.filter((p) => p.treatment_review).length,
    }),
    [patients],
  );

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader title="Patients" subtitle="Overview of all patients under your care." />

        <Row className="g-3 mb-4">
          <Col lg={3} sm={6}>
            <StatCard label="Total patients" icon={Users} value={patients.length} />
          </Col>
          <Col lg={3} sm={6}>
            <StatCard label="High readings" value={counts.high} valueColor={ALERT_ACCENTS.high} sub="Based on latest reading" />
          </Col>
          <Col lg={3} sm={6}>
            <StatCard label="Elevated readings" value={counts.elevated} valueColor={ALERT_ACCENTS.elevated} sub="Based on latest reading" />
          </Col>
          <Col lg={3} sm={6}>
            <StatCard
              label="Treatment review"
              value={counts.review}
              valueColor={ALERT_ACCENTS.elevated}
              sub="Sustained elevated/high or low band"
            />
          </Col>
        </Row>

        <Panel
          title="All patients"
          action={
            <div className="d-flex align-items-center gap-3 flex-wrap">
              <Form.Check
                type="switch"
                id="needs-review-only"
                label="Needs review only"
                checked={needsReviewOnly}
                onChange={(event) => setNeedsReviewOnly(event.target.checked)}
              />
            <div className="hs-search-field">
              <Search size={16} color="#94A3B8" aria-hidden="true" />
              <label className="visually-hidden" htmlFor="patient-search">Search patients</label>
              <Form.Control
                id="patient-search"
                type="search"
                placeholder="Search by name or email…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            </div>
          }
        >
          {loading ? (
            <Loader />
          ) : error ? (
            <ErrorState message="Could not load your patient list." onRetry={reload} />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={Users}
              message={patients.length === 0 ? 'No patients registered yet.' : 'No patients match your search.'}
            />
          ) : (
            filtered.map((patient) => (
              <DataRow
                key={patient.user_id}
                onClick={() => navigate(`/clinician/patients/${patient.user_id}`)}
                trailing={
                  <>
                    <TreatmentReviewBadge review={patient.treatment_review} />
                    <div className="text-end">
                      <div className="hs-reading-value hs-reading-value-sm">
                        {patient.latest ? `${patient.latest.systolic}/${patient.latest.diastolic}` : '—'}
                      </div>
                      <div className="hs-reading-meta">{pluralise(patient.reading_count, 'reading')}</div>
                    </div>
                    <StatusPill status={patient.latest?.status || 'no_data'} size="sm" />
                  </>
                }
              >
                <div className="d-flex align-items-center">
                  <div className="hs-avatar me-3" aria-hidden="true">{patient.full_name.charAt(0).toUpperCase()}</div>
                  <div>
                    <div className="hs-reading-value">{patient.full_name}</div>
                    <div className="hs-reading-meta">{patient.email}</div>
                  </div>
                </div>
              </DataRow>
            ))
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
