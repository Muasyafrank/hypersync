/** Date/number formatting helpers, so format strings live in one place. */

const DATE_TIME = { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' };
const DATE_ONLY = { month: 'short', day: 'numeric' };
const DATE_FULL = { month: 'short', day: 'numeric', year: 'numeric' };

function toDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value, fallback = '') {
  const date = toDate(value);
  return date ? date.toLocaleString(undefined, DATE_TIME) : fallback;
}

export function formatShortDate(value, fallback = '') {
  const date = toDate(value);
  return date ? date.toLocaleDateString(undefined, DATE_ONLY) : fallback;
}

export function formatFullDate(value, fallback = '') {
  const date = toDate(value);
  return date ? date.toLocaleDateString(undefined, DATE_FULL) : fallback;
}

/** "Today" / "1 day ago" / "5 days ago". */
export function relativeDays(value, fallback = '—') {
  const date = toDate(value);
  if (!date) return fallback;
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return 'Today';
  if (days === 1) return '1 day ago';
  return `${days} days ago`;
}

/** Pluralise a countable noun: pluralise(1, 'reading') -> "1 reading". */
export function pluralise(count, noun, plural = `${noun}s`) {
  return `${count} ${count === 1 ? noun : plural}`;
}

/** Turn an axios error into something safe to show a user. */
export function errorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).filter(Boolean).join(', ') || fallback;
  if (typeof detail === 'string') return detail;
  return fallback;
}

/** Where each role lands after logging in. */
export function roleHome(role) {
  if (role === 'admin') return '/admin';
  if (role === 'clinician') return '/clinician';
  return '/dashboard';
}

/** Input value for <input type="datetime-local"> in the user's own timezone. */
export function toLocalDateTimeInput(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
