/**
 * Definition of the daily lifestyle check-in: one question per screen.
 *
 * Kept apart from the components so the wizard, the review summary and the
 * save payload all read from the same list (and so it can be unit-tested).
 *
 * Step types: 'when' | 'choice' | 'bool' | 'number' | 'review'.
 * `key` of a data step is the field name the API expects.
 */

const INTAKE = { options: ['none', 'low', 'moderate', 'high'], labels: ['None', 'Low', 'Moderate', 'High'] };

export const STEPS = [
  { key: 'when', label: 'For', question: 'When is this for?', type: 'when' },
  {
    key: 'stress_level', label: 'Stress', question: 'What is your stress level today?', type: 'choice',
    options: ['low', 'moderate', 'high'], labels: ['Low', 'Moderate', 'High'],
  },
  {
    key: 'sleep_hours', label: 'Sleep', question: 'How many hours did you sleep?', type: 'number',
    unit: 'hours', min: 0, max: 24, step: 0.5, placeholder: 'e.g. 7',
  },
  { key: 'salt_intake', label: 'Salt', question: 'How much salt did you eat?', type: 'choice', ...INTAKE },
  { key: 'caffeine_intake', label: 'Coffee or tea', question: 'How much coffee or tea did you drink?', type: 'choice', ...INTAKE },
  { key: 'alcohol_consumed', label: 'Alcohol', question: 'Did you drink alcohol?', type: 'bool' },
  { key: 'smoked', label: 'Smoked', question: 'Did you smoke?', type: 'bool' },
  {
    key: 'physical_activity_minutes', label: 'Activity', question: 'How many minutes did you move or walk?', type: 'number',
    unit: 'minutes', min: 0, max: 1440, step: 5, placeholder: 'e.g. 30', integer: true,
  },
  { key: 'diet_adherence', label: 'Diet as advised', question: 'Did you eat as your clinic advised?', type: 'bool' },
  { key: 'medication_taken', label: 'Medicine taken', question: 'Did you take your medicine?', type: 'bool' },
  { key: 'review', label: 'Review', question: 'Save this entry?', type: 'review' },
];

/** Steps that collect a value for the API (everything except 'when' and 'review'). */
export const DATA_STEPS = STEPS.filter((step) => step.type !== 'when' && step.type !== 'review');

/**
 * Clamp a typed number to the field's allowed range and round it if the API
 * expects an integer. Done at save time, not while typing: rounding live would
 * make the field snap mid-keystroke (e.g. typing "27.5").
 */
export function normaliseAnswer(step, value) {
  if (value == null) return null;
  if (step.type !== 'number') return value;
  const clamped = Math.min(Math.max(value, step.min), step.max);
  return step.integer ? Math.round(clamped) : clamped;
}

/** The payload fields for createFactor, one per data step. */
export function buildFactorPayload(answers) {
  return Object.fromEntries(DATA_STEPS.map((step) => [step.key, normaliseAnswer(step, answers[step.key] ?? null)]));
}

/** Human-readable answer for the review screen, or null if the step was skipped. */
export function describeAnswer(step, value) {
  if (step.type === 'when') return value === 'yesterday' ? 'Yesterday' : 'Today';
  if (value == null) return null;
  switch (step.type) {
    case 'choice':
      return step.labels[step.options.indexOf(value)] ?? String(value);
    case 'bool':
      return value ? 'Yes' : 'No';
    case 'number':
      return `${normaliseAnswer(step, value)} ${step.unit}`;
    default:
      return String(value);
  }
}
