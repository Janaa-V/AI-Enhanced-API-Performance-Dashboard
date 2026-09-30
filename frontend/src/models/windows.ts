// The time windows the dashboard offers. Each one has the same shape as MetricsParams, so a
// preset can be passed straight to fetchMetrics.

export interface WindowPreset {
  label: string
  windowMinutes: number
  bucketMinutes: number
}

// The backend's limits for GET /metrics (backend/app/api/routers/metrics.py). A preset outside
// them would get a 422; windows.test.ts checks every preset against them.
export const LIMITS = { maxWindowMinutes: 1440, maxBucketMinutes: 60, maxBuckets: 288 } as const

// 5 to 24 points per chart: enough to show a trend, few enough to read each bucket.
export const WINDOW_PRESETS = [
  { label: '5 min', windowMinutes: 5, bucketMinutes: 1 },
  { label: '15 min', windowMinutes: 15, bucketMinutes: 1 },
  { label: '1 hour', windowMinutes: 60, bucketMinutes: 5 },
  { label: '6 hours', windowMinutes: 360, bucketMinutes: 15 },
  { label: '24 hours', windowMinutes: 1440, bucketMinutes: 60 },
] as const satisfies readonly WindowPreset[]

export const DEFAULT_WINDOW: WindowPreset = WINDOW_PRESETS[2]

// The preset for a window length, such as one read from the URL; undefined if none matches.
export function findWindowPreset(windowMinutes: number): WindowPreset | undefined {
  return WINDOW_PRESETS.find((preset) => preset.windowMinutes === windowMinutes)
}
