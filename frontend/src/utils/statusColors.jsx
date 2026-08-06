export const STATUS_COLORS = {
  controlled: { bg: '#DCFCE7', text: '#166534', accent: '#16A34A', label: 'Controlled' },
  elevated: { bg: '#FEF9C3', text: '#854D0E', accent: '#EAB308', label: 'Elevated' },
  high: { bg: '#FEE2E2', text: '#991B1B', accent: '#DC2626', label: 'High' },
  low: { bg: '#DBEAFE', text: '#1E40AF', accent: '#2563EB', label: 'Low' },
  no_data: { bg: '#F1F5F9', text: '#64748B', accent: '#94A3B8', label: 'No Data' },
};

export function statusInfo(status) {
  return STATUS_COLORS[status] || STATUS_COLORS.no_data;
}