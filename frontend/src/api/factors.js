import apiClient from './client';

export async function createFactor(payload) {
  const response = await apiClient.post('/factors/', payload);
  return response.data;
}

export async function getMyFactors() {
  const response = await apiClient.get('/factors/me');
  return response.data;
}

export async function deleteFactor(factorId) {
  await apiClient.delete(`/factors/${factorId}`);
}