import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import { buildFactorPayload, DATA_STEPS, describeAnswer, normaliseAnswer, STEPS } from './steps.js';

const byKey = (key) => STEPS.find((step) => step.key === key);

describe('normaliseAnswer', () => {
  it('rounds integer fields only at save time', () => {
    assert.equal(normaliseAnswer(byKey('physical_activity_minutes'), 27.5), 28);
  });

  it('keeps decimals where the API allows them', () => {
    assert.equal(normaliseAnswer(byKey('sleep_hours'), 7.5), 7.5);
  });

  it('clamps to the range the API accepts', () => {
    assert.equal(normaliseAnswer(byKey('sleep_hours'), 30), 24);
    assert.equal(normaliseAnswer(byKey('sleep_hours'), -2), 0);
    assert.equal(normaliseAnswer(byKey('physical_activity_minutes'), 5000), 1440);
  });

  it('passes other answers through, and keeps skipped ones null', () => {
    assert.equal(normaliseAnswer(byKey('smoked'), false), false);
    assert.equal(normaliseAnswer(byKey('sleep_hours'), undefined), null);
  });
});

describe('buildFactorPayload', () => {
  it('sends every data field, null when skipped', () => {
    const payload = buildFactorPayload({ stress_level: 'low', sleep_hours: 6 });
    assert.equal(payload.stress_level, 'low');
    assert.equal(payload.sleep_hours, 6);
    assert.equal(payload.smoked, null);
    assert.equal('when' in payload, false);
    assert.equal('review' in payload, false);
  });

  // backend/app/routers/environmental_factor.py lists the accepted fields.
  it('covers exactly the fields the API accepts', () => {
    const source = readFileSync(
      new URL('../../../../backend/app/routers/environmental_factor.py', import.meta.url),
      'utf8',
    );
    const block = source.match(/FACTOR_FIELDS\s*=\s*\(([\s\S]*?)\)/)[1];
    const backend = [...block.matchAll(/"([a-z_]+)"/g)].map((match) => match[1]);
    assert.deepEqual(DATA_STEPS.map((step) => step.key).sort(), backend.sort());
  });
});

describe('describeAnswer', () => {
  it('describes each kind of answer', () => {
    assert.equal(describeAnswer(byKey('when'), undefined), 'Today');
    assert.equal(describeAnswer(byKey('when'), 'yesterday'), 'Yesterday');
    assert.equal(describeAnswer(byKey('salt_intake'), 'moderate'), 'Moderate');
    assert.equal(describeAnswer(byKey('smoked'), true), 'Yes');
    assert.equal(describeAnswer(byKey('smoked'), false), 'No');
    assert.equal(describeAnswer(byKey('sleep_hours'), 7.5), '7.5 hours');
    assert.equal(describeAnswer(byKey('temperature_feel'), 'cold'), 'Cold');
    assert.equal(describeAnswer(byKey('noise_level'), 'loud'), 'Loud');
  });

  it('returns null for a skipped question', () => {
    assert.equal(describeAnswer(byKey('smoked'), undefined), null);
    assert.equal(describeAnswer(byKey('sleep_hours'), null), null);
  });
});
