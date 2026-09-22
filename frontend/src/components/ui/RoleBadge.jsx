import StatusPill from './StatusPill';

const ROLE_COLORS = {
  patient: { bg: '#DCFCE7', text: '#166534' },
  clinician: { bg: '#DBEAFE', text: '#1E40AF' },
  admin: { bg: '#FEF9C3', text: '#854D0E' },
};

const FALLBACK = { bg: '#F1F5F9', text: '#64748B' };

export default function RoleBadge({ role }) {
  return (
    <StatusPill
      size="sm"
      colors={ROLE_COLORS[role] || FALLBACK}
      label={role ? role.charAt(0).toUpperCase() + role.slice(1) : 'Unknown'}
    />
  );
}
