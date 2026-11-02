import axios from 'axios';
import { clearAccessToken, getAccessToken, setAccessToken } from './tokenStorage';

// Default to the page's own hostname. The refresh cookie is SameSite, and
// "localhost" and "127.0.0.1" count as different sites, so the app and the API
// have to be opened on the same one. Set VITE_API_BASE_URL for anything else.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
const TIMEOUT_MS = 20_000;
const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh'];

// Sent with every request so the API groups readings by the user's own
// calendar day rather than the UTC day.
const TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

const apiClient = axios.create({ baseURL: API_BASE_URL, timeout: TIMEOUT_MS, withCredentials: true });

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (TIME_ZONE) config.headers['X-Timezone'] = TIME_ZONE;
  return config;
});

/**
 * Refresh coordination: while one refresh is in flight, everything else that
 * needs one (other 401s, or the page-load session restore) waits for its
 * result instead of each firing its own request.
 */
let refreshPromise = null;

/**
 * Trade the httpOnly refresh cookie for a fresh access token and keep it in
 * memory. Rejects (401) when there is no valid session.
 */
export function refreshSession() {
  if (!refreshPromise) {
    // Bare axios: this call must not go through the 401 interceptor below.
    refreshPromise = axios
      .post(`${API_BASE_URL}/auth/refresh`, null, { withCredentials: true, timeout: TIMEOUT_MS })
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

function redirectToLogin() {
  clearAccessToken();
  // Avoid a redirect loop if we are already sitting on the login screen.
  if (!window.location.pathname.startsWith('/login')) {
    window.location.assign('/login');
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config;
    const isAuthCall = request?.url && AUTH_PATHS.some((path) => request.url.includes(path));

    if (error.response?.status !== 401 || request?._retry || isAuthCall) {
      return Promise.reject(error);
    }

    request._retry = true;
    try {
      const token = await refreshSession();
      request.headers.Authorization = `Bearer ${token}`;
      return apiClient(request);
    } catch (refreshError) {
      redirectToLogin();
      return Promise.reject(refreshError);
    }
  },
);

export default apiClient;
