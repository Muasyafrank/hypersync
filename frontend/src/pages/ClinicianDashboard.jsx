import { useMemo, useState } from 'react';
import { Col, Container, Form, Row } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Search, Users } from 'lucide-react';
import Layout from '../components/Layout';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel, StatCard, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { getPatientSummaries } from '../api/clinician';

import { pluralise } from '../utils/format';

export default function ClinicianDashboard() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  // Single request: the API returns each patient's latest reading and count.
  const { data: patients, loading, error, reload } = useAsync(getPatientSummaries, [], []);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return patients;
    return patients.filter(
      (p) => p.full_name.toLowerCase().includes(term) || p.email.toLowerCase().includes(term),
    );
  }, [patients, search]);

  const counts = useMemo(
    () => ({
      high: patients.filter((p) => p.latest?.status === 'high').length,
      elevated: patients.filter((p) => p.latest?.status === 'elevated').length,
    }),
    [patients],
  );

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader title="Patients" subtitle="Overview of all patients under your care." />

        <Row className="g-3 mb-4">
          <Col md={4} sm={6}>
            <StatCard label="Total patients" icon={Users} value={patients.length} />
          </Col>
          <Col md={4} sm={6}>
            <StatCard label="High readings" value={counts.high} valueColor="#DC2626" sub="Based on latest reading" />
          </Col>
          <Col md={4} sm={6}>
            <StatCard label="Elevated readings" value={counts.elevated} valueColor="#CA8A04" sub="Based on latest reading" />
          </Col>
        </Row>

        <Panel
          title="All patients"
          action={
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
                    <div className="text-end">
                      <div className="hs-reading-value" style={{ fontSize: '0.95rem' }}>
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
