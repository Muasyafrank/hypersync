/** Pure helpers for the blood-pressure trend chart. */

const MINIMUM_AXIS_MAX = 200;
const AXIS_STEP = 40;

/**
 * Keep the chart's upper bound above every plotted value.
 *
 * The previous fixed 200 mmHg ceiling clipped unusually high readings. The
 * minimum remains 200 for ordinary charts, while 220, 250 and 260 mmHg each
 * receive visible headroom.
 */
export function chartAxisMax(values = []) {
  const numbers = values.map(Number).filter(Number.isFinite);
  const highest = Math.max(...numbers, 0);
  if (highest < MINIMUM_AXIS_MAX) return MINIMUM_AXIS_MAX;
  return Math.ceil((highest + 1) / 20) * 20;
}

/** Readable axis ticks with the dynamic maximum as the final tick. */
export function chartAxisTicks(axisMax) {
  const ticks = [];
  for (let value = 40; value < axisMax; value += AXIS_STEP) ticks.push(value);
  ticks.push(axisMax);
  return ticks;
}

/** Render the API's one-decimal daily average without losing that precision. */
export function formatDailyAverage(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toFixed(1);
}
