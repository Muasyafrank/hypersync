import apiClient from './client';

export async function getAllUsers() {
  const { data } = await apiClient.get('/users');
  return data;
}

export async function getUser(userId) {
  const { data } = await apiClient.get(`/users/${userId}`);
  return data;
}

export async function createClinician(payload) {
  const { data } = await apiClient.post('/users/clinicians', payload);
  return data;
}

export async function updateUser(userId, payload) {
  const { data } = await apiClient.put(`/users/${userId}`, payload);
  return data;
}

export async function deleteUser(userId) {
  await apiClient.delete(`/users/${userId}`);
}

export async function resetPassword(userId, newPassword) {
  await apiClient.post(`/users/${userId}/reset-password`, { new_password: newPassword });
}
