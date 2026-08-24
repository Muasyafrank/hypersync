import { useState, useEffect } from 'react';
import { Container, Spinner } from 'react-bootstrap';
import { Bell, CheckCircle2 } from 'lucide-react';
import Layout from '../components/Layout';
import { getMyAlerts } from '../api/alerts';

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyAlerts().then(setAlerts).finally(() => setLoading(false));
  }, []);

  return (
    <Layout>
      <Container fluid className="px-0" style={{ maxWidth: 760 }}>
        <h2 className="hs-title mb-1">Alerts</h2>
        <p className="hs-subtitle mb-4">Notifications raised when your blood pressure trend needs attention.</p>

        <div className="hs-panel">
          {loading ? (
            <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-5">
              <Bell size={28} color="#CBD5E1" className="mb-2" />
              <p className="hs-subtitle mb-0">No alerts yet. You'll see one here if your trend becomes elevated or high.</p>
            </div>
          ) : (
            alerts.map((a) => (
              <div key={a.alert_id} className="hs-reading-row" style={{ alignItems: 'flex-start' }}>
                <div
                  className="hs-reading-row-accent"
                  style={{ backgroundColor: a.alert_type.includes('high') ? '#DC2626' : '#CA8A04', marginTop: 2 }}
                />
                <div className="flex-grow-1">
                  <div style={{ fontSize: '0.9rem', color: 'var(--hs-navy)', lineHeight: 1.5 }}>{a.message}</div>
                  <div style={{ fontSize: '0.78rem', color: '#94A3B8', marginTop: 4 }}>
                    {new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  </div>
                </div>
                {a.acknowledged && (
                  <span className="d-flex align-items-center gap-1" style={{ fontSize: '0.78rem', color: '#16A34A', fontWeight: 600 }}>
                    <CheckCircle2 size={14} /> Reviewed
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </Container>
    </Layout>
  );
}