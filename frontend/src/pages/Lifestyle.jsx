import { useCallback, useEffect, useState } from 'react';
import { Container } from 'react-bootstrap';
import {
  ArrowLeft, ArrowRight, Check, ListChecks, PlusCircle, Volume2,
} from 'lucide-react';
import Layout from '../components/Layout';
import WizardStep from '../components/lifestyle/WizardStep';
import FactorEntryRow from '../components/lifestyle/FactorEntryRow';
import { buildFactorPayload, STEPS } from '../components/lifestyle/steps';
import { EmptyState, ErrorState, Loader, Panel } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { createFactor, deleteFactor, getMyFactors } from '../api/factors';
import { errorMessage, toLocalDateInput } from '../utils/format';

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
  const confirm = useConfirm();

  const [view, setView] = useState('wizard'); // 'wizard' | 'history'
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);

  const { data: entries, loading, error, reload } = useAsync(getMyFactors, [], []);

  // Stop any in-progress narration when leaving the page.
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const step = STEPS[stepIndex];
  const progress = ((stepIndex + 1) / STEPS.length) * 100;
  const isLastStep = step.type === 'review';

  const setAnswer = useCallback((key, value) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  }, []);

  const goNext = useCallback(() => {
    setStepIndex((index) => Math.min(index + 1, STEPS.length - 1));
  }, []);

  const goBack = useCallback(() => {
    setStepIndex((index) => Math.max(index - 1, 0));
  }, []);

  function resetWizard() {
    setAnswers({});
    setStepIndex(0);
  }

  async function handleSave() {
    setSaving(true);
    try {
      // The user's own calendar day (not UTC, which lags Kenya by 3 hours).
      const loggedDate = new Date();
      if (answers.when === 'yesterday') loggedDate.setDate(loggedDate.getDate() - 1);

      await createFactor({ ...buildFactorPayload(answers), logged_date: toLocalDateInput(loggedDate) });
      toast.success('Saved!');
      resetWizard();
      await reload();
      setView('history');
    } catch (err) {
      toast.error(errorMessage(err, 'Could not save. Please try again.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(factorId) {
    const confirmed = await confirm({
      title: 'Delete this entry?',
      message: 'This will be permanently removed.',
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      await deleteFactor(factorId);
      toast.success('Deleted.');
      reload();
    } catch (err) {
      toast.error(errorMessage(err, 'Could not delete this entry.'));
    }
  }

  return (
    <Layout>
      <Container fluid className="px-0 hs-page-narrow">
        <div className="d-flex gap-3 mb-4" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={view === 'wizard'}
            className={`hs-bigtab${view === 'wizard' ? ' active' : ''}`}
            onClick={() => setView('wizard')}
          >
            <PlusCircle size={26} />
            <span>New</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'history'}
            className={`hs-bigtab${view === 'history' ? ' active' : ''}`}
            onClick={() => setView('history')}
          >
            <ListChecks size={26} />
            <span>History</span>
          </button>
        </div>

        {view === 'wizard' ? (
          <div className="hs-wizard-card">
            <div
              className="hs-progress-track mb-4"
              role="progressbar"
              aria-valuenow={stepIndex + 1}
              aria-valuemin={1}
              aria-valuemax={STEPS.length}
              aria-label={`Question ${stepIndex + 1} of ${STEPS.length}`}
            >
              <div className="hs-progress-fill" style={{ width: `${progress}%` }} />
            </div>

            <div className="d-flex align-items-center justify-content-between mb-4">
              <h3 className="hs-title mb-0 hs-wizard-question">{step.question}</h3>
              <button type="button" className="hs-speaker-btn" onClick={() => speak(step.question)} aria-label="Hear this question">
                <Volume2 size={22} />
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
                <ArrowLeft size={22} />
              </button>

              {isLastStep ? (
                <button type="button" className="hs-save-btn" onClick={handleSave} disabled={saving}>
                  <Check size={26} /> {saving ? 'Saving…' : 'Save'}
                </button>
              ) : (
                <button type="button" className="hs-nav-btn hs-nav-btn-primary" onClick={goNext} aria-label="Next question">
                  <ArrowRight size={22} />
                </button>
              )}
            </div>

            {!isLastStep && step.type !== 'when' && (
              <div className="text-center mt-3">
                <button type="button" className="hs-skip-btn" onClick={goNext}>Skip this question</button>
              </div>
            )}
          </div>
        ) : (
          <Panel title="Your entries">
            {loading ? (
              <Loader />
            ) : error ? (
              <ErrorState message="Could not load your entries." onRetry={reload} />
            ) : entries.length === 0 ? (
              <EmptyState
                icon={ListChecks}
                message="No entries yet. Use the New tab to record your first daily check-in."
              />
            ) : (
              entries.map((entry) => (
                <FactorEntryRow key={entry.factor_id} entry={entry} onDelete={() => handleDelete(entry.factor_id)} />
              ))
            )}
          </Panel>
        )}
      </Container>
    </Layout>
  );
}
