import apiClient from './client';

export async function createReading(payload) {
    const response = await apiClient.post('/readings', payload);
    return response.data
}
export async function getMyReadings() {
    const response = await apiClient.get('/readings/me');
    return response.data
    
}

export async function getMyTrend(periodDays) {
    const response = await apiClient.get('/readings/me/trend',{
        params:{ period_days: periodDays},
    });
    return response.data;
}

export async function deleteReading(readingId) {
    await apiClient.delete(`/readings/${readingId}`);
}
