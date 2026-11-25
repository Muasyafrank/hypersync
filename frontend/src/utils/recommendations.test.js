import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { groupRecommendations } from './recommendations.js';

const item = (source, message = source) => ({ recommendation_id: message, source, message });

describe('groupRecommendations', () => {
  it('sorts items into the four groups and keeps the API order inside each', () => {
    const groups = groupRecommendations([
      item('population_model', 'summary'),
      item('readings', 'readings line'),
      item('pattern', 'own 1'),
      item('model', 'habit 1'),
      item('rule', 'habit 2'),
      item('pattern', 'own 2'),
      item('system', 'nudge'),
    ]);
    assert.deepEqual(
      groups.map((g) => [g.key, g.items.map((i) => i.message)]),
      [
        ['standing', ['summary', 'readings line']],
        ['own', ['own 1', 'own 2']],
        ['work', ['habit 1', 'habit 2']],
        ['notes', ['nudge']],
      ],
    );
  });

  it('always puts the first item under "Where you stand", whatever its source', () => {
    for (const source of ['system', 'model', 'population_model', 'rule', 'pattern']) {
      assert.equal(groupRecommendations([item(source)])[0].key, 'standing');
    }
  });

  it('leaves empty groups out', () => {
    assert.deepEqual(groupRecommendations([item('system', 'a'), item('system', 'b')]).map((g) => g.key), ['standing', 'notes']);
  });

  it('copes with nothing at all', () => {
    assert.deepEqual(groupRecommendations([]), []);
    assert.deepEqual(groupRecommendations(undefined), []);
  });

  it('puts an unknown source under "Keep in mind" rather than dropping it', () => {
    const groups = groupRecommendations([item('system', 'first'), item('something-new', 'later')]);
    assert.deepEqual(groups.at(-1).items.map((i) => i.message), ['later']);
  });
});
