import { useMemo } from 'react'
import { useChartColors } from '../../hooks/useChartColors'
import { useSortState } from '../../hooks/useSortState'
import { endpointKey } from '../../lib/endpoints'
import { formatCount, formatLatency, formatPercent } from '../../lib/format'
import { assignSeriesSlots } from '../../lib/series'
import { sortBy, type SortDirection, type SortValue } from '../../lib/sort'
import type { EndpointMetrics } from '../../models/metrics'
import table from '../../styles/table.module.css'
import styles from './EndpointTable.module.css'
import { SortableHeader } from './SortableHeader'

type Column =
  | 'endpoint'
  | 'total_requests'
  | 'error_rate'
  | 'server_errors'
  | 'client_errors'
  | 'avg_latency_ms'
  | 'p95_latency_ms'

const COLUMNS: { column: Column; label: string; numeric: boolean }[] = [
  { column: 'endpoint', label: 'Endpoint', numeric: false },
  { column: 'total_requests', label: 'Requests', numeric: true },
  { column: 'error_rate', label: 'Error rate', numeric: true },
  { column: 'server_errors', label: '5xx', numeric: true },
  { column: 'client_errors', label: '4xx', numeric: true },
  { column: 'avg_latency_ms', label: 'Average', numeric: true },
  { column: 'p95_latency_ms', label: 'p95', numeric: true },
]

const valueOf =
  (column: Column) =>
  (row: EndpointMetrics): SortValue =>
    column === 'endpoint' ? endpointKey(row) : row[column]

const firstDirection = (column: Column): SortDirection => (column === 'endpoint' ? 'asc' : 'desc')

// The same statistics as the KPI cards, for each method and route. Slowest (p95) first.
export function EndpointTable({ endpoints }: { endpoints: EndpointMetrics[] }) {
  const colors = useChartColors()
  const { sort, sortBy: sortColumn } = useSortState<Column>(
    { column: 'p95_latency_ms', direction: 'desc' },
    firstDirection,
  )
  const rows = useMemo(
    () => sortBy(endpoints, valueOf(sort.column), sort.direction),
    [endpoints, sort],
  )
  const slots = useMemo(() => assignSeriesSlots(endpoints.map(endpointKey)), [endpoints])

  return (
    <div className={table.scroll} tabIndex={0} role="region" aria-label="Endpoints table">
      <table className={table.table}>
        <thead>
          <tr>
            {COLUMNS.map(({ column, label, numeric }) => (
              <SortableHeader
                key={column}
                label={label}
                numeric={numeric}
                active={sort.column === column}
                direction={sort.direction}
                onSort={() => sortColumn(column)}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = endpointKey(row)
            const slot = slots.get(key)
            return (
              <tr key={key}>
                <th scope="row">
                  <span className={styles.endpoint}>
                    {/* The line colour this endpoint has in the latency chart. */}
                    <span
                      className={styles.key}
                      style={{ background: slot ? colors.series[slot - 1] : colors.axis }}
                      aria-hidden="true"
                    />
                    <span className={styles.method}>{row.method}</span>
                    {row.endpoint}
                  </span>
                </th>
                <td className={table.number}>{formatCount(row.total_requests)}</td>
                <td className={table.number}>{formatPercent(row.error_rate)}</td>
                <td className={table.number}>{formatCount(row.server_errors)}</td>
                <td className={table.number}>{formatCount(row.client_errors)}</td>
                <td className={table.number}>{formatLatency(row.avg_latency_ms)}</td>
                <td className={table.number}>{formatLatency(row.p95_latency_ms)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
