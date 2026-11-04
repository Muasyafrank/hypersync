import apiClient from './client';

export async function registerUser(payload) {
  const { data } = await apiClient.post('/auth/register', payload);
  return data;
}

export async function loginUser({ email, password }) {
  // The API's /auth/login is an OAuth2 password flow, so it expects form
  // encoding with the email in the "username" field.
  const form = new URLSearchParams({ username: email, password });
  const { data } = await apiClient.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

/** Revokes the session server-side; the API reads the refresh cookie itself. */
export async function logoutUser() {
  await apiClient.post('/auth/logout');
}

export async function getCurrentUser() {
  const { data } = await apiClient.get('/auth/me');
  return data;
}
