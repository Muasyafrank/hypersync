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
const SALT_INTAKE = {
  options: ['none', 'low', 'moderate', 'high'],
  labels: ['Never', 'Not every week', 'Most meals', 'Every meal'],
};

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
  {
    key: 'salt_intake', label: 'Salt', question: 'How often do you add salt to your food?', type: 'choice',
    ...SALT_INTAKE,
  },
  { key: 'caffeine_intake', label: 'Coffee or tea', question: 'How much coffee or tea did you drink?', type: 'choice', ...INTAKE },
  { key: 'alcohol_consumed', label: 'Alcohol', question: 'Have you drunk any alcohol in the last 30 days?', type: 'bool' },
  { key: 'smoked', label: 'Smoked', question: 'Do you currently smoke?', type: 'bool' },
  {
    key: 'physical_activity_minutes', label: 'Activity',
    question: 'On a usual day, how many active minutes do you do, including work, walking, and sport?',
    type: 'number', unit: 'minutes', min: 0, max: 1440, step: 5, placeholder: 'e.g. 60', integer: true,
  },
  {
    key: 'diet_adherence', label: 'Fruit and vegetables',
    question: 'Do you usually eat at least five servings of fruit and vegetables each day?', type: 'bool',
  },
  {
    key: 'medication_prescribed',
    label: 'Medication prescribed',
    question: 'Do you take any medication prescribed by a clinician?',
    type: 'bool',
  },
  {
    key: 'medication_taken', label: 'Medication taken', question: 'Did you take your medication as advised today?',
    type: 'bool', visibleWhen: (answers) => answers.medication_prescribed === true,
  },
  {
    key: 'temperature_feel', label: 'Temperature', question: 'How did the temperature feel today?', type: 'choice',
    options: ['cold', 'comfortable', 'hot'], labels: ['Cold', 'Comfortable', 'Hot'],
  },
  {
    key: 'noise_level', label: 'Noise', question: 'How noisy was your day?', type: 'choice',
    options: ['quiet', 'moderate', 'loud'], labels: ['Quiet', 'Moderate', 'Loud'],
  },
  { key: 'review', label: 'Review', question: 'Save this entry?', type: 'review' },
];

/** Steps that collect a value for the API (everything except 'when' and 'review'). */
export const DATA_STEPS = STEPS.filter((step) => step.type !== 'when' && step.type !== 'review');

/** Steps currently relevant to the answers given so far. */
export function getVisibleSteps(answers) {
  return STEPS.filter((step) => !step.visibleWhen || step.visibleWhen(answers));
}

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
