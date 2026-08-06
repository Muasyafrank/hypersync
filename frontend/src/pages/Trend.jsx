import { useState, useEffect } from 'react';
import { Container, Form, Spinner } from 'react-bootstrap';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceArea,
} from 'recharts';
import Layout from '../components/Layout';
import { getMyTrend } from '../api/readings';

export default function Trend() {
  const [periodDays, setPeriodDays] = useState(30);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getMyTrend(periodDays).then(setTrend).finally(() => setLoading(false));
  }, [periodDays]);

  const chartData =
    trend?.daily_breakdown.map((d) => ({
      date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      Systolic: d.avg_systolic,
      Diastolic: d.avg_diastolic,
    })) || [];

  return (
    <Layout>
      <Container fluid className="px-0">
        <div className="d-flex justify-content-between align-items-start mb-4 flex-wrap gap-2">
          <div>
            <h2 className="hs-title mb-1">Trends</h2>
            <p className="hs-subtitle mb-0">Visualize your blood pressure over time.</p>
          </div>
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

        <div className="hs-panel">
          <h5 className="hs-title mb-1">Systolic &amp; Diastolic History</h5>
          <p className="hs-subtitle mb-3" style={{ fontSize: '0.88rem' }}>
            Colored background bands represent normal (green), elevated (yellow), and high (orange/red) zones.
          </p>

          {loading ? (
            <div className="text-center py-5"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
          ) : chartData.length === 0 ? (
            <p className="hs-subtitle">No readings in this period yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="date" stroke="#64748B" fontSize={12} />
                <YAxis stroke="#64748B" fontSize={12} domain={[40, 200]} ticks={[40, 80, 120, 160, 200]} />

                {/* Low zone */}
                <ReferenceArea y1={40} y2={90} fill="#DBEAFE" fillOpacity={0.35} />
                {/* Controlled zone */}
                <ReferenceArea y1={90} y2={135} fill="#DCFCE7" fillOpacity={0.4} />
                {/* Elevated zone */}
                <ReferenceArea y1={135} y2={150} fill="#FEF9C3" fillOpacity={0.5} />
                {/* High zone */}
                <ReferenceArea y1={150} y2={200} fill="#FEE2E2" fillOpacity={0.45} />

                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} labelStyle={{ color: '#0F172A', fontWeight: 600 }} />
                <Legend />
                <Line type="monotone" dataKey="Systolic" stroke="#0D9488" strokeWidth={2.5} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="Diastolic" stroke="#0F172A" strokeWidth={2.5} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </Container>
    </Layout>
  );
}