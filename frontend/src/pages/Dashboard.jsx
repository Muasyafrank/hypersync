import { useState, useEffect } from 'react';
import { Container, Row, Col, Button, Badge, Spinner, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Heart, TrendingUp, Activity, Bell, ArrowRight } from 'lucide-react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getMyReadings, getMyTrend } from '../api/readings';
import { statusInfo } from '../utils/statusColors';

// Safe helper for status info with fallback values
const getSafeStatus = (key) => {
  const info = statusInfo(key);
  return info || { label: 'Unknown', bg: '#6c757d', text: '#ffffff', accent: '#6c757d' };
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [readings, setReadings] = useState([]);
  const [trend30, setTrend30] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    
    Promise.all([getMyReadings(), getMyTrend(30)])
      .then(([r, t]) => {
        if (!isMounted) return;
        setReadings(Array.isArray(r) ? r : []);
        setTrend30(t || null);
      })
      .catch((err) => {
        console.error("Failed to load dashboard data:", err);
        if (isMounted) setError("Failed to load health metrics.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => { isMounted = false; };
  }, []);

  if (loading) {
    return (
      <Layout>
        <div className="text-center py-5">
          <Spinner animation="border" style={{ color: 'var(--hs-teal, #0d9488)' }} />
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <Container className="py-4">
          <Alert variant="danger">{error}</Alert>
        </Container>
      </Layout>
    );
  }

  const latest = readings.length > 0 ? readings[0] : null;
  const overallStatus = getSafeStatus(trend30?.status || 'no_data');

  const distribution = ['controlled', 'elevated', 'high', 'low'].map((key) => {
    const info = getSafeStatus(key);
    return {
      name: info.label,
      value: readings.filter((r) => r?.status === key).length,
      color: info.accent,
    };
  }).filter((d) => d.value > 0);

  function daysAgo(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '—';
    const diffMs = Date.now() - date.getTime();
    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (days <= 0) return 'Today';
    if (days === 1) return '1 day ago';
    return `${days} days ago`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '';
    return date.toLocaleString(undefined, { 
      month: 'short', 
      day: 'numeric', 
      hour: 'numeric', 
      minute: '2-digit' 
    });
  }

  return (
    <Layout>
      <Container fluid className="px-0 py-3">
        <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
          <div>
            <h2 className="hs-title mb-1">Dashboard</h2>
            <p className="hs-subtitle mb-0">
              Welcome back, {user?.full_name || 'there'}. Here's your latest health summary.
            </p>
          </div>
          <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => navigate('/readings/new')}>
            <Heart size={16} /> Log Reading
          </Button>
        </div>

        <Row className="g-3 mb-4">
          <Col md={3} sm={6}>
            <div className="hs-stat-card border p-3 rounded">
              <div className="hs-stat-label d-flex justify-content-between align-items-center">
                <span>Latest Reading</span>
                <Activity size={16} color="#94A3B8" />
              </div>
              <div className="hs-stat-value h3 mb-1 mt-2">
                {latest ? `${latest.systolic}/${latest.diastolic}` : '—'}
              </div>
              <div className="hs-stat-sub text-muted small">
                {latest ? daysAgo(latest.recorded_at) : 'No readings yet'}
              </div>
            </div>
          </Col>

          <Col md={3} sm={6}>
            <div className="hs-stat-card border p-3 rounded">
              <div className="hs-stat-label d-flex justify-content-between align-items-center">
                <span>30-Day Average</span>
                <Heart size={16} color="#94A3B8" />
              </div>
              <div className="hs-stat-value h3 mb-1 mt-2">
                {trend30?.avg_systolic ? `${Math.round(trend30.avg_systolic)}/${Math.round(trend30.avg_diastolic)}` : '—'}
              </div>
              <div className="hs-stat-sub text-muted small">
                Based on {trend30?.reading_count || 0} readings
              </div>
            </div>
          </Col>

          <Col md={3} sm={6}>
            <div className="hs-stat-card border p-3 rounded">
              <div className="hs-stat-label d-flex justify-content-between align-items-center">
                <span>Status</span>
                <TrendingUp size={16} color="#94A3B8" />
              </div>
              <div className="mt-2">
                <Badge style={{ backgroundColor: overallStatus.bg, color: overallStatus.text, fontWeight: 600, padding: '0.4rem 0.8rem', borderRadius: '20px' }}>
                  {overallStatus.label}
                </Badge>
              </div>
            </div>
          </Col>

          <Col md={3} sm={6}>
            <div className="hs-stat-card border p-3 rounded">
              <div className="hs-stat-label d-flex justify-content-between align-items-center">
                <span>Unread Alerts</span>
                <Bell size={16} color="#94A3B8" />
              </div>
              <div className="hs-stat-value h3 mb-1 mt-2">0</div>
            </div>
          </Col>
        </Row>

        <Row className="g-3">
          <Col lg={7}>
            <div className="hs-panel border p-3 rounded">
              <div className="d-flex justify-content-between align-items-start mb-3">
                <div>
                  <h5 className="hs-title mb-1">Recent Readings</h5>
                  <p className="hs-subtitle mb-0 text-muted" style={{ fontSize: '0.88rem' }}>Your latest blood pressure logs.</p>
                </div>
                <Button variant="link" className="d-flex align-items-center gap-1 p-0 text-decoration-none" style={{ color: 'var(--hs-teal, #0d9488)', fontWeight: 600, fontSize: '0.9rem' }} onClick={() => navigate('/readings')}>
                  View All <ArrowRight size={14} />
                </Button>
              </div>

              {readings.length === 0 ? (
                <p className="hs-subtitle text-muted">No readings logged yet.</p>
              ) : (
                readings.slice(0, 5).map((r, idx) => {
                  const s = getSafeStatus(r.status);
                  return (
                    <div key={r.reading_id || idx} className="hs-reading-row d-flex justify-content-between align-items-center py-2 border-bottom">
                      <div className="d-flex align-items-center gap-2">
                        <div className="hs-reading-row-accent" style={{ width: '4px', height: '32px', backgroundColor: s.accent, borderRadius: '2px' }} />
                        <div>
                          <div style={{ fontWeight: 700, color: 'var(--hs-navy, #0f172a)' }}>
                            {r.systolic}/{r.diastolic} <span style={{ fontWeight: 400, fontSize: '0.85rem', color: '#94A3B8' }}>mmHg</span>
                          </div>
                          <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                            {formatDate(r.recorded_at)}
                          </div>
                        </div>
                      </div>
                      <Badge style={{ backgroundColor: s.bg, color: s.text, fontWeight: 600, padding: '0.35rem 0.7rem', borderRadius: '20px' }}>
                        {s.label}
                      </Badge>
                    </div>
                  );
                })
              )}
            </div>
          </Col>

          <Col lg={5}>
            <div className="hs-panel border p-3 rounded h-100">
              <h5 className="hs-title mb-1">Reading Distribution</h5>
              <p className="hs-subtitle mb-3 text-muted" style={{ fontSize: '0.88rem' }}>Breakdown of your readings by classification.</p>

              {distribution.length === 0 ? (
                <p className="hs-subtitle text-muted">No data to display yet.</p>
              ) : (
                <div style={{ position: 'relative', width: '100%', height: '260px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={distribution}
                        dataKey="value"
                        innerRadius={70}
                        outerRadius={100}
                        paddingAngle={2}
                      >
                        {distribution.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center', pointerEvents: 'none' }}>
                    <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--hs-navy, #0f172a)' }}>{readings.length}</div>
                    <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Total</div>
                  </div>
                </div>
              )}
            </div>
          </Col>
        </Row>
      </Container>
    </Layout>
  );
}