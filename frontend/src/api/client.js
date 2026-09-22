import axios from 'axios';
import { clearTokens, getAccessToken, getRefreshToken, setAccessToken } from './tokenStorage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh'];

const apiClient = axios.create({ baseURL: API_BASE_URL, timeout: 20_000 });

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/**
 * Refresh coordination: while one refresh is in flight, other 401s wait for
 * its result instead of each firing their own refresh request.
 */
let refreshPromise = null;

function redirectToLogin() {
  clearTokens();
  // Avoid a redirect loop if we are already sitting on the login screen.
  if (!window.location.pathname.startsWith('/login')) {
    window.location.assign('/login');
  }
}

function refreshAccessToken(refreshToken) {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
      .then(({ data }) => {
        setAccessToken(data.access_token);
        return data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    const isAuthCall = request?.url && AUTH_PATHS.some((path) => request.url.includes(path));

    if (error.response?.status !== 401 || request?._retry || isAuthCall) {
      return Promise.reject(error);
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      redirectToLogin();
      return Promise.reject(error);
    }

    request._retry = true;
    try {
      const token = await refreshAccessToken(refreshToken);
      request.headers.Authorization = `Bearer ${token}`;
      return apiClient(request);
    } catch (refreshError) {
      redirectToLogin();
      return Promise.reject(refreshError);
    }
  },
);

export default apiClient;
