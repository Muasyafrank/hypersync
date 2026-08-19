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
export async function getUser(userId) {
  const response = await apiClient.get(`/users/${userId}`);
  return response.data
}

export async function updateUser(userId,payload) {
  const response = await apiClient.put(`/users/${userId}`,payload);
}
export async function resetPassword(userId,newPassword) {
  await apiClient.post(`/users/${userId}/reset-password`,{new_password: newPassword});
}