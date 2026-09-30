// Sorting for the tables. null ("nothing to measure") always goes last, whichever way the column
// is sorted, so empty rows never crowd the top.
import { LOCALE } from './format'

export type SortDirection = 'asc' | 'desc'

export type SortValue = string | number | null

const collator = new Intl.Collator(LOCALE, { numeric: true })

export function compareValues(a: SortValue, b: SortValue, direction: SortDirection): number {
  if (a === null || b === null) {
    if (a === b) return 0
    return a === null ? 1 : -1
  }
  const order =
    typeof a === 'number' && typeof b === 'number' ? a - b : collator.compare(`${a}`, `${b}`)
  return direction === 'asc' ? order : -order
}

// A sorted copy; the input is never changed. Rows that compare equal keep their order, so sorting
// by one column keeps the backend's order within it.
// Timestamps need a numeric value (Date.parse): ISO strings do not sort correctly as text when
// some have fractional seconds and some do not.
export function sortBy<T>(
  items: readonly T[],
  value: (item: T) => SortValue,
  direction: SortDirection,
): T[] {
  return items.toSorted((a, b) => compareValues(value(a), value(b), direction))
}
