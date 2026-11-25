import { useId, useMemo } from 'react';
import {
  Area, AreaChart, CartesianGrid, Legend, ReferenceArea,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { formatShortDate } from '../utils/format';
import { chartAxisMax, chartAxisTicks, formatDailyAverage } from '../utils/chart';

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
          <span className="hs-chart-tooltip-value">{formatDailyAverage(entry.value)}</span>
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
  const reactId = useId();
  const idPrefix = `hs-${reactId.replace(/:/g, '')}`;
  const dataTableId = `${idPrefix}-trend-data`;
  const systolicGradientId = `${idPrefix}-systolic-gradient`;
  const diastolicGradientId = `${idPrefix}-diastolic-gradient`;

  const data = useMemo(
    () =>
      dailyBreakdown.map((day) => ({
        date: formatShortDate(day.date),
        fullDate: day.date,
        Systolic: day.avg_systolic,
        Diastolic: day.avg_diastolic,
        readingCount: day.reading_count,
      })),
    [dailyBreakdown],
  );

  const axisMax = useMemo(
    () => chartAxisMax(data.flatMap((day) => [day.Systolic, day.Diastolic])),
    [data],
  );

  const axisTicks = useMemo(() => chartAxisTicks(axisMax), [axisMax]);

  if (data.length === 0) return null;

  const chartLabel = `Blood pressure trend chart for ${data.length} days, in millimetres of mercury. Highest plotted value ${formatDailyAverage(
    Math.max(...data.map((day) => day.Systolic)),
  )} systolic and ${formatDailyAverage(Math.max(...data.map((day) => day.Diastolic)))} diastolic.`;

  return (
    <div className="hs-trend-chart">
      <p id={dataTableId} className="hs-chart-summary">
        Daily average systolic and diastolic blood pressure for {data.length} days. Expand the table below for exact values.
      </p>
      <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
          role="img"
          aria-label={chartLabel}
          aria-describedby={dataTableId}
        >
          <defs>
            <linearGradient id={systolicGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SYSTOLIC_COLOR} stopOpacity={0.35} />
              <stop offset="100%" stopColor={SYSTOLIC_COLOR} stopOpacity={0} />
            </linearGradient>
            <linearGradient id={diastolicGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={DIASTOLIC_COLOR} stopOpacity={0.22} />
              <stop offset="100%" stopColor={DIASTOLIC_COLOR} stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="4 6" stroke="#CBD5E1" vertical={false} />
          <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} />
          <YAxis
            stroke="#94A3B8"
            fontSize={12}
            domain={[40, axisMax]}
            ticks={axisTicks}
            tickLine={false}
            axisLine={false}
          />

          {BANDS.map((band) => (
            <ReferenceArea
              key={band.y1}
              y1={band.y1}
              y2={band.y1 === 150 ? axisMax : band.y2}
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
            fill={`url(#${diastolicGradientId})`}
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
            fill={`url(#${systolicGradientId})`}
            dot={{ r: 3, fill: SYSTOLIC_COLOR, strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#FFFFFF' }}
            isAnimationActive={animate}
            animationDuration={700}
          />
        </AreaChart>
      </ResponsiveContainer>
      </div>

      <details className="hs-chart-data">
        <summary>View daily values as a table</summary>
        <div className="hs-chart-table-wrap">
          <table className="hs-chart-data-table">
            <caption>Daily average blood pressure values</caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Average systolic</th>
                <th scope="col">Average diastolic</th>
                <th scope="col">Readings</th>
              </tr>
            </thead>
            <tbody>
              {data.map((day) => (
                <tr key={day.fullDate}>
                  <th scope="row">{day.fullDate}</th>
                  <td>{formatDailyAverage(day.Systolic)} mmHg</td>
                  <td>{formatDailyAverage(day.Diastolic)} mmHg</td>
                  <td>{day.readingCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
