import apiClient from './client';

export async function getMyRecommendations(periodDays = 7) {
  const { data } = await apiClient.get('/recommendations/me', {
    params: { period_days: periodDays },
  });
  return data;
}
