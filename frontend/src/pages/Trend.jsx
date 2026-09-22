import { useState } from 'react';
import { Container } from 'react-bootstrap';
import { Activity, Calendar, Heart, TrendingUp } from 'lucide-react';
import Layout from '../components/Layout';
import BPTrendChart from '../components/BPTrendChart';
import PeriodSelect from '../components/PeriodSelect';
import { EmptyState, ErrorState, Loader, PageHeader, Panel, StatCard, StatusPill } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { getMyTrend } from '../api/readings';

export default function Trend() {
  const [periodDays, setPeriodDays] = useState(30);
  const { data: trend, loading, error, reload } = useAsync(() => getMyTrend(periodDays), [periodDays]);

  const hasData = Boolean(trend?.reading_count);

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader
          title="Trends"
          subtitle="Visualise your blood pressure over time."
          action={<PeriodSelect value={periodDays} onChange={setPeriodDays} />}
        />

        {loading ? (
          <Loader className="py-5" />
        ) : error ? (
          <ErrorState message="Could not load your trend data." onRetry={reload} />
        ) : (
          <>
            {hasData && (
              <div className="row g-3 mb-4">
                <div className="col-md-3 col-sm-6">
                  <StatCard label="Avg systolic" icon={Heart} value={trend.avg_systolic ?? '—'} />
                </div>
                <div className="col-md-3 col-sm-6">
                  <StatCard label="Avg diastolic" icon={Activity} value={trend.avg_diastolic ?? '—'} />
                </div>
                <div className="col-md-3 col-sm-6">
                  <StatCard label="Readings" icon={Calendar} value={trend.reading_count} />
                </div>
                <div className="col-md-3 col-sm-6">
                  <StatCard label="Overall status" icon={TrendingUp}>
                    <div className="mt-2">
                      <StatusPill status={trend.status} />
                    </div>
                  </StatCard>
                </div>
              </div>
            )}

            <Panel
              title="Systolic &amp; diastolic history"
              description="Shaded bands mark low, controlled, elevated and high zones."
            >
              {hasData ? (
                <BPTrendChart dailyBreakdown={trend.daily_breakdown} />
              ) : (
                <EmptyState message="No readings in this period yet. Log a few readings to see your trend." />
              )}
            </Panel>
          </>
        )}
      </Container>
    </Layout>
  );
}
