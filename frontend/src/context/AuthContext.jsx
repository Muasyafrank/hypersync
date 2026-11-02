import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, loginUser, logoutUser } from '../api/auth';
import { refreshSession } from '../api/client';
import { clearAccessToken, purgeLegacyTokens, setAccessToken } from '../api/tokenStorage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore the session on first load. The access token only lives in memory,
  // so a reload starts by trading the httpOnly refresh cookie for a new one.
  useEffect(() => {
    purgeLegacyTokens();
    let active = true;
    refreshSession()
      .then(() => getCurrentUser())
      .then((data) => { if (active) setUser(data); })
      .catch(() => clearAccessToken()) // no valid session: stay logged out
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  /**
   * Exchange credentials for a session. Used by both the login and the
   * registration screens (which log the new patient straight in).
   * Resolves with the signed-in user; rejects on bad credentials.
   */
  const signIn = useCallback(async ({ email, password }) => {
    const { access_token: accessToken } = await loginUser({ email, password });
    // Set before /auth/me so the request interceptor can attach it. (The API
    // also set the refresh cookie on this response.)
    setAccessToken(accessToken);
    const currentUser = await getCurrentUser();
    setUser(currentUser);
    return currentUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      // Best effort: revoke server-side, but always clear locally.
      await logoutUser();
    } catch {
      /* the local session is cleared regardless */
    } finally {
      clearAccessToken();
      setUser(null);
    }
  }, []);

  // Memoised so consumers don't re-render on every provider render.
  const value = useMemo(() => ({ user, signIn, logout, loading }), [user, signIn, logout, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) throw new Error('useAuth must be used inside an <AuthProvider>');
  return context;
}
