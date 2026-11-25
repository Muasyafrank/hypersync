/**
 * How the Recommendations tab organises what the API returns.
 *
 * The API gives one ordered list. Each item has a `source`:
 *   "pattern" : worked out from the patient's own readings and log
 *   "model"   : a habit the national survey data supports
 *   "population_model": the survey's population-level estimate
 *   "rule"    : general clinical guidance
 *   "mixed"   : an overflow item combining more than one provenance
 *   "readings": a note about the readings themselves
 *   "system"  : the summary line and nudges (log more, keep going)
 * The first item is always the summary of where the patient stands.
 */

export const GROUPS = [
  { key: 'standing', title: 'Where you stand' },
  { key: 'own', title: 'What your own data shows' },
  { key: 'work', title: 'What to work on' },
  { key: 'notes', title: 'Keep in mind' },
];

function groupOf(item, index) {
  if (index === 0 || item.source === 'readings') return 'standing';
  if (item.source === 'pattern') return 'own';
  if (item.source === 'model' || item.source === 'rule' || item.source === 'mixed') return 'work';
  return 'notes';
}

/** Items split into the groups above, in the API's order. Empty groups are left out. */
export function groupRecommendations(items = []) {
  const buckets = Object.fromEntries(GROUPS.map(({ key }) => [key, []]));
  items.forEach((item, index) => buckets[groupOf(item, index)].push(item));
  return GROUPS.filter(({ key }) => buckets[key].length > 0).map((group) => ({ ...group, items: buckets[group.key] }));
}
