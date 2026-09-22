/**
 * Blood-pressure status vocabulary shared across the app.
 *
 * The thresholds here MUST match backend/app/core/bp_classification.py —
 * otherwise the live preview on the "Log reading" screen disagrees with the
 * status the API assigns once the reading is saved.
 */

export const THRESHOLDS = {
  lowSystolic: 90,
  lowDiastolic: 60,
  highSystolic: 150,
  highDiastolic: 90,
  elevatedSystolic: 135,
  elevatedDiastolic: 85,
};

export const STATUS_COLORS = {
  controlled: { bg: '#DCFCE7', text: '#166534', accent: '#16A34A', label: 'Controlled' },
  elevated: { bg: '#FEF9C3', text: '#854D0E', accent: '#EAB308', label: 'Elevated' },
  high: { bg: '#FEE2E2', text: '#991B1B', accent: '#DC2626', label: 'High' },
  low: { bg: '#DBEAFE', text: '#1E40AF', accent: '#2563EB', label: 'Low' },
  no_data: { bg: '#F1F5F9', text: '#64748B', accent: '#94A3B8', label: 'No data' },
};

/** Always returns a usable descriptor, never undefined. */
export function statusInfo(status) {
  return STATUS_COLORS[status] || STATUS_COLORS.no_data;
}

export function classifyBP(systolic, diastolic) {
  if (!systolic || !diastolic) return null;
  if (systolic < THRESHOLDS.lowSystolic || diastolic < THRESHOLDS.lowDiastolic) return 'low';
  if (systolic >= THRESHOLDS.highSystolic || diastolic >= THRESHOLDS.highDiastolic) return 'high';
  if (systolic >= THRESHOLDS.elevatedSystolic || diastolic >= THRESHOLDS.elevatedDiastolic) return 'elevated';
  return 'controlled';
}

/** Short guidance shown alongside a live classification. */
export const STATUS_NOTES = {
  high: "This reading is high. Consider contacting your clinician if it's persistent.",
  elevated: 'This reading is a little elevated — worth keeping an eye on.',
  controlled: 'This reading is within a healthy, controlled range.',
  low: 'This reading is on the low side. Note how you feel alongside it.',
};
