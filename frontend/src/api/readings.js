import apiClient from './client';

export async function createReading(payload) {
  const { data } = await apiClient.post('/readings', payload);
  return data;
}

export async function getMyReadings({ limit } = {}) {
  const { data } = await apiClient.get('/readings/me', { params: limit ? { limit } : undefined });
  return data;
}

/** Total and per-status counts across all readings, without downloading them. */
export async function getMyReadingSummary() {
  const { data } = await apiClient.get('/readings/me/summary');
  return data;
}

export async function getMyTrend(periodDays) {
  const { data } = await apiClient.get('/readings/me/trend', {
    params: { period_days: periodDays },
  });
  return data;
}

export async function deleteReading(readingId) {
  await apiClient.delete(`/readings/${readingId}`);
}
