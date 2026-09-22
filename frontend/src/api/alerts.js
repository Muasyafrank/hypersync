import apiClient from './client';

export async function getMyAlerts() {
  const { data } = await apiClient.get('/alerts/me');
  return data;
}

export async function getAllAlerts(unacknowledgedOnly = true) {
  const { data } = await apiClient.get('/alerts', {
    params: { unacknowledged_only: unacknowledgedOnly },
  });
  return data;
}

export async function acknowledgeAlert(alertId) {
  const { data } = await apiClient.post(`/alerts/${alertId}/acknowledge`);
  return data;
}
