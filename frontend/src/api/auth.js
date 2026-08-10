import apiClient from './client';

export async function registerUser(payload) {
  const response = await apiClient.post('/auth/register', payload);
  return response.data;
}

export async function loginUser({ email, password }) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const response = await apiClient.post('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
}

export async function refreshAccessToken(refreshToken) {
  const response = await apiClient.post('/auth/refresh',{ refresh_token:refreshToken});
  return response.data  
}

export async function log(refreshToken) {
  await apiClient.post('/auth/logout',{refresh_token: refreshToken});
  
}

export async function getCurrentUser() {
  const response = await apiClient.get('/auth/me');
  return response.data;
}