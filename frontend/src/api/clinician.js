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

/** Whether this patient is flagged for a treatment review, and why. Clinicians only. */
export async function getTreatmentReview(patientId) {
  const { data } = await apiClient.get(`/treatment-review/patients/${patientId}`);
  return data;
}

/** Record that a clinician reviewed this patient; pauses the flag for a while. */
export async function markTreatmentReviewed(patientId, note) {
  const { data } = await apiClient.post(`/treatment-review/patients/${patientId}/reviewed`, {
    note: note?.trim() || null,
  });
  return data;
}
