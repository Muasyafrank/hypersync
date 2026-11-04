import { Container } from 'react-bootstrap';
import { Bell, CheckCircle2 } from 'lucide-react';
import Layout from '../components/Layout';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { getMyAlerts } from '../api/alerts';
import { alertAccent } from '../utils/bpStatus';
import { formatDateTime } from '../utils/format';

export default function Alerts() {
  const { data: alerts, loading, error, reload } = useAsync(getMyAlerts, [], []);

  return (
    <Layout>
      <Container fluid className="px-0 hs-page-medium">
        <PageHeader
          title="Alerts"
          subtitle="Notifications raised when your blood pressure trend needs attention."
        />

        <Panel>
          {loading ? (
            <Loader />
          ) : error ? (
            <ErrorState message="Could not load your alerts." onRetry={reload} />
          ) : alerts.length === 0 ? (
            <EmptyState
              icon={Bell}
              message="No alerts yet. You'll see one here if your trend becomes elevated or high."
            />
          ) : (
            alerts.map((alert) => (
              <DataRow
                key={alert.alert_id}
                align="start"
                accent={alertAccent(alert.alert_type)}
                trailing={
                  alert.acknowledged ? (
                    <span className="hs-alert-reviewed">
                      <CheckCircle2 size={14} /> Reviewed
                    </span>
                  ) : null
                }
              >
                <div className="hs-body-text">{alert.message}</div>
                <div className="hs-reading-meta mt-1">{formatDateTime(alert.created_at)}</div>
              </DataRow>
            ))
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
