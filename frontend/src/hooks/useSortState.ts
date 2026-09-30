import { useCallback, useState } from 'react'
import type { SortDirection } from '../lib/sort'

export interface SortState<Column extends string> {
  column: Column
  direction: SortDirection
}

// Which column a table is sorted by. Clicking the sorted column flips it; clicking another
// starts that column in its natural direction (numbers largest first, text A to Z).
export function useSortState<Column extends string>(
  initial: SortState<Column>,
  firstDirection: (column: Column) => SortDirection,
) {
  const [sort, setSort] = useState(initial)
  const sortBy = useCallback(
    (column: Column) => {
      setSort((current) =>
        current.column === column
          ? { column, direction: current.direction === 'asc' ? 'desc' : 'asc' }
          : { column, direction: firstDirection(column) },
      )
    },
    [firstDirection],
  )
  return { sort, sortBy }
}
