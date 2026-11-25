import { useMemo } from 'react';
import { Alert, Button, Col, Container, Row } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Activity, ArrowRight, Bell, Heart, Lightbulb, TrendingUp } from 'lucide-react';
import Layout from '../components/Layout';
import RecommendationCard from '../components/RecommendationCard';
import { DataRow, ErrorState, Loader, PageHeader, Panel, StatCard, StatusPill } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useRecommendations } from '../context/RecommendationsContext';
import { useAsync } from '../hooks/useAsync';
import { getMyReadings, getMyReadingSummary, getMyTrend } from '../api/readings';
import { getMyAlerts } from '../api/alerts';
import { statusInfo } from '../utils/bpStatus';
import { formatDateTime, relativeDays } from '../utils/format';

const RECENT_LIMIT = 5;
const DASHBOARD_RECOMMENDATIONS = 4; // the full list lives on the Recommendations tab
const TREND_WINDOW_DAYS = 30;
const DISTRIBUTION_KEYS = ['controlled', 'elevated', 'high', 'low'];

const EMPTY = {
  readings: [],
  summary: { total: 0, status_counts: {} },
  trend: null,
  alerts: [],
  alertsError: null,
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Core dashboard data: one combined load so the page renders in one pass.
  const { data, loading, error, reload } = useAsync(
    async () => {
      // Only the handful of readings shown on screen are downloaded; the
      // totals for the distribution chart come from a small server-side count.
      const [readings, summary, trend, alertResult] = await Promise.all([
        getMyReadings({ limit: RECENT_LIMIT }),
        getMyReadingSummary(),
        getMyTrend(TREND_WINDOW_DAYS),
        getMyAlerts()
          .then((alerts) => ({ alerts: alerts ?? [], alertsError: null }))
          .catch((error) => ({ alerts: [], alertsError: error })),
      ]);
      return { readings: readings ?? [], summary, trend, ...alertResult };
    },
    [],
    EMPTY,
  );

  // Shared with the Recommendations tab and refreshed whenever the patient saves
  // something, so the dashboard never shows advice older than their data.
  const {
    items: recommendations,
    status: recsStatus,
    error: recsError,
    refresh: refreshRecs,
  } = useRecommendations();
  const loadingRecs = ['idle', 'loading', 'refreshing'].includes(recsStatus) && recommendations.length === 0;

  const { readings, summary, trend, alerts, alertsError } = data ?? EMPTY;

  const distribution = useMemo(
    () =>
      DISTRIBUTION_KEYS.map((key) => {
        const info = statusInfo(key);
        return {
          name: info.label,
          value: summary.status_counts?.[key] ?? 0,
          color: info.accent,
        };
      }).filter((entry) => entry.value > 0),
    [summary],
  );

  if (loading) return <Layout><Loader className="py-5" /></Layout>;

  if (error) {
    return (
      <Layout>
        <ErrorState message="Could not load your dashboard data." onRetry={reload} />
      </Layout>
    );
  }

  const latest = readings[0] ?? null;
  const unreadAlerts = alerts.filter((a) => !a.acknowledged).length;

  return (
    <Layout>
      <Container fluid className="px-0 py-3">
        <PageHeader
          title="Dashboard"
          subtitle={`Welcome back, ${user?.full_name || 'there'}. Here's your latest health summary.`}
          action={
            <Button className="btn-hs-primary d-flex align-items-center gap-2" onClick={() => navigate('/readings/new')}>
              <Heart size={16} /> Log reading
            </Button>
          }
        />

        <Row className="g-3 mb-4">
          <Col md={3} sm={6}>
            <StatCard
              label="Latest reading"
              icon={Activity}
              value={latest ? `${latest.systolic}/${latest.diastolic}` : '—'}
              sub={latest ? relativeDays(latest.recorded_at) : 'No readings yet'}
            />
          </Col>
          <Col md={3} sm={6}>
            <StatCard
              label={`${TREND_WINDOW_DAYS}-day average`}
              icon={Heart}
              value={trend?.avg_systolic ? `${Math.round(trend.avg_systolic)}/${Math.round(trend.avg_diastolic)}` : '—'}
              sub={`Based on ${trend?.reading_count || 0} readings`}
            />
          </Col>
          <Col md={3} sm={6}>
            <StatCard label="Status" icon={TrendingUp}>
              <div className="mt-2">
                <StatusPill status={trend?.status || 'no_data'} />
              </div>
            </StatCard>
          </Col>
          <Col md={3} sm={6}>
            <StatCard
              label="Unread alerts"
              icon={Bell}
              value={alertsError ? '—' : unreadAlerts}
              sub={alertsError ? 'Could not load alerts' : undefined}
            />
          </Col>
        </Row>

        {alertsError && (
          <Alert variant="warning" role="alert">
            The dashboard loaded, but the alert count could not be loaded. Open Alerts to retry.
          </Alert>
        )}

        <Row className="g-3">
          <Col lg={7}>
            <Panel
              title="Recent readings"
              description="Your latest blood pressure logs."
              action={
                <Button variant="link" className="hs-link d-flex align-items-center gap-1 p-0 text-decoration-none" onClick={() => navigate('/readings')}>
                  View all <ArrowRight size={14} />
                </Button>
              }
            >
              {readings.length === 0 ? (
                <p className="hs-subtitle mb-0">No readings logged yet.</p>
              ) : (
                readings.map((reading) => {
                  const info = statusInfo(reading.status);
                  return (
                    <DataRow
                      key={reading.reading_id}
                      accent={info.accent}
                      trailing={<StatusPill status={reading.status} />}
                    >
                      <div className="hs-reading-value">
                        {reading.systolic}/{reading.diastolic} <span className="hs-reading-unit">mmHg</span>
                      </div>
                      <div className="hs-reading-meta">{formatDateTime(reading.recorded_at)}</div>
                    </DataRow>
                  );
                })
              )}
            </Panel>
          </Col>

          <Col lg={5}>
            <Panel
              title="Reading distribution"
              description="Breakdown of your readings by classification."
              className="h-100"
            >
              {distribution.length === 0 ? (
                <p className="hs-subtitle mb-0">No data to display yet.</p>
              ) : (
                <div className="hs-donut">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart
                      role="img"
                      title="Reading distribution chart"
                      desc={`${summary.total} readings: ${distribution
                        .map((entry) => `${entry.value} ${entry.name.toLowerCase()}`)
                        .join(', ')}.`}
                    >
                      <Pie data={distribution} dataKey="value" innerRadius={70} outerRadius={100} paddingAngle={distribution.length > 1 ? 2 : 0}>
                        {distribution.map((entry) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="hs-donut-centre">
                    <div className="hs-donut-total">{summary.total}</div>
                    <div className="hs-reading-meta justify-content-center">Total</div>
                  </div>
                </div>
              )}
            </Panel>
          </Col>
        </Row>

        {(loadingRecs || recommendations.length > 0 || recsError) && (
          <Panel
            className="mt-3"
            title={
              <span className="d-flex align-items-center gap-2">
                <Lightbulb size={18} color="var(--hs-teal)" /> Recommendations for you
              </span>
            }
          >
            {loadingRecs ? (
              <Loader size="sm" className="py-3" />
            ) : recsError && recommendations.length === 0 ? (
              <ErrorState
                message="Could not load your recommendations."
                onRetry={() => refreshRecs().catch(() => {})}
              />
            ) : (
              <>
                {recsError && (
                  <Alert variant="warning" role="alert" className="d-flex align-items-center justify-content-between gap-3">
                    <span>These recommendations may be out of date.</span>
                    <Button variant="outline-warning" size="sm" onClick={() => refreshRecs().catch(() => {})}>
                      Try again
                    </Button>
                  </Alert>
                )}
                {recommendations.slice(0, DASHBOARD_RECOMMENDATIONS).map((rec) => (
                  <RecommendationCard key={rec.recommendation_id} rec={rec} />
                ))}
                <Button variant="link" className="p-0 mt-2" onClick={() => navigate('/recommendations')}>
                  {recommendations.length > DASHBOARD_RECOMMENDATIONS
                    ? `See all ${recommendations.length} recommendations`
                    : 'Open recommendations'}
                </Button>
              </>
            )}
          </Panel>
        )}
      </Container>
    </Layout>
  );
}
