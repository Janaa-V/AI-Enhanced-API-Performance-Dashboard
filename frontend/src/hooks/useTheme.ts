import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'

export const THEME_PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system']

// What a first-time viewer sees. Also the fallback when storage is blocked or holds nonsense.
export const DEFAULT_THEME: ThemePreference = 'dark'

// Also read by the inline script in index.html, which applies the theme before the first paint.
export const THEME_STORAGE_KEY = 'dashboard-theme'

function isThemePreference(value: unknown): value is ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference)
}

// Storage can be blocked (private windows, strict settings); the page then simply forgets.
function readStored(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemePreference(stored) ? stored : DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}

// Every choice is stored, "system" included: with nothing stored the default (dark) applies.
function store(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // Not remembered; the choice still applies to this visit.
  }
}

// Dark by default; light, or the operating system's choice, on request. tokens.css does the
// rest: data-theme on <html> picks a theme, and without it prefers-color-scheme decides.
export function useTheme() {
  const [preference, setPreferenceState] = useState(readStored)

  useEffect(() => {
    const root = document.documentElement
    if (preference === 'system') delete root.dataset.theme
    else root.dataset.theme = preference
  }, [preference])

  const setPreference = useCallback((next: ThemePreference) => {
    store(next)
    setPreferenceState(next)
  }, [])

  return { preference, setPreference }
}
