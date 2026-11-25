import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  beginRecommendationsRefresh,
  completeRecommendationsRefresh,
  createLatestRequestTracker,
  failRecommendationsRefresh,
  INITIAL_RECOMMENDATIONS_STATE,
  resolveLatestRequest,
  SUPERSEDED_REQUEST,
} from './recommendationsState.js';

describe('recommendations request state', () => {
  it('shows a first load and then a background refresh', () => {
    const loading = beginRecommendationsRefresh(INITIAL_RECOMMENDATIONS_STATE);
    assert.equal(loading.status, 'loading');

    const refreshing = beginRecommendationsRefresh({
      ...INITIAL_RECOMMENDATIONS_STATE,
      fetchedAt: new Date('2026-11-25T08:00:00Z'),
    });
    assert.equal(refreshing.status, 'refreshing');
  });

  it('keeps stale items visible when a refresh fails', () => {
    const oldItems = [{ recommendation_id: 'old', message: 'Still useful while offline.' }];
    const failed = failRecommendationsRefresh(
      { ...INITIAL_RECOMMENDATIONS_STATE, items: oldItems, fetchedAt: new Date() },
      new Error('offline'),
    );

    assert.equal(failed.status, 'error');
    assert.deepEqual(failed.items, oldItems);
    assert.equal(failed.error.message, 'offline');
  });

  it('clears a previous error after a successful refresh', () => {
    const complete = completeRecommendationsRefresh([{ recommendation_id: 'new' }]);

    assert.equal(complete.status, 'ready');
    assert.equal(complete.error, null);
    assert.equal(complete.items[0].recommendation_id, 'new');
    assert.ok(complete.fetchedAt instanceof Date);
  });
});

describe('latest-request arbitration', () => {
  it('does not let an older response own the state', () => {
    const tracker = createLatestRequestTracker();
    const older = tracker.begin();
    const newer = tracker.begin();

    assert.equal(tracker.isCurrent(older), false);
    assert.equal(tracker.isCurrent(newer), true);
  });

  it('invalidates work in flight when the patient signs out', () => {
    const tracker = createLatestRequestTracker();
    const request = tracker.begin();
    tracker.invalidate();

    assert.equal(tracker.isCurrent(request), false);
    assert.equal(tracker.getLatestPromise(), null);
  });

  it('keeps the promise belonging to the newest request', () => {
    const tracker = createLatestRequestTracker();
    const older = tracker.begin();
    const olderPromise = Promise.resolve(['older']);
    tracker.setLatestPromise(older, olderPromise);

    const newer = tracker.begin();
    const newerPromise = Promise.resolve(['newer']);
    tracker.setLatestPromise(newer, newerPromise);

    assert.equal(tracker.getLatestPromise(), newerPromise);
  });

  it('resolves a superseded caller from the winning request', async () => {
    const tracker = createLatestRequestTracker();
    const older = tracker.begin();
    const olderRequest = Promise.resolve(SUPERSEDED_REQUEST);
    tracker.setLatestPromise(older, olderRequest);

    const newer = tracker.begin();
    const newerRequest = Promise.resolve(['fresh']);
    tracker.setLatestPromise(newer, newerRequest);

    assert.deepEqual(await resolveLatestRequest(olderRequest, tracker), ['fresh']);
  });

  it('reports the winning request failure to a superseded caller', async () => {
    const tracker = createLatestRequestTracker();
    const older = tracker.begin();
    const olderRequest = Promise.resolve(SUPERSEDED_REQUEST);
    tracker.setLatestPromise(older, olderRequest);

    const newer = tracker.begin();
    const newerRequest = Promise.reject(new Error('network unavailable'));
    tracker.setLatestPromise(newer, newerRequest);

    await assert.rejects(() => resolveLatestRequest(olderRequest, tracker), /network unavailable/);
  });
});
