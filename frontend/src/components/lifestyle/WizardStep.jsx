import { Check, CheckCircle2, Frown, Meh, Smile, Sun, Sunset, X } from 'lucide-react';

/** Stress options shown on the "How do you feel today?" step. */
const FACES = [
  { value: 'low', Icon: Smile, label: 'Calm', color: '#16A34A' },
  { value: 'moderate', Icon: Meh, label: 'So-so', color: '#CA8A04' },
  { value: 'high', Icon: Frown, label: 'Stressed', color: '#DC2626' },
];

const TALLY_LABELS = ['None', 'A little', 'Some', 'A lot'];

/** Large, high-contrast choice button — the wizard is designed for low-literacy
 *  and older users, so targets are oversized and always paired with an icon. */
export function BigChoice({ Icon, iconColor, label, selected, onClick, badge, badgeColor }) {
  return (
    <button
      type="button"
      className={`hs-choice-btn${selected ? ' selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="hs-choice-icon-wrap">
        <Icon size={40} color={iconColor || (selected ? 'var(--hs-teal)' : 'var(--hs-navy)')} strokeWidth={1.8} />
        {badge && <span className="hs-choice-badge" style={{ backgroundColor: badgeColor }}>{badge}</span>}
      </span>
      <span className="hs-choice-label">{label}</span>
    </button>
  );
}

function WhenStep({ value, onSelect }) {
  return (
    <div className="d-flex gap-3">
      <BigChoice Icon={Sun} label="Today" selected={value !== 'yesterday'} onClick={() => onSelect('today')} />
      <BigChoice Icon={Sunset} label="Yesterday" selected={value === 'yesterday'} onClick={() => onSelect('yesterday')} />
    </div>
  );
}

function FaceStep({ value, onSelect }) {
  return (
    <div className="d-flex gap-3">
      {FACES.map((face) => (
        <BigChoice
          key={face.value}
          Icon={face.Icon}
          iconColor={face.color}
          label={face.label}
          selected={value === face.value}
          onClick={() => onSelect(face.value)}
        />
      ))}
    </div>
  );
}

function TallyStep({ step, value, onSelect }) {
  const StepIcon = step.icon;
  return (
    <div className="row g-2">
      {step.map.map((mapped, index) => (
        <div className="col-6" key={TALLY_LABELS[index]}>
          <button
            type="button"
            className={`hs-tally-btn${value === mapped ? ' selected' : ''}`}
            onClick={() => onSelect(mapped)}
            aria-pressed={value === mapped}
          >
            <span className="hs-tally-symbols">
              {index === 0
                ? <StepIcon size={22} style={{ opacity: 0.3 }} />
                : Array.from({ length: index }, (_, i) => <StepIcon key={i} size={22} />)}
            </span>
            <span className="hs-tally-label">{TALLY_LABELS[index]}</span>
          </button>
        </div>
      ))}
    </div>
  );
}

function BoolStep({ step, value, onSelect }) {
  const StepIcon = step.icon;
  return (
    <div className="d-flex gap-3">
      <BigChoice Icon={StepIcon} badge={<Check size={16} />} badgeColor="#16A34A" label="Yes" selected={value === true} onClick={() => onSelect(true)} />
      <BigChoice Icon={StepIcon} badge={<X size={16} />} badgeColor="#DC2626" label="No" selected={value === false} onClick={() => onSelect(false)} />
    </div>
  );
}

/** Renders the body for whichever wizard step is active. */
export default function WizardStep({ step, answers, setAnswer, onAutoAdvance }) {
  const select = (value) => {
    setAnswer(step.key, value);
    onAutoAdvance();
  };

  switch (step.type) {
    case 'when':
      return <WhenStep value={answers.when} onSelect={select} />;
    case 'face':
      return <FaceStep value={answers[step.key]} onSelect={select} />;
    case 'tally':
      return <TallyStep step={step} value={answers[step.key]} onSelect={select} />;
    case 'bool':
      return <BoolStep step={step} value={answers[step.key]} onSelect={select} />;
    case 'review':
      return (
        <div className="text-center py-3">
          <CheckCircle2 size={56} color="var(--hs-teal)" />
          <p className="hs-subtitle mt-2">Tap Save to record this entry.</p>
        </div>
      );
    default:
      return null;
  }
}
