import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { chartAxisMax, chartAxisTicks, formatDailyAverage } from './chart.js';

describe('blood-pressure chart scale', () => {
  it('keeps the ordinary 200 mmHg ceiling when every value fits', () => {
    assert.equal(chartAxisMax([120, 80]), 200);
  });

  it('adds visible headroom above unusually high readings', () => {
    assert.equal(chartAxisMax([200, 100]), 220);
    assert.equal(chartAxisMax([220, 120]), 240);
    assert.equal(chartAxisMax([250, 130]), 260);
    assert.equal(chartAxisMax([260, 140]), 280);
  });

  it('always includes the dynamic maximum as the last tick', () => {
    const ticks = chartAxisTicks(280);
    assert.equal(ticks.at(-1), 280);
    assert.ok(ticks.includes(240));
  });
});

describe('accessible daily values', () => {
  it('does not round a one-decimal API average a second time', () => {
    assert.equal(formatDailyAverage(120.5), '120.5');
    assert.equal(formatDailyAverage(80.5), '80.5');
    assert.equal(formatDailyAverage(120), '120.0');
  });
});
