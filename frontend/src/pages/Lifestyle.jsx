import { useCallback, useEffect, useState } from 'react';
import { Container } from 'react-bootstrap';
import {
  ArrowLeft, ArrowRight, Check, Coffee, Cigarette, Droplet, Footprints,
  ListChecks, Moon, Pill, PlusCircle, Utensils, Volume2, Wine,
} from 'lucide-react';
import Layout from '../components/Layout';
import WizardStep from '../components/lifestyle/WizardStep';
import FactorEntryRow from '../components/lifestyle/FactorEntryRow';
import { EmptyState, ErrorState, Loader, Panel } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';
import { useConfirm } from '../context/ConfirmContext';
import { createFactor, deleteFactor, getMyFactors } from '../api/factors';
import { errorMessage } from '../utils/format';

const DAY_MS = 86_400_000;

/**
 * Guided daily check-in. Deliberately one question per screen with large
 * targets and a read-aloud button — many users are older or low-literacy.
 */
const STEPS = [
  { key: 'when', question: 'When is this for?', type: 'when' },
  { key: 'stress_level', question: 'How do you feel today?', type: 'face' },
  { key: 'sleep_hours', question: 'How did you sleep?', type: 'tally', icon: Moon, map: [null, 4, 6, 8] },
  { key: 'salt_intake', question: 'How much salt did you eat?', type: 'tally', icon: Droplet, map: ['none', 'low', 'moderate', 'high'] },
  { key: 'caffeine_intake', question: 'How much coffee or tea did you drink?', type: 'tally', icon: Coffee, map: ['none', 'low', 'moderate', 'high'] },
  { key: 'alcohol_consumed', question: 'Did you drink alcohol?', type: 'bool', icon: Wine },
  { key: 'smoked', question: 'Did you smoke?', type: 'bool', icon: Cigarette },
  { key: 'physical_activity_minutes', question: 'How much did you move or walk today?', type: 'tally', icon: Footprints, map: [0, 15, 30, 60] },
  { key: 'diet_adherence', question: 'Did you eat as your clinic advised?', type: 'bool', icon: Utensils },
  { key: 'medication_taken', question: 'Did you take your medicine?', type: 'bool', icon: Pill },
  { key: 'review', question: 'Save this entry?', type: 'review' },
];

const FACTOR_KEYS = STEPS.map((step) => step.key).filter((key) => key !== 'when' && key !== 'review');

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

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
      const loggedDate = answers.when === 'yesterday' ? new Date(Date.now() - DAY_MS) : new Date();
      const payload = Object.fromEntries(FACTOR_KEYS.map((key) => [key, answers[key] ?? null]));

      await createFactor({ ...payload, logged_date: loggedDate.toISOString().slice(0, 10) });
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
      <Container fluid className="px-0" style={{ maxWidth: 640 }}>
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
                className="hs-nav-btn"
                onClick={goBack}
                disabled={stepIndex === 0}
                style={{ visibility: stepIndex === 0 ? 'hidden' : 'visible' }}
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
