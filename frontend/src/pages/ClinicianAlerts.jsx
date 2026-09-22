import { useState } from 'react';
import { Button, Container, Form } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import Layout from '../components/Layout';
import { DataRow, EmptyState, ErrorState, Loader, PageHeader, Panel } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';
import { acknowledgeAlert, getAllAlerts } from '../api/alerts';
import { errorMessage, formatDateTime } from '../utils/format';

const HIGH_ACCENT = '#DC2626';
const ELEVATED_ACCENT = '#CA8A04';

export default function ClinicianAlerts() {
  const navigate = useNavigate();
  const toast = useToast();
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const [pendingId, setPendingId] = useState(null);

  const { data: alerts, loading, error, reload } = useAsync(
    () => getAllAlerts(!showAcknowledged),
    [showAcknowledged],
    [],
  );

  async function handleAcknowledge(alertId) {
    setPendingId(alertId);
    try {
      await acknowledgeAlert(alertId);
      toast.success('Alert acknowledged.');
      await reload();
    } catch (err) {
      toast.error(errorMessage(err, 'Could not acknowledge alert.'));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0">
        <PageHeader
          title="Alert queue"
          subtitle="Patients whose blood pressure trend needs review."
          action={
            <Form.Check
              type="switch"
              id="show-acknowledged"
              label="Show acknowledged"
              checked={showAcknowledged}
              onChange={(event) => setShowAcknowledged(event.target.checked)}
            />
          }
        />

        <Panel>
          {loading ? (
            <Loader />
          ) : error ? (
            <ErrorState message="Could not load the alert queue." onRetry={reload} />
          ) : alerts.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              iconColor="#16A34A"
              message="No unacknowledged alerts. Everything's under control."
            />
          ) : (
            alerts.map((alert) => {
              const isHigh = alert.alert_type?.includes('high');
              return (
                <DataRow
                  key={alert.alert_id}
                  align="start"
                  accent={isHigh ? HIGH_ACCENT : ELEVATED_ACCENT}
                  trailing={
                    !alert.acknowledged && (
                      <Button
                        size="sm"
                        className="btn-hs-primary"
                        disabled={pendingId === alert.alert_id}
                        onClick={() => handleAcknowledge(alert.alert_id)}
                      >
                        {pendingId === alert.alert_id ? 'Saving…' : 'Acknowledge'}
                      </Button>
                    )
                  }
                >
                  <button
                    type="button"
                    className="hs-alert-patient"
                    onClick={() => navigate(`/clinician/patients/${alert.patient_id}`)}
                  >
                    <AlertTriangle size={15} color={isHigh ? HIGH_ACCENT : ELEVATED_ACCENT} />
                    {alert.patient_name || 'Patient'}
                  </button>
                  <div className="hs-alert-message">{alert.message}</div>
                  <div className="hs-reading-meta mt-1">{formatDateTime(alert.created_at)}</div>
                </DataRow>
              );
            })
          )}
        </Panel>
      </Container>
    </Layout>
  );
}
