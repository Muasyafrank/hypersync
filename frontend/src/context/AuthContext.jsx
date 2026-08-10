import { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser } from '../api/auth';
import { getAccessToken,getRefreshToken,setTokens,clearTokens} from '../api/tokenStorage'

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => {
        clearTokens();
      })
      .finally(() => setLoading(false));
  }, []);

  function login(tokenPair, userData) {
    setTokens(tokenPair);
    setUser(userData);
  }

  async  function logout() {
    const refreshToken = getRefreshToken();
    try{
      if(refreshToken){
        await logoutUser(refreshToken);
      }
    }catch{

    }finally{
      clearTokens();
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}