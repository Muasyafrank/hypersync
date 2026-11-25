import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { getMyRecommendations } from '../api/recommendations';
import {
  beginRecommendationsRefresh,
  completeRecommendationsRefresh,
  createLatestRequestTracker,
  failRecommendationsRefresh,
  INITIAL_RECOMMENDATIONS_STATE,
  resolveLatestRequest,
  SUPERSEDED_REQUEST,
} from '../utils/recommendationsState';
import { useAuth } from './AuthContext';

const RecommendationsContext = createContext(null);

const CHANNEL_NAME = 'hypersync-data';
const FOCUS_REFETCH_MIN_MS = 10_000; // don't refetch more often than this when the tab regains focus

/**
 * The patient's current recommendations, kept in one place so every screen that
 * shows them (the Dashboard, the Recommendations tab) agrees, and refreshed:
 *
 *   * when the app opens;
 *   * right after the patient saves or deletes a reading or lifestyle entry
 *     (`dataChanged`), including in their OTHER open browser tabs;
 *   * when the tab regains focus, which also catches data entered elsewhere.
 */
export function RecommendationsProvider({ children }) {
  const { user } = useAuth();
  const enabled = user?.role === 'patient';

  const [state, setState] = useState(INITIAL_RECOMMENDATIONS_STATE);
  const [requestTracker] = useState(createLatestRequestTracker);
  const lastFetch = useRef(0);
  const channel = useRef(null);

  const refresh = useCallback(async () => {
    if (!enabled) return null;
    const id = requestTracker.begin();
    lastFetch.current = Date.now();
    setState((s) => beginRecommendationsRefresh(s));

    const request = getMyRecommendations(7).then(
      (items) => {
        if (!requestTracker.isCurrent(id)) return SUPERSEDED_REQUEST;
        setState(completeRecommendationsRefresh(items));
        return items;
      },
      (error) => {
        if (!requestTracker.isCurrent(id)) return SUPERSEDED_REQUEST;
        setState((s) => failRecommendationsRefresh(s, error));
        throw error;
      },
    );
    requestTracker.setLatestPromise(id, request);

    // A slower request may be superseded while it is in flight. In that case,
    // resolve from the winning request rather than reporting a false failure.
    return resolveLatestRequest(request, requestTracker);
  }, [enabled, requestTracker]);

  // Load when a patient signs in; clear everything when they sign out.
  useEffect(() => {
    if (!enabled) {
      requestTracker.invalidate(); // abandon anything in flight
      setState(INITIAL_RECOMMENDATIONS_STATE);
      return;
    }
    refresh().catch(() => {});
  }, [enabled, refresh, requestTracker]);

  // Other tabs and returning focus.
  useEffect(() => {
    if (!enabled) return undefined;

    const refetchIfStale = () => {
      if (document.visibilityState === 'hidden') return;
      if (Date.now() - lastFetch.current >= FOCUS_REFETCH_MIN_MS) refresh().catch(() => {});
    };
    window.addEventListener('focus', refetchIfStale);
    document.addEventListener('visibilitychange', refetchIfStale);

    if (typeof BroadcastChannel !== 'undefined') {
      channel.current = new BroadcastChannel(CHANNEL_NAME);
      channel.current.onmessage = () => refresh().catch(() => {});
    }
    return () => {
      window.removeEventListener('focus', refetchIfStale);
      document.removeEventListener('visibilitychange', refetchIfStale);
      channel.current?.close();
      channel.current = null;
    };
  }, [enabled, refresh, requestTracker]);

  /**
   * Call after a reading or lifestyle entry is saved or deleted. Resolves to true
   * when the advice was recomputed successfully, or false when the refresh failed.
   * It never throws: saving the patient's data already succeeded, and the shared
   * error state lets the Recommendations screen offer a retry.
   */
  const dataChanged = useCallback(async () => {
    channel.current?.postMessage({ type: 'changed' });
    try {
      const items = await refresh();
      return items !== null;
    } catch {
      return false;
    }
  }, [refresh]);

  const value = useMemo(() => ({ ...state, refresh, dataChanged }), [state, refresh, dataChanged]);
  return <RecommendationsContext.Provider value={value}>{children}</RecommendationsContext.Provider>;
}

export function useRecommendations() {
  const context = useContext(RecommendationsContext);
  if (context === null) throw new Error('useRecommendations must be used inside a <RecommendationsProvider>');
  return context;
}
