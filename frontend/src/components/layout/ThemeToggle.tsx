import { THEME_PREFERENCES, useTheme, type ThemePreference } from '../../hooks/useTheme'
import { SegmentedControl } from '../controls/SegmentedControl'

const LABELS: Record<ThemePreference, string> = { light: 'Light', dark: 'Dark', system: 'System' }
const OPTIONS = THEME_PREFERENCES.map((value) => ({ value, label: LABELS[value] }))

export function ThemeToggle() {
  const { preference, setPreference } = useTheme()
  return (
    <SegmentedControl
      legend="Theme"
      options={OPTIONS}
      value={preference}
      onChange={setPreference}
    />
  )
}
