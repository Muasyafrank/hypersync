import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, logoutUser } from '../api/auth';
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../api/tokenStorage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }
    let active = true;
    getCurrentUser()
      .then((data) => { if (active) setUser(data); })
      .catch(() => { if (active) clearTokens(); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const login = useCallback((tokenPair, userData) => {
    setTokens(tokenPair);
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    try {
      // Best effort: revoke server-side, but always clear locally.
      if (refreshToken) await logoutUser(refreshToken);
    } catch {
      /* the local session is cleared regardless */
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  // Memoised so consumers don't re-render on every provider render.
  const value = useMemo(() => ({ user, login, logout, loading }), [user, login, logout, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) throw new Error('useAuth must be used inside an <AuthProvider>');
  return context;
}
