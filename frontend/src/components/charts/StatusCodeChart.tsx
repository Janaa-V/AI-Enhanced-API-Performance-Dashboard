import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  LabelList,
  Rectangle,
  Tooltip,
  XAxis,
  YAxis,
  type BarShapeProps,
  type TooltipContentProps,
} from 'recharts'
import { useChartColors, type ChartColors } from '../../hooks/useChartColors'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { statusClass, toStatusClasses, type StatusTone } from '../../lib/chartData'
import { formatCount, formatPercent } from '../../lib/format'
import type { StatusCodeCount } from '../../models/metrics'
import shared from '../../styles/shared.module.css'
import { ChartTable } from './ChartTable'
import styles from './StatusCodeChart.module.css'

// A symbol beside every code, so the class never depends on colour alone.
const TONE_SYMBOLS: Record<StatusTone, string> = {
  success: '✓',
  warning: '!',
  danger: '✕',
  neutral: '·',
}

const CLASS_NAMES: Record<string, string> = {
  '1xx': 'Informational',
  '2xx': 'Success',
  '3xx': 'Redirect',
  '4xx': 'Client error',
  '5xx': 'Server error',
}

const BAR_SIZE = 20
const ROW_HEIGHT = 36

interface BarRow {
  code: string
  // The axis label: symbol and code, such as "✕ 503".
  label: string
  count: number
  share: number
  tone: StatusTone
}

function toneColor(tone: StatusTone, colors: ChartColors): string {
  return tone === 'neutral' ? colors.axis : colors[tone]
}

// How the window's responses split by status code: one thin bar per code, coloured by class.
export function StatusCodeChart({ codes }: { codes: StatusCodeCount[] }) {
  const colors = useChartColors()
  const animate = !usePrefersReducedMotion()
  const groups = useMemo(() => toStatusClasses(codes), [codes])
  const total = groups.reduce((sum, group) => sum + group.count, 0)

  const rows = useMemo<BarRow[]>(
    () =>
      groups.flatMap((group) =>
        group.codes.map((code) => ({
          code: String(code.status_code),
          label: `${TONE_SYMBOLS[group.tone]} ${code.status_code}`,
          count: code.count,
          share: total === 0 ? 0 : code.count / total,
          tone: group.tone,
        })),
      ),
    [groups, total],
  )

  return (
    <figure className={styles.figure}>
      {/* The class totals, as text anyone can read without hovering. */}
      <ul className={styles.classes}>
        {groups.map((group) => (
          <li key={group.statusClass} className={styles.classItem}>
            <span
              className={styles.swatch}
              style={{ background: toneColor(group.tone, colors) }}
              aria-hidden="true"
            />
            <span aria-hidden="true">{TONE_SYMBOLS[group.tone]}</span>
            <span>
              <strong>{group.statusClass}</strong> {CLASS_NAMES[group.statusClass]}:{' '}
              <span className={shared.numeric}>
                {formatCount(group.count)} (
                {formatPercent(total === 0 ? null : group.count / total)})
              </span>
            </span>
          </li>
        ))}
      </ul>
      <div className={styles.chart} aria-hidden="true">
        <BarChart
          data={rows}
          layout="vertical"
          responsive
          width="100%"
          height={rows.length * ROW_HEIGHT + 8}
          margin={{ top: 4, right: 64, bottom: 4, left: 0 }}
          barSize={BAR_SIZE}
          accessibilityLayer={false}
        >
          <XAxis type="number" hide domain={[0, 'dataMax']} />
          <YAxis
            type="category"
            dataKey="label"
            width={64}
            tickLine={false}
            axisLine={false}
            tick={{ fill: colors.textMuted, fontSize: 12 }}
          />
          <Tooltip
            cursor={false}
            isAnimationActive={false}
            content={(props: TooltipContentProps) => <CodeTooltip {...props} />}
          />
          <Bar
            dataKey="count"
            isAnimationActive={animate}
            // Rounded at the data end, square at the baseline.
            shape={(props: BarShapeProps) => (
              <Rectangle
                {...props}
                radius={[0, 4, 4, 0]}
                fill={toneColor((props.payload as BarRow).tone, colors)}
              />
            )}
          >
            <LabelList
              dataKey="count"
              position="right"
              formatter={(value) => formatCount(Number(value))}
              fill={colors.text}
              fontSize={12}
            />
          </Bar>
        </BarChart>
      </div>
      <ChartTable
        caption="Responses by status code"
        columns={['Status code', 'Class', 'Requests', 'Share']}
        rows={rows.map((row) => [
          row.code,
          CLASS_NAMES[statusClass(Number(row.code))] ?? '',
          formatCount(row.count),
          formatPercent(row.share),
        ])}
      />
    </figure>
  )
}

function CodeTooltip({ active, payload }: TooltipContentProps) {
  const row = payload?.[0]?.payload as BarRow | undefined
  if (!active || !row) return null
  return (
    <div className={styles.tooltip}>
      <strong className={shared.numeric}>{formatCount(row.count)} requests</strong>
      <span className={styles.tooltipName}>
        HTTP {row.code} · {formatPercent(row.share)}
      </span>
    </div>
  )
}
