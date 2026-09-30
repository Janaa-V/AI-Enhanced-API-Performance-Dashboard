import { useId } from 'react'
import { THEME_PREFERENCES, useTheme, type ThemePreference } from '../../hooks/useTheme'
import shared from '../../styles/shared.module.css'
import styles from './ThemeToggle.module.css'

const LABELS: Record<ThemePreference, string> = { light: 'Light', dark: 'Dark', system: 'System' }

// Native radio buttons styled as a segmented control: arrow keys move between them.
export function ThemeToggle() {
  const { preference, setPreference } = useTheme()
  const name = useId()
  return (
    <fieldset className={styles.toggle}>
      <legend className={shared.visuallyHidden}>Theme</legend>
      {THEME_PREFERENCES.map((option) => (
        <label key={option} className={styles.option}>
          <input
            type="radio"
            name={name}
            value={option}
            checked={preference === option}
            onChange={() => setPreference(option)}
            className={styles.input}
          />
          {LABELS[option]}
        </label>
      ))}
    </fieldset>
  )
}
