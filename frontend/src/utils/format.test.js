// Pin the timezone before any Date is created: the date helpers are about the
// difference between the user's day and the UTC day, which only shows up away
// from UTC. Nairobi is UTC+3 with no daylight saving.
process.env.TZ = 'Africa/Nairobi';

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  capitalize,
  errorMessage,
  formatDayMonth,
  formatFullDate,
  formatShortDate,
  formatTime,
  measurementFlags,
  NETWORK_ERROR_MESSAGE,
  pluralise,
  relativeDays,
  roleHome,
  toLocalDateInput,
  toLocalDateTimeInput,
  toTriState,
} from './format.js';

describe('errorMessage', () => {
  it('prefers the server detail string', () => {
    assert.equal(errorMessage({ response: { data: { detail: 'Email already registered' } } }), 'Email already registered');
  });

  it('joins FastAPI validation messages', () => {
    const err = { response: { data: { detail: [{ msg: 'Field required' }, { msg: 'Too short' }] } } };
    assert.equal(errorMessage(err), 'Field required, Too short');
  });

  it('explains a network failure instead of blaming the input', () => {
    assert.equal(errorMessage({ request: {} }, 'Could not save.'), NETWORK_ERROR_MESSAGE);
  });

  it('falls back when the error carries no detail', () => {
    assert.equal(errorMessage({ response: { status: 500, data: 'Internal Server Error' } }, 'Could not save.'), 'Could not save.');
    assert.equal(errorMessage(undefined, 'Could not save.'), 'Could not save.');
  });
});

describe('local dates', () => {
  // 01:30 on 29 Oct in Nairobi is still 28 Oct in UTC.
  const lateNight = new Date('2026-10-28T22:30:00Z');

  it('toLocalDateInput uses the user\'s calendar day, not the UTC day', () => {
    assert.equal(lateNight.toISOString().slice(0, 10), '2026-10-28'); // the trap
    assert.equal(toLocalDateInput(lateNight), '2026-10-29');
  });

  it('toLocalDateTimeInput matches the datetime-local format', () => {
    assert.equal(toLocalDateTimeInput(lateNight), '2026-10-29T01:30');
  });
});

describe('small helpers', () => {
  it('pluralise', () => {
    assert.equal(pluralise(1, 'reading'), '1 reading');
    assert.equal(pluralise(0, 'reading'), '0 readings');
    assert.equal(pluralise(2, 'entry', 'entries'), '2 entries');
  });

  it('capitalize', () => {
    assert.equal(capitalize('clinician'), 'Clinician');
    assert.equal(capitalize(''), '');
    assert.equal(capitalize(undefined), '');
  });

  it('roleHome', () => {
    assert.equal(roleHome('admin'), '/admin');
    assert.equal(roleHome('clinician'), '/clinician');
    assert.equal(roleHome('patient'), '/dashboard');
  });

  it('relativeDays', () => {
    assert.equal(relativeDays(new Date()), 'Today');
    assert.equal(relativeDays(new Date(Date.now() - 3 * 86_400_000)), '3 days ago');
    assert.equal(relativeDays(null), '—');
  });
});

describe('optional yes/no answers', () => {
  it('toTriState maps the select values, keeping "not sure" as null', () => {
    assert.equal(toTriState('yes'), true);
    assert.equal(toTriState('no'), false);
    assert.equal(toTriState(''), null);
    assert.equal(toTriState(undefined), null);
  });
});

describe('measurementFlags', () => {
  it('flags only conditions that can inflate a reading', () => {
    assert.deepEqual(measurementFlags({ rested_before: false }), ['Not rested first']);
    assert.deepEqual(measurementFlags({ stimulant_before: true }), ['Soon after coffee, tea, smoking or exercise']);
    assert.equal(measurementFlags({ rested_before: false, stimulant_before: true }).length, 2);
  });

  it('does not flag good or unanswered conditions', () => {
    assert.deepEqual(measurementFlags({ rested_before: true, stimulant_before: false }), []);
    assert.deepEqual(measurementFlags({ rested_before: null, stimulant_before: null }), []);
    assert.deepEqual(measurementFlags(undefined), []);
  });
});

describe('formatDayMonth', () => {
  it('reads an ISO date as a calendar day, whatever the timezone', () => {
    const text = formatDayMonth('2026-10-20');
    assert.match(text, /20/);
    assert.match(text, /Oct/);
  });

  it('falls back on missing or malformed input', () => {
    assert.equal(formatDayMonth(undefined, '—'), '—');
    assert.equal(formatDayMonth('not-a-date', '—'), '—');
  });

  it('does not shift an API date-only value in a UTC-negative timezone', () => {
    const previous = process.env.TZ;
    process.env.TZ = 'America/New_York';
    try {
      assert.match(formatShortDate('2026-10-20'), /20/);
      assert.match(formatFullDate('2026-10-20'), /20/);
      assert.doesNotMatch(formatShortDate('2026-10-20'), /19/);
    } finally {
      process.env.TZ = previous;
    }
  });
});

describe('formatTime', () => {
  it('shows just the clock time in the user\'s timezone', () => {
    // 11:32 UTC is 14:32 in Nairobi (UTC+3, set at the top of this file); the format follows the user's locale.
    assert.match(formatTime(new Date('2026-11-18T11:32:00Z')), /14[:.]32|0?2[:.]32\s?pm/i);
  });

  it('falls back when there is no date', () => {
    assert.equal(formatTime(null, '—'), '—');
  });
});
