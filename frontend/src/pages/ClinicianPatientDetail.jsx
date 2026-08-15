import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Container, Spinner, Form } from 'react-bootstrap';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceArea,
} from 'recharts';
import { ArrowLeft, Calendar } from 'lucide-react';
import Layout from '../components/Layout';
import { getPatients, getPatientReadings, getPatientTrend } from '../api/clinician';
import { statusInfo } from '../utils/statusColors';

export default function ClinicianPatientDetail() {
  const { patientId } = useParams();
  const navigate = useNavigate();

  const [patient, setPatient] = useState(null);
  const [readings, setReadings] = useState([]);
  const [trend, setTrend] = useState(null);
  const [periodDays, setPeriodDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([getPatients(), getPatientReadings(patientId), getPatientTrend(patientId, periodDays)])
      .then(([patients, readingsData, trendData]) => {
        if (cancelled) return;
        setPatient(patients.find((p) => p.user_id === patientId) || null);
        setReadings(readingsData);
        setTrend(trendData);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [patientId, periodDays]);

  const chartData = (trend?.daily_breakdown || []).map((d) => ({
    date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    Systolic: d.avg_systolic,
    Diastolic: d.avg_diastolic,
  }));

  if (loading) {
    return (
      <Layout>
        <div className="text-center py-5"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="d-flex align-items-center gap-3 mb-1">
          <ArrowLeft size={20} style={{ cursor: 'pointer', color: 'var(--hs-navy)' }} onClick={() => navigate('/clinician')} />
          <h2 className="hs-title mb-0">{patient?.full_name || 'Patient'}</h2>
        </div>
        <p className="hs-subtitle mb-4">{patient?.email}</p>

        <div className="hs-panel mb-4">
          <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h5 className="hs-title mb-0">Blood Pressure Trend</h5>
            <Form.Select
              style={{ width: 'auto' }}
              value={periodDays}
              onChange={(e) => setPeriodDays(Number(e.target.value))}
            >
              <option value={7}>Last 7 Days</option>
              <option value={14}>Last 14 Days</option>
              <option value={30}>Last 30 Days</option>
              <option value={90}>Last 90 Days</option>
            </Form.Select>
          </div>

          {chartData.length === 0 ? (
            <p className="hs-subtitle text-center py-4">No readings in this period.</p>
          ) : (
            <div style={{ width: '100%', height: 380 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" stroke="#64748B" fontSize={12} />
                  <YAxis stroke="#64748B" fontSize={12} domain={[40, 200]} ticks={[40, 80, 120, 160, 200]} />
                  <ReferenceArea y1={40} y2={90} fill="#DBEAFE" fillOpacity={0.35} ifOverflow="extendDomain" />
                  <ReferenceArea y1={90} y2={135} fill="#DCFCE7" fillOpacity={0.4} ifOverflow="extendDomain" />
                  <ReferenceArea y1={135} y2={150} fill="#FEF9C3" fillOpacity={0.5} ifOverflow="extendDomain" />
                  <ReferenceArea y1={150} y2={200} fill="#FEE2E2" fillOpacity={0.45} ifOverflow="extendDomain" />
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} labelStyle={{ color: '#0F172A', fontWeight: 600 }} />
                  <Legend />
                  <Line type="monotone" dataKey="Systolic" stroke="#0D9488" strokeWidth={2.5} dot={{ r: 4 }} isAnimationActive={false} />
                  <Line type="monotone" dataKey="Diastolic" stroke="#0F172A" strokeWidth={2.5} dot={{ r: 4 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="hs-panel">
          <h5 className="hs-title mb-3">Reading History</h5>
          {readings.length === 0 ? (
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
                        {r.heart_rate && <span style={{ fontWeight: 400, fontSize: '0.85rem', color: '#94A3B8' }}> · {r.heart_rate} bpm</span>}
                      </div>
                      <div className="d-flex align-items-center gap-1" style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                        <Calendar size={13} />
                        {new Date(r.recorded_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                      </div>
                      {r.notes && <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: 2 }}>"{r.notes}"</div>}
                    </div>
                  </div>
                  <span style={{ backgroundColor: s.bg, color: s.text, fontWeight: 600, padding: '0.35rem 0.7rem', borderRadius: '20px', fontSize: '0.85rem' }}>
                    {s.label}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </Container>
    </Layout>
  );
}