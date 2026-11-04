import { describeAnswer, STEPS } from './steps';

/**
 * One radio-button row, styled as a large tappable block rather than a
 * cramped native radio — keeps the wizard's "big, unambiguous target"
 * intent from before, but as a real form control instead of an icon.
 */
function ChoiceRow({ name, value, label, checked, onChange }) {
  return (
    <label className={`hs-choice-row${checked ? ' selected' : ''}`}>
      <input type="radio" name={name} value={String(value)} checked={checked} onChange={onChange} />
      <span>{label}</span>
    </label>
  );
}

function WhenStep({ value, onSelect }) {
  return (
    <div className="hs-choice-list" role="radiogroup" aria-label="When is this for?">
      <ChoiceRow name="when" label="Today" checked={value !== 'yesterday'} onChange={() => onSelect('today')} />
      <ChoiceRow name="when" label="Yesterday" checked={value === 'yesterday'} onChange={() => onSelect('yesterday')} />
    </div>
  );
}

/** A labelled radio group for a fixed set of options (stress, salt, caffeine). */
function ChoiceStep({ step, value, onSelect }) {
  return (
    <div className="hs-choice-list" role="radiogroup" aria-label={step.question}>
      {step.options.map((option, index) => (
        <ChoiceRow
          key={option}
          name={step.key}
          label={step.labels[index]}
          checked={value === option}
          onChange={() => onSelect(option)}
        />
      ))}
    </div>
  );
}

/** Yes / No as a two-option radio group — no icon, no badge to interpret. */
function BoolStep({ step, value, onSelect }) {
  return (
    <div className="hs-choice-list" role="radiogroup" aria-label={step.question}>
      <ChoiceRow name={step.key} label="Yes" checked={value === true} onChange={() => onSelect(true)} />
      <ChoiceRow name={step.key} label="No" checked={value === false} onChange={() => onSelect(false)} />
    </div>
  );
}

/**
 * A plain number field for sleep hours / activity minutes, replacing the
 * old three-option tally (which could only record 4/6/8 hours, say).
 * Deliberately does NOT auto-advance on every keystroke — the person
 * needs to finish typing a number first, so this relies on the wizard's
 * own Next button instead.
 */
function NumberStep({ step, value, onChange }) {
  return (
    <div className="hs-number-field">
      <input
        type="number"
        inputMode="decimal"
        className="hs-number-input"
        min={step.min}
        max={step.max}
        step={step.step}
        placeholder={step.placeholder}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value === '' ? null : Number(event.target.value))}
        aria-label={step.question}
      />
      <span className="hs-number-unit">{step.unit}</span>
    </div>
  );
}

/** Everything about to be saved, so nothing is a surprise; skipped questions are shown as such. */
function ReviewStep({ answers }) {
  const reviewed = STEPS.filter((step) => step.type !== 'review');
  return (
    <div>
      <dl className="hs-review-list">
        {reviewed.map((step) => {
          const text = describeAnswer(step, answers[step.key]);
          return (
            <div key={step.key} className="hs-review-row">
              <dt>{step.label}</dt>
              <dd className={text ? undefined : 'hs-review-skipped'}>{text ?? 'Skipped'}</dd>
            </div>
          );
        })}
      </dl>
      <p className="hs-subtitle text-center mt-3 mb-0">Tap Save to record this entry.</p>
    </div>
  );
}

/** Renders the body for whichever wizard step is active. */
export default function WizardStep({ step, answers, setAnswer, onAutoAdvance }) {
  // Tapping a radio option both records the answer and moves on —
  // matches how the old icon buttons behaved.
  const selectAndAdvance = (value) => {
    setAnswer(step.key, value);
    onAutoAdvance();
  };

  switch (step.type) {
    case 'when':
      return <WhenStep value={answers.when} onSelect={selectAndAdvance} />;
    case 'choice':
      return <ChoiceStep step={step} value={answers[step.key]} onSelect={selectAndAdvance} />;
    case 'bool':
      return <BoolStep step={step} value={answers[step.key]} onSelect={selectAndAdvance} />;
    case 'number':
      return <NumberStep step={step} value={answers[step.key]} onChange={(value) => setAnswer(step.key, value)} />;
    case 'review':
      return <ReviewStep answers={answers} />;
    default:
      return null;
  }
}
