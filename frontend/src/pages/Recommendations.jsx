import { useEffect, useState } from 'react';
import { Alert, Button, Container } from 'react-bootstrap';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, Heart, Lightbulb, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import RecommendationCard from '../components/RecommendationCard';
import { EmptyState, ErrorState, Loader, PageHeader, Panel } from '../components/ui';
import { useRecommendations } from '../context/RecommendationsContext';
import { formatTime } from '../utils/format';
import { groupRecommendations } from '../utils/recommendations';
import { veryHighSafetyMessage } from '../utils/bpStatus';

const JUST_UPDATED = {
  reading: 'Updated with your new reading.',
  lifestyle: 'Updated with your daily check-in.',
  deleted: 'Updated after your change.',
};

/**
 * The patient's recommendations. They are recomputed from the patient's data whenever it
 * changes (see RecommendationsContext), so what is shown here is current by construction.
 */
export default function Recommendations() {
  const navigate = useNavigate();
  const location = useLocation();
  const { items, status, error: recommendationsError, fetchedAt, refresh } = useRecommendations();

  // The banner after saving something. Held in state, and cleared from the router state so
  // reloading the page doesn't announce an update that happened earlier.
  const [banner, setBanner] = useState(JUST_UPDATED[location.state?.justUpdated] ?? null);
  const [urgentReading, setUrgentReading] = useState(location.state?.urgentReading ?? null);
  useEffect(() => {
    if (location.state?.urgentReading) setUrgentReading(location.state.urgentReading);
  }, [location.state]);
  useEffect(() => {
    if (location.state?.justUpdated) navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    if (recommendationsError) setBanner(null);
  }, [recommendationsError]);

  const groups = groupRecommendations(items);
  const urgentMessage = urgentReading
    ? veryHighSafetyMessage(urgentReading.systolic, urgentReading.diastolic)
    : null;
  const busy = status === 'idle' || status === 'loading' || status === 'refreshing';

  return (
    <Layout>
      <Container fluid className="px-0 hs-page-medium">
        <PageHeader
          title="Recommendations"
          subtitle="Advice from your readings and what you've logged. It updates as soon as you add a reading or a daily check-in."
        />

        {urgentMessage && (
          <Alert variant="danger" role="alert" className="mb-3">
            {urgentMessage}
          </Alert>
        )}

        {/* Announced to screen readers when the advice changes. */}
        <div aria-live="polite">
          {banner && !recommendationsError && (
            <Alert variant="success" dismissible={false} className="d-flex align-items-center justify-content-between">
              <span>{banner}</span>
              <Button variant="link" size="sm" className="p-0" onClick={() => setBanner(null)}>
                Dismiss
              </Button>
            </Alert>
          )}
        </div>

        <div className="hs-rec-updated mb-3">
          <span>
            {status === 'refreshing' ? 'Updating…' : fetchedAt ? `Last updated ${formatTime(fetchedAt)}` : ''}
          </span>
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={() => refresh().catch(() => {})}
            disabled={busy}
            aria-label="Refresh recommendations"
          >
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </Button>
        </div>

        {recommendationsError && items.length > 0 && (
          <Alert variant="danger" role="alert" className="d-flex align-items-center justify-content-between gap-3">
            <span>Could not refresh recommendations, so these may be out of date.</span>
            <Button variant="outline-danger" size="sm" onClick={() => refresh().catch(() => {})}>
              Try again
            </Button>
          </Alert>
        )}

        {busy && items.length === 0 ? (
          <Loader className="py-4" />
        ) : status === 'error' && items.length === 0 ? (
          <ErrorState message="Could not load your recommendations." onRetry={() => refresh().catch(() => {})} />
        ) : groups.length === 0 ? (
          <EmptyState icon={Lightbulb} message="Nothing to show yet. Log a reading and your advice will appear here." />
        ) : (
          groups.map((group) => (
            <Panel key={group.key} title={group.title} className="mb-3">
              {group.items.map((rec) => (
                <RecommendationCard key={rec.recommendation_id} rec={rec} />
              ))}
            </Panel>
          ))
        )}

        <div className="d-flex gap-2 flex-wrap mt-3">
          <Button className="btn-hs-primary" onClick={() => navigate('/readings/new')}>
            <Heart size={15} aria-hidden="true" /> Log a reading
          </Button>
          <Button variant="outline-secondary" onClick={() => navigate('/lifestyle')}>
            <Activity size={15} aria-hidden="true" /> Daily check-in
          </Button>
        </div>

        <p className="hs-reading-meta mt-4 mb-0">
          These are general suggestions. Discuss your readings and health history with your clinician.
        </p>
      </Container>
    </Layout>
  );
}
