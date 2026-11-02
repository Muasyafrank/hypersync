/**
 * Where the access token lives: in memory only.
 *
 * It is gone on reload and is not readable from storage, so a script injected
 * into the page (XSS) cannot walk off with a long-lived credential. The
 * long-lived refresh token is an httpOnly cookie managed by the browser and
 * the API; the page never sees it. On load, AuthContext asks the API for a new
 * access token using that cookie.
 */
let accessToken = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = null;
}

/** Earlier versions kept both tokens in localStorage; remove any left behind. */
export function purgeLegacyTokens() {
  try {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  } catch {
    /* storage unavailable: nothing to purge */
  }
}
