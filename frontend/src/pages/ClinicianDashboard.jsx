import { useState, useEffect } from 'react';
import { Container, Row, Col, Spinner, Form } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Users, Search } from 'lucide-react';
import Layout from '../components/Layout';
import { getPatients, getPatientReadings } from '../api/clinician';
import { statusInfo } from '../utils/statusColors';

export default function ClinicianDashboard() {
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getPatients()
      .then(async (list) => {
        // Pull each patient's latest reading in parallel so the list shows real status
        const enriched = await Promise.all(
          list.map(async (p) => {
            try {
              const readings = await getPatientReadings(p.user_id);
              return { ...p, latest: readings[0] || null, readingCount: readings.length };
            } catch {
              return { ...p, latest: null, readingCount: 0 };
            }
          })
        );
        if (!cancelled) setPatients(enriched);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  const filtered = patients.filter((p) =>
    p.full_name.toLowerCase().includes(search.toLowerCase()) ||
    p.email.toLowerCase().includes(search.toLowerCase())
  );

  const highCount = patients.filter((p) => p.latest?.status === 'high').length;
  const elevatedCount = patients.filter((p) => p.latest?.status === 'elevated').length;

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="mb-4">
          <h2 className="hs-title mb-1">Patients</h2>
          <p className="hs-subtitle mb-0">Overview of all patients under your care.</p>
        </div>

        <Row className="g-3 mb-4">
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>Total Patients</span><Users size={16} color="#94A3B8" /></div>
              <div className="hs-stat-value">{patients.length}</div>
            </div>
          </Col>
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>High Readings</span></div>
              <div className="hs-stat-value" style={{ color: '#DC2626' }}>{highCount}</div>
              <div className="hs-stat-sub">Based on latest reading</div>
            </div>
          </Col>
          <Col md={4} sm={6}>
            <div className="hs-stat-card">
              <div className="hs-stat-label"><span>Elevated Readings</span></div>
              <div className="hs-stat-value" style={{ color: '#CA8A04' }}>{elevatedCount}</div>
              <div className="hs-stat-sub">Based on latest reading</div>
            </div>
          </Col>
        </Row>

        <div className="hs-panel">
          <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h5 className="hs-title mb-0">All Patients</h5>
            <div style={{ position: 'relative', width: 260 }}>
              <Search size={16} color="#94A3B8" style={{ position: 'absolute', left: 12, top: 10 }} />
              <Form.Control
                placeholder="Search by name or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 36 }}
              />
            </div>
          </div>

          {loading ? (
            <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : filtered.length === 0 ? (
            <p className="hs-subtitle text-center py-4">
              {patients.length === 0 ? 'No patients registered yet.' : 'No patients match your search.'}
            </p>
          ) : (
            filtered.map((p) => {
              const s = statusInfo(p.latest?.status || 'no_data');
              return (
                <div
                  key={p.user_id}
                  className="hs-reading-row"
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/clinician/patients/${p.user_id}`)}
                >
                  <div className="d-flex align-items-center">
                    <div className="hs-avatar me-3">{p.full_name.charAt(0).toUpperCase()}</div>
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--hs-navy)' }}>{p.full_name}</div>
                      <div style={{ fontSize: '0.82rem', color: '#94A3B8' }}>{p.email}</div>
                    </div>
                  </div>
                  <div className="d-flex align-items-center gap-3">
                    <div className="text-end">
                      <div style={{ fontWeight: 700, color: 'var(--hs-navy)', fontSize: '0.95rem' }}>
                        {p.latest ? `${p.latest.systolic}/${p.latest.diastolic}` : '—'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>
                        {p.readingCount} reading{p.readingCount === 1 ? '' : 's'}
                      </div>
                    </div>
                    <span style={{ backgroundColor: s.bg, color: s.text, fontWeight: 600, padding: '0.35rem 0.7rem', borderRadius: '20px', fontSize: '0.8rem' }}>
                      {s.label}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Container>
    </Layout>
  );
}