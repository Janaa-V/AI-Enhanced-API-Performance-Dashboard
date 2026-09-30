import { useCallback, useEffect, useState } from 'react'
import { DEFAULT_WINDOW, findWindowPreset, type WindowPreset } from '../models/windows'

export interface DashboardControls {
  preset: WindowPreset
  autoRefresh: boolean
}

// Read once at startup. Unknown or missing values fall back to the defaults.
export function readControls(search: string): DashboardControls {
  const params = new URLSearchParams(search)
  const minutes = Number(params.get('window'))
  return {
    preset: findWindowPreset(minutes) ?? DEFAULT_WINDOW,
    autoRefresh: params.get('refresh') !== 'off',
  }
}

// Only values that differ from the defaults are written, so the default view has a clean URL.
// Other query parameters are kept.
export function writeControls(search: string, { preset, autoRefresh }: DashboardControls): string {
  const params = new URLSearchParams(search)
  if (preset.windowMinutes === DEFAULT_WINDOW.windowMinutes) params.delete('window')
  else params.set('window', String(preset.windowMinutes))
  if (autoRefresh) params.delete('refresh')
  else params.set('refresh', 'off')
  const query = params.toString()
  return query ? `?${query}` : ''
}

// The selected window and auto-refresh, mirrored in the query string (?window=360&refresh=off)
// so a view can be bookmarked or shared without a router. replaceState, not pushState: changing
// the window should not fill the Back button's history.
export function useDashboardControls() {
  const [controls, setControls] = useState(() => readControls(window.location.search))

  useEffect(() => {
    const { pathname, search, hash } = window.location
    const next = writeControls(search, controls)
    if (next !== search) window.history.replaceState(null, '', `${pathname}${next}${hash}`)
  }, [controls])

  const setPreset = useCallback((preset: WindowPreset) => {
    setControls((current) => ({ ...current, preset }))
  }, [])
  const setAutoRefresh = useCallback((autoRefresh: boolean) => {
    setControls((current) => ({ ...current, autoRefresh }))
  }, [])

  return { ...controls, setPreset, setAutoRefresh }
}
