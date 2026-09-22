import { useMemo } from 'react';
import {
  Area, AreaChart, CartesianGrid, Legend, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { formatShortDate } from '../utils/format';

const SYSTOLIC_COLOR = '#0D9488';
const DIASTOLIC_COLOR = '#0F172A';

// Shaded bands matching the classification thresholds.
const BANDS = [
  { y1: 40, y2: 90, fill: '#3B82F6', opacity: 0.06 },
  { y1: 90, y2: 135, fill: '#22C55E', opacity: 0.07 },
  { y1: 135, y2: 150, fill: '#EAB308', opacity: 0.08 },
  { y1: 150, y2: 200, fill: '#EF4444', opacity: 0.07 },
];

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="hs-chart-tooltip">
      <div className="hs-chart-tooltip-date">{label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="hs-chart-tooltip-row">
          <span className="hs-chart-tooltip-dot" style={{ background: entry.color }} />
          <span className="hs-chart-tooltip-label">{entry.dataKey}</span>
          <span className="hs-chart-tooltip-value">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Systolic/diastolic daily averages over time. Shared by the patient Trends
 * page and the clinician patient detail view, which previously each carried
 * their own near-identical chart definition.
 */
export default function BPTrendChart({ dailyBreakdown = [], height = 420, animate = true }) {
  const data = useMemo(
    () =>
      dailyBreakdown.map((day) => ({
        date: formatShortDate(day.date),
        Systolic: day.avg_systolic,
        Diastolic: day.avg_diastolic,
      })),
    [dailyBreakdown],
  );

  if (data.length === 0) return null;

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="hs-sys-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SYSTOLIC_COLOR} stopOpacity={0.35} />
              <stop offset="100%" stopColor={SYSTOLIC_COLOR} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="hs-dia-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={DIASTOLIC_COLOR} stopOpacity={0.22} />
              <stop offset="100%" stopColor={DIASTOLIC_COLOR} stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="4 6" stroke="#CBD5E1" vertical={false} />
          <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} />
          <YAxis
            stroke="#94A3B8"
            fontSize={12}
            domain={[40, 200]}
            ticks={[40, 80, 120, 160, 200]}
            tickLine={false}
            axisLine={false}
          />

          {BANDS.map((band) => (
            <ReferenceArea
              key={band.y1}
              y1={band.y1}
              y2={band.y2}
              fill={band.fill}
              fillOpacity={band.opacity}
              ifOverflow="extendDomain"
            />
          ))}

          <Tooltip content={<ChartTooltip />} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: '0.85rem' }} />

          <Area
            type="monotone"
            dataKey="Diastolic"
            stroke={DIASTOLIC_COLOR}
            strokeWidth={2.5}
            fill="url(#hs-dia-gradient)"
            dot={{ r: 3, fill: DIASTOLIC_COLOR, strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#FFFFFF' }}
            isAnimationActive={animate}
            animationDuration={700}
          />
          <Area
            type="monotone"
            dataKey="Systolic"
            stroke={SYSTOLIC_COLOR}
            strokeWidth={2.5}
            fill="url(#hs-sys-gradient)"
            dot={{ r: 3, fill: SYSTOLIC_COLOR, strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#FFFFFF' }}
            isAnimationActive={animate}
            animationDuration={700}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
