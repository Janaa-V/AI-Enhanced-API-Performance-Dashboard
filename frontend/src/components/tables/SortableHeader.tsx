import type { SortDirection } from '../../lib/sort'
import table from '../../styles/table.module.css'
import styles from './SortableHeader.module.css'

const ARIA_SORT = { asc: 'ascending', desc: 'descending' } as const

// A column header that sorts its table. aria-sort tells screen readers which column is sorted
// and which way; the arrow shows the same on screen.
export function SortableHeader({
  label,
  active,
  direction,
  numeric = false,
  onSort,
}: {
  label: string
  active: boolean
  direction: SortDirection
  numeric?: boolean
  onSort: () => void
}) {
  const arrow = (
    <span className={active ? styles.arrow : styles.arrowIdle} aria-hidden="true">
      {active && direction === 'asc' ? '▲' : '▼'}
    </span>
  )
  return (
    <th
      scope="col"
      aria-sort={active ? ARIA_SORT[direction] : 'none'}
      className={numeric ? table.number : undefined}
    >
      <button type="button" className={styles.button} onClick={onSort}>
        {/* In a right-aligned column the arrow goes first, so the label lines up with the values. */}
        {numeric && arrow}
        {label}
        {!numeric && arrow}
      </button>
    </th>
  )
}
