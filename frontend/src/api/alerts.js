import apiClient from './client';

export async function getMyAlerts() {
  const response = await apiClient.get('/alerts/me');
  return response.data;
}

export async function getAllAlerts(unacknowledgedOnly = true) {
  const response = await apiClient.get('/alerts/', {
    params: { unacknowledged_only: unacknowledgedOnly },
  });
  return response.data;
}

export async function acknowledgeAlert(alertId) {
  const response = await apiClient.post(`/alerts/${alertId}/acknowledge`);
  return response.data;
}