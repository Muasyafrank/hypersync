import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Container } from 'react-bootstrap';
import {
  ArrowLeft, ArrowRight, Check, ListChecks, PlusCircle, Volume2,
} from 'lucide-react';
import Layout from '../components/Layout';
import WizardStep from '../components/lifestyle/WizardStep';
import FactorEntryRow from '../components/lifestyle/FactorEntryRow';
import { buildFactorPayload, getVisibleSteps } from '../components/lifestyle/steps';
import { EmptyState, ErrorState, Loader, PageHeader, Panel } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useRecommendations } from '../context/RecommendationsContext';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { createFactor, deleteFactor, getMyFactors } from '../api/factors';
import { errorMessage, formatDayMonth, isNotFoundError, toLocalDateInput } from '../utils/format';

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

/**
 * Guided daily check-in: one question per screen, form controls only
 * (radio buttons, a plain number field) — no icons to interpret. One
 * question at a time with large tap targets and a read-aloud button, since
 * that part of the design (built for older/low-literacy users) wasn't the
 * problem. The questions themselves live in components/lifestyle/steps.js.
 */
export default function Lifestyle() {
  const toast = useToast();
  const navigate = useNavigate();
  const {
    dataChanged,
    error: recommendationsError,
    refresh: refreshRecommendations,
  } = useRecommendations();
  const confirm = useConfirm();

  const [view, setView] = useState('wizard'); // 'wizard' | 'history'
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleteFailure, setDeleteFailure] = useState(null);
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const deletingIdsRef = useRef(new Set());
  const tabRefs = useRef({});

  const { data: entries, loading, error, reload } = useAsync(getMyFactors, [], []);

  // Stop any in-progress narration when leaving the page.
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const steps = getVisibleSteps(answers);
  const step = steps[stepIndex];
  const progress = ((stepIndex + 1) / steps.length) * 100;
  const isLastStep = step.type === 'review';

  const setAnswer = useCallback((key, value) => {
    setAnswers((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'medication_prescribed' && value !== true) next.medication_taken = null;
      return next;
    });
  }, []);

  const goNext = useCallback(() => {
    setStepIndex((index) => Math.min(index + 1, steps.length - 1));
  }, [steps.length]);

  const goBack = useCallback(() => {
    setStepIndex((index) => Math.max(index - 1, 0));
  }, []);

  function resetWizard() {
    setAnswers({});
    setStepIndex(0);
  }

  async function handleSave() {
    if (loading) {
      toast.error('Wait for your entry history to finish loading before saving a check-in.');
      return;
    }
    if (error) {
      toast.error('Your entry history could not be loaded. Retry it before saving a check-in.');
      return;
    }

    setSaving(true);
    try {
      // The user's own calendar day (not UTC, which lags Kenya by 3 hours).
      const loggedDate = new Date();
      if (answers.when === 'yesterday') loggedDate.setDate(loggedDate.getDate() - 1);
      const loggedDateValue = toLocalDateInput(loggedDate);
      const payload = buildFactorPayload(answers);

      if (Object.values(payload).every((value) => value === null)) {
        toast.error('Answer at least one question before saving your check-in.');
        return;
      }
      if (entries.some((entry) => entry.logged_date === loggedDateValue)) {
        toast.error(`You already have a check-in for ${loggedDateValue}. Delete it first if you need to replace it.`);
        return;
      }

      await createFactor({ ...payload, logged_date: loggedDateValue });
      const refreshed = await dataChanged(); // recompute the advice from this entry before showing it
      if (refreshed) {
        toast.success('Saved. Your recommendations are up to date.');
      } else {
        toast.warning('Check-in saved, but recommendations could not be refreshed. Open Recommendations to retry.');
      }
      resetWizard();
      navigate('/recommendations', {
        state: refreshed ? { justUpdated: 'lifestyle' } : undefined,
      });
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error('You already have a check-in for that day. Delete it first if you need to replace it.');
      } else {
        toast.error(errorMessage(err, 'Could not save. Please try again.'));
      }
    } finally {
      setSaving(false);
    }
  }

  function handleTabKeyDown(event, index) {
    const lastIndex = 1;
    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = index === lastIndex ? 0 : index + 1;
    if (event.key === 'ArrowLeft') nextIndex = index === 0 ? lastIndex : index - 1;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = lastIndex;
    if (nextIndex === null) return;
    event.preventDefault();
    setView(nextIndex === 0 ? 'wizard' : 'history');
    window.requestAnimationFrame(() => tabRefs.current[nextIndex]?.focus());
  }

  function setDeleting(entryId, pending) {
    const next = new Set(deletingIdsRef.current);
    if (pending) next.add(entryId);
    else next.delete(entryId);
    deletingIdsRef.current = next;
    setDeletingIds(next);
  }

  async function performDelete(entry, alreadyPending = false) {
    const entryId = entry.factor_id;
    if (!alreadyPending) {
      if (deletingIdsRef.current.has(entryId)) return;
      setDeleting(entryId, true);
    }

    try {
      try {
        await deleteFactor(entryId);
      } catch (err) {
        // The desired state is already true if another request or tab removed
        // this check-in first.
        if (!isNotFoundError(err)) throw err;
      }
      setDeleteFailure(null);
      await reload();
      const refreshed = await dataChanged(); // the advice may no longer apply
      if (refreshed) {
        toast.success('Entry deleted, and your recommendations were updated.');
      } else {
        toast.warning('Entry deleted, but recommendations could not be refreshed. Use Try again above to retry.');
      }
    } catch (err) {
      const message = errorMessage(err, 'The server did not delete this entry.');
      setDeleteFailure({ entry, message });
      toast.error(message);
    } finally {
      setDeleting(entryId, false);
    }
  }

  async function handleDelete(entry) {
    const entryId = entry.factor_id;
    if (deletingIdsRef.current.has(entryId)) return;
    setDeleting(entryId, true);

    let confirmed = false;
    try {
      confirmed = await confirm({
        title: 'Delete this entry?',
        message: 'This will be permanently removed.',
        confirmLabel: 'Delete',
        variant: 'danger',
      });
      if (!confirmed) return;
      await performDelete(entry, true);
    } finally {
      if (!confirmed) setDeleting(entryId, false);
    }
  }

  async function retryDelete() {
    if (deleteFailure?.entry) await performDelete(deleteFailure.entry);
  }

  return (
    <Layout>
      <Container fluid className="px-0 hs-page-narrow">
        <PageHeader
          title="Lifestyle check-in"
          subtitle="Record one short daily check-in and review the entries you have saved."
        />

        {recommendationsError && (
          <Alert variant="warning" role="alert" className="d-flex align-items-center justify-content-between gap-3">
            <span>Your recommendations could not be refreshed and may be out of date.</span>
            <Button variant="outline-warning" size="sm" onClick={() => refreshRecommendations().catch(() => {})}>
              Try again
            </Button>
          </Alert>
        )}

        {deleteFailure && (
          <Alert variant="danger" role="alert" className="d-flex align-items-center justify-content-between gap-3">
            <span>
              <strong>Check-in not deleted.</strong>{' '}
              Could not delete the check-in for {formatDayMonth(deleteFailure.entry.logged_date)}. {deleteFailure.message}
            </span>
            <Button
              variant="outline-danger"
              size="sm"
              onClick={retryDelete}
              disabled={deletingIds.has(deleteFailure.entry.factor_id)}
            >
              Try again
            </Button>
          </Alert>
        )}

        {error && (
          <ErrorState message="Could not load your entries, so a new check-in cannot be checked for duplicates safely." onRetry={reload} />
        )}

        <div className="d-flex gap-3 mb-4" role="tablist" aria-label="Lifestyle check-in views">
          <button
            type="button"
            role="tab"
            id="lifestyle-wizard-tab"
            aria-controls="lifestyle-wizard-panel"
            aria-selected={view === 'wizard'}
            tabIndex={view === 'wizard' ? 0 : -1}
            ref={(node) => { tabRefs.current[0] = node; }}
            className={`hs-bigtab${view === 'wizard' ? ' active' : ''}`}
            onClick={() => setView('wizard')}
            onKeyDown={(event) => handleTabKeyDown(event, 0)}
          >
            <PlusCircle size={26} aria-hidden="true" />
            <span>New</span>
          </button>
          <button
            type="button"
            role="tab"
            id="lifestyle-history-tab"
            aria-controls="lifestyle-history-panel"
            aria-selected={view === 'history'}
            tabIndex={view === 'history' ? 0 : -1}
            ref={(node) => { tabRefs.current[1] = node; }}
            className={`hs-bigtab${view === 'history' ? ' active' : ''}`}
            onClick={() => setView('history')}
            onKeyDown={(event) => handleTabKeyDown(event, 1)}
          >
            <ListChecks size={26} aria-hidden="true" />
            <span>History</span>
          </button>
        </div>

        <div
          className="hs-wizard-card"
          role="tabpanel"
          id="lifestyle-wizard-panel"
          aria-labelledby="lifestyle-wizard-tab"
          hidden={view !== 'wizard'}
          tabIndex={0}
        >
          <div
            className="hs-progress-track mb-4"
            role="progressbar"
            aria-valuenow={stepIndex + 1}
            aria-valuemin={1}
            aria-valuemax={steps.length}
            aria-label={`Question ${stepIndex + 1} of ${steps.length}`}
          >
            <div className="hs-progress-fill" style={{ width: `${progress}%` }} />
          </div>

          <div className="d-flex align-items-center justify-content-between mb-4">
            <h2 className="hs-title mb-0 hs-wizard-question">{step.question}</h2>
            <button type="button" className="hs-speaker-btn" onClick={() => speak(step.question)} aria-label="Hear this question">
              <Volume2 size={22} aria-hidden="true" />
            </button>
          </div>

          <WizardStep step={step} answers={answers} setAnswer={setAnswer} onAutoAdvance={goNext} />

          <div className="d-flex justify-content-between align-items-center mt-4">
            <button
              type="button"
              className={`hs-nav-btn${stepIndex === 0 ? ' invisible' : ''}`}
              onClick={goBack}
              disabled={stepIndex === 0}
              aria-label="Previous question"
            >
              <ArrowLeft size={22} aria-hidden="true" />
            </button>

            {isLastStep ? (
              <button
                type="button"
                className="hs-save-btn"
                onClick={handleSave}
                disabled={saving || loading || Boolean(error)}
              >
                <Check size={26} aria-hidden="true" /> {saving ? 'Saving…' : 'Save'}
              </button>
            ) : (
              <button type="button" className="hs-nav-btn hs-nav-btn-primary" onClick={goNext} aria-label="Next question">
                <ArrowRight size={22} aria-hidden="true" />
              </button>
            )}
          </div>

          {!isLastStep && step.type !== 'when' && (
            <div className="text-center mt-3">
              <button type="button" className="hs-skip-btn" onClick={goNext}>Skip this question</button>
            </div>
          )}
        </div>

        <div
          role="tabpanel"
          id="lifestyle-history-panel"
          aria-labelledby="lifestyle-history-tab"
          hidden={view !== 'history'}
          tabIndex={0}
        >
          <Panel title="Your entries">
            {loading ? (
              <Loader />
            ) : error ? null : entries.length === 0 ? (
              <EmptyState
                icon={ListChecks}
                message="No entries yet. Use the New tab to record your first daily check-in."
              />
            ) : (
              entries.map((entry) => (
                <FactorEntryRow
                  key={entry.factor_id}
                  entry={entry}
                  onDelete={() => handleDelete(entry)}
                  deleting={deletingIds.has(entry.factor_id)}
                />
              ))
            )}
          </Panel>
        </div>
      </Container>
    </Layout>
  );
}
