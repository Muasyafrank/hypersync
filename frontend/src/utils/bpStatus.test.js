import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';
import {
  alertAccent,
  ALERT_ACCENTS,
  classifyBP,
  isVeryHighBP,
  statusInfo,
  THRESHOLDS,
  veryHighSafetyMessage,
} from './bpStatus.js';

describe('classifyBP', () => {
  const cases = [
    [120, 80, 'controlled'],
    [134, 84, 'controlled'],
    [135, 80, 'elevated'], // systolic alone crosses the band
    [120, 85, 'elevated'], // diastolic alone crosses the band
    [149, 89, 'elevated'],
    [150, 80, 'high'],
    [120, 90, 'high'],
    [89, 70, 'low'],
    [110, 59, 'low'],
    [90, 60, 'controlled'],
    [160, 55, 'low'], // low is checked before ordinary high
    [185, 50, 'high'], // very high takes precedence over a conflicting low value
  ];

  for (const [systolic, diastolic, expected] of cases) {
    it(`${systolic}/${diastolic} is ${expected}`, () => {
      assert.equal(classifyBP(systolic, diastolic), expected);
    });
  }

  it('returns null while a value is still missing', () => {
    assert.equal(classifyBP(null, 80), null);
    assert.equal(classifyBP(120, null), null);
  });
});

describe('isVeryHighBP', () => {
  it('uses the internal safety boundary without changing the public band', () => {
    assert.equal(isVeryHighBP(180, 100), true);
    assert.equal(isVeryHighBP(170, 110), true);
    assert.equal(isVeryHighBP(179, 109), false);
    assert.equal(classifyBP(180, 100), 'high');
  });

  it('returns false while a value is missing', () => {
    assert.equal(isVeryHighBP(null, 110), false);
    assert.equal(isVeryHighBP(180, null), false);
  });
});

describe('veryHighSafetyMessage', () => {
  it('builds urgent wording directly from a saved very-high reading', () => {
    const message = veryHighSafetyMessage(185, 115);
    assert.match(message, /185\/115/);
    assert.match(message, /seek urgent medical care/i);
    assert.match(message, /do not rely on this app/i);
  });

  it('returns null for an ordinary reading', () => {
    assert.equal(veryHighSafetyMessage(120, 80), null);
  });
});

describe('statusInfo', () => {
  it('always returns a descriptor, even for unknown statuses', () => {
    assert.equal(statusInfo('high').label, 'High');
    assert.equal(statusInfo('something-new').label, 'No data');
    assert.equal(statusInfo(undefined).label, 'No data');
  });
});

describe('alertAccent', () => {
  it('maps alert types to an accent colour', () => {
    assert.equal(alertAccent('high_trend'), ALERT_ACCENTS.high);
    assert.equal(alertAccent('elevated_trend'), ALERT_ACCENTS.elevated);
    assert.equal(alertAccent(undefined), ALERT_ACCENTS.elevated);
  });
});

// The README's golden rule: the browser preview and the API must classify
// identically. This fails the build if someone changes only one side.
describe('thresholds match backend/app/core/bp_classification.py', () => {
  const source = readFileSync(
    new URL('../../../backend/app/core/bp_classification.py', import.meta.url),
    'utf8',
  );
  const toCamel = (name) =>
    name.toLowerCase().replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());

  const backend = Object.fromEntries(
    [...source.matchAll(/^((?:[A-Z]+_)*(?:SYSTOLIC|DIASTOLIC))\s*=\s*(\d+)/gm)].map(([, name, value]) => [
      toCamel(name),
      Number(value),
    ]),
  );

  it('finds every threshold in the Python file', () => {
    assert.deepEqual(Object.keys(backend).sort(), Object.keys(THRESHOLDS).sort());
  });

  it('has identical values', () => {
    assert.deepEqual(backend, THRESHOLDS);
  });
});
