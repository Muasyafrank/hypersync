import { useState, useEffect } from 'react';
import { Container, Form, Spinner } from 'react-bootstrap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceArea,
} from 'recharts';
import { TrendingUp, Activity, Heart, Calendar } from 'lucide-react';
import Layout from '../components/Layout';
import { getMyTrend } from '../api/readings';
import { statusInfo } from '../utils/statusColors';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="hs-chart-tooltip">
      <div className="hs-chart-tooltip-date">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="hs-chart-tooltip-row">
          <span className="hs-chart-tooltip-dot" style={{ background: p.color }} />
          <span className="hs-chart-tooltip-label">{p.dataKey}</span>
          <span className="hs-chart-tooltip-value">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function Trend() {
  const [periodDays, setPeriodDays] = useState(30);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getMyTrend(periodDays).then(setTrend).finally(() => setLoading(false));
  }, [periodDays]);

  const chartData = (trend?.daily_breakdown || []).map((d) => ({
    date: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    Systolic: d.avg_systolic,
    Diastolic: d.avg_diastolic,
  }));

  const overall = trend?.status ? statusInfo(trend.status) : null;

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
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </Form.Select>
        </div>

        {loading ? (
          <div className="text-center py-5"><Spinner animation="border" style={{ color: 'var(--hs-teal)' }} /></div>
        ) : (
          <>
            {trend && trend.reading_count > 0 && (
              <div className="row g-3 mb-4">
                <div className="col-md-3 col-sm-6">
                  <div className="hs-stat-card">
                    <div className="hs-stat-label"><span>Avg systolic</span><Heart size={16} color="#94A3B8" /></div>
                    <div className="hs-stat-value">{trend.avg_systolic ?? '—'}</div>
                  </div>
                </div>
                <div className="col-md-3 col-sm-6">
                  <div className="hs-stat-card">
                    <div className="hs-stat-label"><span>Avg diastolic</span><Activity size={16} color="#94A3B8" /></div>
                    <div className="hs-stat-value">{trend.avg_diastolic ?? '—'}</div>
                  </div>
                </div>
                <div className="col-md-3 col-sm-6">
                  <div className="hs-stat-card">
                    <div className="hs-stat-label"><span>Readings</span><Calendar size={16} color="#94A3B8" /></div>
                    <div className="hs-stat-value">{trend.reading_count}</div>
                  </div>
                </div>
                <div className="col-md-3 col-sm-6">
                  <div className="hs-stat-card">
                    <div className="hs-stat-label"><span>Overall status</span><TrendingUp size={16} color="#94A3B8" /></div>
                    {overall && (
                      <span className="hs-status-badge mt-2 d-inline-block" style={{ backgroundColor: overall.bg, color: overall.text }}>
                        {overall.label}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="hs-panel">
              <h5 className="hs-title mb-1">Systolic &amp; diastolic history</h5>
              <p className="hs-subtitle mb-3" style={{ fontSize: '0.88rem' }}>
                Shaded bands mark low, controlled, elevated, and high zones.
              </p>

              {chartData.length === 0 ? (
                <div className="text-center py-5">
                  <p className="hs-subtitle mb-0">No readings in this period yet. Log a few readings to see your trend.</p>
                </div>
              ) : (
                <div style={{ width: '100%', height: 420 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="sysGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0D9488" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="#0D9488" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="diaGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0F172A" stopOpacity={0.22} />
                          <stop offset="100%" stopColor="#0F172A" stopOpacity={0} />
                        </linearGradient>
                      </defs>

                      <CartesianGrid strokeDasharray="4 6" stroke="#CBD5E1" vertical={false} />
                      <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#94A3B8" fontSize={12} domain={[40, 200]} ticks={[40, 80, 120, 160, 200]} tickLine={false} axisLine={false} />

                      <ReferenceArea y1={40} y2={90} fill="#3B82F6" fillOpacity={0.06} ifOverflow="extendDomain" />
                      <ReferenceArea y1={90} y2={135} fill="#22C55E" fillOpacity={0.07} ifOverflow="extendDomain" />
                      <ReferenceArea y1={135} y2={150} fill="#EAB308" fillOpacity={0.08} ifOverflow="extendDomain" />
                      <ReferenceArea y1={150} y2={200} fill="#EF4444" fillOpacity={0.07} ifOverflow="extendDomain" />

                      <Tooltip content={<CustomTooltip />} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: '0.85rem' }} />

                      <Area
                        type="monotone"
                        dataKey="Diastolic"
                        stroke="#0F172A"
                        strokeWidth={2.5}
                        fill="url(#diaGradient)"
                        dot={{ r: 3, fill: '#0F172A', strokeWidth: 0 }}
                        activeDot={{ r: 6, strokeWidth: 2, stroke: '#FFFFFF' }}
                        isAnimationActive={true}
                        animationDuration={700}
                      />
                      <Area
                        type="monotone"
                        dataKey="Systolic"
                        stroke="#0D9488"
                        strokeWidth={2.5}
                        fill="url(#sysGradient)"
                        dot={{ r: 3, fill: '#0D9488', strokeWidth: 0 }}
                        activeDot={{ r: 6, strokeWidth: 2, stroke: '#FFFFFF' }}
                        isAnimationActive={true}
                        animationDuration={700}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </>
        )}
      </Container>
    </Layout>
  );
}