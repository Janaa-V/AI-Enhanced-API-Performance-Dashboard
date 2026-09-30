// Turns raw API values into display text. The API sends unrounded milliseconds, rates as
// fractions, UTC timestamps and null for "nothing to measure"; values stay that way until here.

// One fixed locale, so numbers read the same for every viewer and in tests. Times still use the
// viewer's own time zone.
export const LOCALE = 'en-US'

// Shown for null. Never 0: an empty window has no latency, which is not the same as 0 ms.
export const NO_VALUE = '—'

const numberFormats = new Map<number, Intl.NumberFormat>()

// Rounded to exactly `digits` decimals, with thousands separators.
function formatNumber(value: number, digits: number): string {
  let format = numberFormats.get(digits)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
    numberFormats.set(digits, format)
  }
  return format.format(value)
}

// 4.2 ms, 842 ms, 1.24 s, 12.3 s. The thresholds sit where rounding would otherwise print
// "10.0 ms" or "1,000 ms".
export function formatLatency(ms: number | null): string {
  if (ms === null) return NO_VALUE
  if (ms > 0 && ms < 0.05) return '< 0.1 ms'
  if (ms < 9.95) return `${formatNumber(ms, 1)} ms`
  if (ms < 999.5) return `${formatNumber(ms, 0)} ms`
  const seconds = ms / 1000
  return `${formatNumber(seconds, seconds < 9.995 ? 2 : 1)} s`
}

// Axis ticks are already round numbers, so they need no fixed decimals: 0, 250 ms, 1.5 s.
export function formatLatencyAxis(ms: number): string {
  if (ms === 0) return '0'
  if (ms < 1000) return `${formatCompact(ms)} ms`
  return `${formatCompact(ms / 1000)} s`
}

const compactFormat = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 })

function formatCompact(value: number): string {
  return compactFormat.format(value)
}

// A fraction from 0 to 1 as a percentage: 0.032 -> 3.2 %. A tiny non-zero rate is not shown as
// 0.0 %, so a rare error is never hidden.
export function formatPercent(fraction: number | null): string {
  if (fraction === null) return NO_VALUE
  if (fraction > 0 && fraction < 0.0005) return '< 0.1 %'
  return `${formatNumber(fraction * 100, 1)} %`
}

// 1,234
export function formatCount(count: number | null): string {
  return count === null ? NO_VALUE : formatNumber(count, 0)
}

// Requests per minute: 8.0 req/min, 120 req/min.
export function formatRate(perMinute: number | null): string {
  if (perMinute === null) return NO_VALUE
  return `${formatNumber(perMinute, perMinute < 9.95 ? 1 : 0)} req/min`
}

const timeFormats = {
  withSeconds: new Intl.DateTimeFormat(LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }),
  withoutSeconds: new Intl.DateTimeFormat(LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }),
}

// A UTC timestamp (ISO string or epoch milliseconds) as 24-hour local time: 15:34:05. Charts
// pass epoch milliseconds and leave out the seconds for axis ticks.
export function formatTime(
  time: string | number | null,
  { seconds = true }: { seconds?: boolean } = {},
): string {
  if (time === null) return NO_VALUE
  const date = new Date(time)
  if (Number.isNaN(date.getTime())) return NO_VALUE
  return (seconds ? timeFormats.withSeconds : timeFormats.withoutSeconds).format(date)
}

// How long ago `time` was, for "Updated 12 s ago". `now` is passed in (from useNow) so the
// result is testable and the label updates on the clock's schedule.
export function formatRelative(time: string | number | null, now: number): string {
  if (time === null) return NO_VALUE
  const then = new Date(time).getTime()
  if (Number.isNaN(then)) return NO_VALUE
  // Under 5 seconds, and times slightly ahead of the viewer's clock, read as "just now".
  const seconds = Math.floor((now - then) / 1000)
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds} s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  return `${formatCount(Math.floor(minutes / 60))} h ago`
}
