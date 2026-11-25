/** Pure state transitions for the shared recommendations request. */

export const SUPERSEDED_REQUEST = Symbol('recommendations-request-superseded');

export const INITIAL_RECOMMENDATIONS_STATE = Object.freeze({
  items: [],
  status: 'idle',
  error: null,
  fetchedAt: null,
});

/**
 * Give every request an increasing ID. Only the newest request may update the
 * shared state, so a slow response cannot overwrite a newer one.
 */
export function createLatestRequestTracker() {
  let latest = 0;
  let latestPromise = null;
  return {
    begin() {
      latest += 1;
      latestPromise = null;
      return latest;
    },
    isCurrent(id) {
      return id === latest;
    },
    setLatestPromise(id, promise) {
      if (id === latest) latestPromise = promise;
    },
    getLatestPromise() {
      return latestPromise;
    },
    invalidate() {
      latest += 1;
      latestPromise = null;
    },
  };
}

/**
 * Wait for the request that actually owns the state.
 *
 * A slow request can be superseded while it is in flight. Its caller should
 * receive the winning request's result, not a false "refresh failed" signal.
 */
export async function resolveLatestRequest(request, tracker) {
  let result = await request;
  while (result === SUPERSEDED_REQUEST) {
    const winner = tracker.getLatestPromise();
    if (!winner) return null;
    result = await winner;
  }
  return result;
}

export function beginRecommendationsRefresh(state) {
  return {
    ...state,
    status: state.fetchedAt ? 'refreshing' : 'loading',
    error: null,
  };
}

export function completeRecommendationsRefresh(items) {
  return {
    items,
    status: 'ready',
    error: null,
    fetchedAt: new Date(),
  };
}

export function failRecommendationsRefresh(state, error) {
  return {
    ...state,
    status: 'error',
    error,
  };
}
