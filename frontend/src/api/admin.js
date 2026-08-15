import apiClient from './client';

export async function getAllUsers() {
  const response = await apiClient.get('/users/');
  return response.data;
}

export async function createClinician(payload) {
  const response = await apiClient.post('/users/clinicians', payload);
  return response.data;
}

export async function deleteUser(userId) {
  await apiClient.delete(`/users/${userId}`);
}