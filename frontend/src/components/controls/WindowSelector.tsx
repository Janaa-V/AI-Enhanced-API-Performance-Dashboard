import { useId } from 'react'
import { findWindowPreset, WINDOW_PRESETS, type WindowPreset } from '../../models/windows'
import styles from './WindowSelector.module.css'

// A native select: keyboard and screen-reader support come with it.
export function WindowSelector({
  value,
  onChange,
}: {
  value: WindowPreset
  onChange: (preset: WindowPreset) => void
}) {
  const id = useId()
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        Window
      </label>
      <select
        id={id}
        className={styles.select}
        value={value.windowMinutes}
        onChange={(event) => {
          const preset = findWindowPreset(Number(event.target.value))
          if (preset) onChange(preset)
        }}
      >
        {WINDOW_PRESETS.map((preset) => (
          <option key={preset.windowMinutes} value={preset.windowMinutes}>
            {preset.label}
          </option>
        ))}
      </select>
    </div>
  )
}
