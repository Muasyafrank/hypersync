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

export async function refreshAccessToken(refreshToken) {
  const { data } = await apiClient.post('/auth/refresh', { refresh_token: refreshToken });
  return data;
}

export async function logoutUser(refreshToken) {
  await apiClient.post('/auth/logout', { refresh_token: refreshToken });
}

export async function getCurrentUser() {
  const { data } = await apiClient.get('/auth/me');
  return data;
}
