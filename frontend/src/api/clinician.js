import  apiClient  from "./client";

export async function getPatients() {
    const response = await apiClient.get('/users/',{params:{role: 'patient'}});
    return response.data;
}

export async function getPatientReadings(patientId) {
    const response = await apiClient.get(`/readings/patient/${patientId}`);
    return response.data;
}
export async function getPatientTrend(patientId, periodDays= 30) {
    const response = await apiClient.get(`readings/patient/${patientId}/trend`,{
        params: { period_days: periodDays},
    });
    return response.data;
}