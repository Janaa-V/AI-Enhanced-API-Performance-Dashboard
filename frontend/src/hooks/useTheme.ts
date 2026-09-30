import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'

export const THEME_PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system']

// Also read by the inline script in index.html, which applies the theme before the first paint.
export const THEME_STORAGE_KEY = 'dashboard-theme'

function isThemePreference(value: unknown): value is ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference)
}

// Storage can be blocked (private windows, strict settings); the page then simply forgets.
function readStored(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemePreference(stored) ? stored : 'system'
  } catch {
    return 'system'
  }
}

function store(preference: ThemePreference): void {
  try {
    if (preference === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
    else localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // Not remembered; the choice still applies to this visit.
  }
}

// Light, dark or the operating system's choice. tokens.css does the rest: data-theme on <html>
// picks a theme, and without it prefers-color-scheme decides.
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
