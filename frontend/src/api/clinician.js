import apiClient from './client';

/**
 * One request returning every patient with their latest reading and total
 * count. Previously the dashboard fetched the full reading history of every
 * patient separately just to display the most recent one.
 */
export async function getPatientSummaries() {
  const { data } = await apiClient.get('/users/patients/summary');
  return data;
}

export async function getPatient(patientId) {
  const { data } = await apiClient.get(`/users/${patientId}`);
  return data;
}

export async function getPatientReadings(patientId, { limit } = {}) {
  const { data } = await apiClient.get(`/readings/patient/${patientId}`, {
    params: limit ? { limit } : undefined,
  });
  return data;
}

export async function getPatientTrend(patientId, periodDays = 30) {
  const { data } = await apiClient.get(`/readings/patient/${patientId}/trend`, {
    params: { period_days: periodDays },
  });
  return data;
}

export async function getPatientFactors(patientId) {
  const { data } = await apiClient.get(`/factors/patient/${patientId}`);
  return data;
}
