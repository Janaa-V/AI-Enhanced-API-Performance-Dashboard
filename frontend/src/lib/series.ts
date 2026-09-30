// Which chart colour each endpoint gets. A colour follows the endpoint, never its rank, so
// switching windows or hiding a series never repaints the others (frontend/README.md, "Palette").

export const SERIES_SLOT_COUNT = 8

// Fixed slots for the demo API's routes. The order was validated for colour-vision
// deficiencies with neighbouring slots next to each other.
const FIXED_SLOTS: Readonly<Record<string, number>> = {
  'GET /demo/users': 1,
  'GET /demo/orders': 2,
  'POST /demo/orders': 3,
  'GET /demo/products': 4,
  'GET /demo/search': 5,
  'GET /demo/reports': 6,
}

const SPARE_SLOTS = [7, 8]

// Slot numbers (1 to 8) for the given series keys. An endpoint without a fixed slot takes a
// spare one, in key order so the result does not depend on the response's order. Past the
// spares it gets null: never a generated ninth colour; the chart draws it in a neutral ink.
export function assignSeriesSlots(keys: readonly string[]): Map<string, number | null> {
  const slots = new Map<string, number | null>()
  const spares = [...SPARE_SLOTS]
  for (const key of [...keys].sort()) {
    slots.set(key, FIXED_SLOTS[key] ?? spares.shift() ?? null)
  }
  return slots
}
