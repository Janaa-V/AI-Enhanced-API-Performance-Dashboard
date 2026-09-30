import { useMemo } from 'react'
import { useSortState } from '../../hooks/useSortState'
import { statusClass } from '../../lib/chartData'
import { formatLatency, formatTime } from '../../lib/format'
import { sortBy, type SortDirection, type SortValue } from '../../lib/sort'
import type { RecentRequest } from '../../models/metrics'
import table from '../../styles/table.module.css'
import styles from './RecentRequestsTable.module.css'
import { SortableHeader } from './SortableHeader'

type Column = 'started_at' | 'method' | 'endpoint' | 'status_code' | 'latency_ms'

const COLUMNS: { column: Column; label: string; numeric: boolean }[] = [
  { column: 'started_at', label: 'Time', numeric: false },
  { column: 'method', label: 'Method', numeric: false },
  { column: 'endpoint', label: 'Endpoint', numeric: false },
  { column: 'status_code', label: 'Status', numeric: true },
  { column: 'latency_ms', label: 'Latency', numeric: true },
]

// Timestamps sort as numbers: ISO strings with and without fractional seconds do not sort
// correctly as text.
const valueOf =
  (column: Column) =>
  (row: RecentRequest): SortValue =>
    column === 'started_at' ? Date.parse(row.started_at) : row[column]

const firstDirection = (column: Column): SortDirection =>
  column === 'method' || column === 'endpoint' ? 'asc' : 'desc'

// Error statuses carry a symbol and a status text colour, never colour alone.
function StatusCell({ code }: { code: number }) {
  const cls = statusClass(code)
  if (cls === '5xx') return <span className={styles.serverError}>✕ {code}</span>
  if (cls === '4xx') return <span className={styles.clientError}>! {code}</span>
  return <span>{code}</span>
}

// The latest requests in the window, newest first. Times are the viewer's local time.
export function RecentRequestsTable({ requests }: { requests: RecentRequest[] }) {
  const { sort, sortBy: sortColumn } = useSortState<Column>(
    { column: 'started_at', direction: 'desc' },
    firstDirection,
  )
  const rows = useMemo(
    () => sortBy(requests, valueOf(sort.column), sort.direction),
    [requests, sort],
  )

  return (
    <div className={table.scroll} tabIndex={0} role="region" aria-label="Recent requests table">
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
          {rows.map((row) => (
            // The row id is stable across refreshes, so React keeps each row's DOM.
            <tr key={row.id}>
              <td>
                <time dateTime={row.started_at}>{formatTime(row.started_at)}</time>
              </td>
              <td className={styles.method}>{row.method}</td>
              <td>{row.endpoint}</td>
              <td className={table.number}>
                <StatusCell code={row.status_code} />
              </td>
              <td className={table.number}>{formatLatency(row.latency_ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
