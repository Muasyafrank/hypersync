import { useState, useEffect } from 'react';
import { Container, Spinner, Button, Form } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import Layout from '../components/Layout';
import { getAllAlerts, acknowledgeAlert } from '../api/alerts';
import { useToast } from '../context/ToastContext';

export default function ClinicianAlerts() {
  const navigate = useNavigate();
  const toast = useToast();

  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    load();
  }, [showAll]);

  function load() {
    setLoading(true);
    getAllAlerts(!showAll).then(setAlerts).finally(() => setLoading(false));
  }

  async function handleAcknowledge(id) {
    try {
      await acknowledgeAlert(id);
      toast.success('Alert acknowledged.');
      load();
    } catch {
      toast.error('Could not acknowledge alert.');
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
          <div>
            <h2 className="hs-title mb-1">Alert Queue</h2>
            <p className="hs-subtitle mb-0">Patients whose blood pressure trend needs review.</p>
          </div>
          <Form.Check
            type="switch"
            id="show-all-switch"
            label="Show acknowledged"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
        </div>

        <div className="hs-panel">
          {loading ? (
            <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-5">
              <CheckCircle2 size={28} color="#16A34A" className="mb-2" />
              <p className="hs-subtitle mb-0">No unacknowledged alerts. Everything's under control.</p>
            </div>
          ) : (
            alerts.map((a) => (
              <div key={a.alert_id} className="hs-reading-row" style={{ alignItems: 'flex-start' }}>
                <div
                  className="hs-reading-row-accent"
                  style={{ backgroundColor: a.alert_type.includes('high') ? '#DC2626' : '#CA8A04', marginTop: 2 }}
                />
                <div className="flex-grow-1">
                  <div
                    className="d-flex align-items-center gap-2"
                    style={{ fontWeight: 700, color: 'var(--hs-navy)', fontSize: '0.92rem', cursor: 'pointer' }}
                    onClick={() => navigate(`/clinician/patients/${a.patient_id}`)}
                  >
                    <AlertTriangle size={15} color={a.alert_type.includes('high') ? '#DC2626' : '#CA8A04'} />
                    {a.patient_name || 'Patient'}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#475569', marginTop: 2 }}>{a.message}</div>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8', marginTop: 4 }}>
                    {new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  </div>
                </div>
                {!a.acknowledged && (
                  <Button size="sm" className="btn-hs-primary" onClick={() => handleAcknowledge(a.alert_id)}>
                    Acknowledge
                  </Button>
                )}
              </div>
            ))
          )}
        </div>
      </Container>
    </Layout>
  );
}