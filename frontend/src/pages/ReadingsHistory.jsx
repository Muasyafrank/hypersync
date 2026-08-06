import { useState, useEffect } from 'react';
import { Container, Button, Spinner } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Plus, Calendar, Trash2 } from 'lucide-react';
import Layout from '../components/Layout';
import { getMyReadings, deleteReading } from '../api/readings';
import { statusInfo } from '../utils/statusColors';

export default function ReadingsHistory() {
  const navigate = useNavigate();
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    getMyReadings()
      .then(setReadings)
      .finally(() => setLoading(false));
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this reading? This cannot be undone.')) return;
    await deleteReading(id);
    load();
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
          <div>
            <h2 className="hs-title mb-1">Readings History</h2>
            <p className="hs-subtitle mb-0">A complete log of your blood pressure measurements.</p>
          </div>
          <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => navigate('/readings/new')}>
            <Plus size={16} /> New Reading
          </Button>
        </div>

        <div className="hs-panel">
          <h5 className="hs-title mb-1">All Readings</h5>
          <p className="hs-subtitle mb-3" style={{ fontSize: '0.88rem' }}>Sorted by most recent first.</p>

          {loading ? (
            <div className="text-center py-4"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : readings.length === 0 ? (
            <p className="hs-subtitle">No readings logged yet.</p>
          ) : (
            readings.map((r) => {
              const s = statusInfo(r.status);
              return (
                <div key={r.reading_id} className="hs-reading-row">
                  <div className="d-flex align-items-center">
                    <div className="hs-reading-row-accent" style={{ backgroundColor: s.accent }} />
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--hs-navy)' }}>
                        {r.systolic}/{r.diastolic} <span style={{ fontWeight: 400, fontSize: '0.85rem', color: '#94A3B8' }}>mmHg</span>
                      </div>
                      <div className="d-flex align-items-center gap-1" style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                        <Calendar size={13} />
                        {new Date(r.recorded_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                  <div className="d-flex align-items-center gap-3">
                    <span style={{ backgroundColor: s.bg, color: s.text, fontWeight: 600, padding: '0.35rem 0.7rem', borderRadius: '20px', fontSize: '0.85rem' }}>
                      {s.label}
                    </span>
                    <Trash2
                      size={18}
                      color="#94A3B8"
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleDelete(r.reading_id)}
                    />
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