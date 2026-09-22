import apiClient from './client';

export async function createFactor(payload) {
  const { data } = await apiClient.post('/factors', payload);
  return data;
}

export async function getMyFactors() {
  const { data } = await apiClient.get('/factors/me');
  return data;
}

export async function deleteFactor(factorId) {
  await apiClient.delete(`/factors/${factorId}`);
}
