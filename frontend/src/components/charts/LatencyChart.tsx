import { useMemo } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { useChartColors } from '../../hooks/useChartColors'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import {
  LATENCY_METRIC_LABELS,
  OVERALL_KEY,
  toLatencyRows,
  type LatencyMetric,
  type LatencyRow,
} from '../../lib/chartData'
import { formatLatency, formatLatencyAxis, formatTime } from '../../lib/format'
import { assignSeriesSlots } from '../../lib/series'
import type { LatencyTrend, MetricsWindow } from '../../models/metrics'
import shared from '../../styles/shared.module.css'
import { ChartTable } from './ChartTable'
import styles from './LatencyChart.module.css'

const OVERALL_LABEL = 'All endpoints'
const CHART_HEIGHT = 280

interface Series {
  key: string
  label: string
  color: string
}

// Latency over the window: one line per endpoint, plus all endpoints together as the reference.
// Empty buckets are gaps, never 0.
export function LatencyChart({
  trend,
  metric,
  range,
}: {
  trend: LatencyTrend
  metric: LatencyMetric
  range: MetricsWindow
}) {
  const colors = useChartColors()
  const animate = !usePrefersReducedMotion()
  const { rows, seriesKeys } = useMemo(() => toLatencyRows(trend, metric), [trend, metric])

  const series = useMemo<Series[]>(() => {
    const slots = assignSeriesSlots(seriesKeys)
    const endpoints = seriesKeys.map((key) => {
      const slot = slots.get(key)
      return {
        key,
        label: key,
        color: slot ? (colors.series[slot - 1] ?? colors.axis) : colors.axis,
      }
    })
    // All endpoints in the text colour, so it reads as the reference and never competes.
    return [...endpoints, { key: OVERALL_KEY, label: OVERALL_LABEL, color: colors.text }]
  }, [seriesKeys, colors])

  const bucketMs = range.bucket_minutes * 60_000
  const metricLabel = LATENCY_METRIC_LABELS[metric]

  return (
    <figure className={styles.figure}>
      <p className={shared.visuallyHidden}>{describe(rows, metricLabel, range)}</p>
      <div className={styles.chart} aria-hidden="true">
        <LineChart
          data={rows}
          responsive
          width="100%"
          height={CHART_HEIGHT}
          margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
          accessibilityLayer={false}
        >
          <CartesianGrid vertical={false} stroke={colors.grid} />
          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={[Date.parse(range.start), Date.parse(range.end)]}
            tickFormatter={(time: number) => formatTime(time, { seconds: false })}
            stroke={colors.grid}
            tick={{ fill: colors.axis, fontSize: 12 }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tickFormatter={formatLatencyAxis}
            stroke={colors.grid}
            tick={{ fill: colors.axis, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            cursor={{ stroke: colors.axis, strokeWidth: 1 }}
            isAnimationActive={false}
            content={(props: TooltipContentProps) => (
              <LatencyTooltip {...props} rows={rows} series={series} bucketMs={bucketMs} />
            )}
          />
          {series.map(({ key, color }) => (
            <Line
              key={key}
              dataKey={key}
              stroke={color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              type="linear"
              connectNulls={false}
              // A bucket between two empty ones has no line to sit on, so it gets a dot.
              dot={(props) => isolatedDot(props, rows, key, color, colors.surface)}
              activeDot={{ r: 4, stroke: colors.surface, strokeWidth: 2, fill: color }}
              isAnimationActive={animate}
            />
          ))}
        </LineChart>
      </div>
      <figcaption>
        <ul className={styles.legend}>
          {series.map(({ key, label, color }) => (
            <li key={key} className={styles.legendItem}>
              <span className={styles.lineKey} style={{ background: color }} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </figcaption>
      <ChartTable
        caption={`${metricLabel} latency per ${range.bucket_minutes}-minute bucket`}
        columns={['Bucket start', ...series.map((item) => item.label)]}
        rows={rows.map((row) => [
          formatTime(row.time, { seconds: false }),
          ...series.map((item) => formatLatency(row[item.key] ?? null)),
        ])}
      />
    </figure>
  )
}

interface DotProps {
  cx?: number | undefined
  cy?: number | undefined
  index?: number | undefined
}

function isolatedDot(
  { cx, cy, index = 0 }: DotProps,
  rows: LatencyRow[],
  key: string,
  color: string,
  surface: string,
) {
  const value = rows[index]?.[key]
  const neighbourHasValue = [rows[index - 1]?.[key], rows[index + 1]?.[key]].some(
    (neighbour) => neighbour !== null && neighbour !== undefined,
  )
  if (
    value === null ||
    value === undefined ||
    neighbourHasValue ||
    cx === undefined ||
    cy === undefined
  ) {
    return <g key={`${key}-${index}`} />
  }
  return (
    <circle
      key={`${key}-${index}`}
      cx={cx}
      cy={cy}
      r={4}
      fill={color}
      stroke={surface}
      strokeWidth={2}
    />
  )
}

// One readout for every series at the hovered bucket, highest first. Values lead, labels follow.
function LatencyTooltip({
  active,
  label,
  rows,
  series,
  bucketMs,
}: TooltipContentProps & {
  rows: LatencyRow[]
  series: Series[]
  bucketMs: number
}) {
  const row = rows.find((candidate) => candidate.time === label)
  if (!active || !row) return null
  const items = series
    .map((item) => ({ ...item, value: row[item.key] ?? null }))
    .sort((a, b) => (b.value ?? -1) - (a.value ?? -1))
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipTitle}>
        {formatTime(row.time, { seconds: false })}–
        {formatTime(row.time + bucketMs, { seconds: false })}
      </p>
      <ul className={styles.tooltipList}>
        {items.map(({ key, label: name, color, value }) => (
          <li key={key} className={styles.tooltipRow}>
            <span className={styles.lineKey} style={{ background: color }} aria-hidden="true" />
            <strong className={styles.tooltipValue}>
              {value === null ? 'no requests' : formatLatency(value)}
            </strong>
            <span className={styles.tooltipName}>{name}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// A one-sentence summary for screen readers; the table below has every value.
function describe(rows: LatencyRow[], metricLabel: string, range: MetricsWindow): string {
  let peak: LatencyRow | undefined
  for (const row of rows) {
    const value = row[OVERALL_KEY]
    if (value !== null && value !== undefined && (peak?.[OVERALL_KEY] ?? -1) < value) peak = row
  }
  const span = `${formatTime(range.start, { seconds: false })} to ${formatTime(range.end, { seconds: false })}`
  if (!peak) return `No requests between ${span}.`
  return `${metricLabel} latency for all endpoints between ${span}, highest ${formatLatency(
    peak[OVERALL_KEY] ?? null,
  )} at ${formatTime(peak.time, { seconds: false })}.`
}
