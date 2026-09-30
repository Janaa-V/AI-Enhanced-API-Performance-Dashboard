import { useId } from 'react'
import shared from '../../styles/shared.module.css'
import styles from './SegmentedControl.module.css'

// Native radio buttons styled as a segmented control: one choice, arrow keys move between them.
export function SegmentedControl<Value extends string>({
  legend,
  options,
  value,
  onChange,
}: {
  // Read by screen readers; the options are self-explanatory on screen.
  legend: string
  options: readonly { value: Value; label: string }[]
  value: Value
  onChange: (value: Value) => void
}) {
  const name = useId()
  return (
    <fieldset className={styles.group}>
      <legend className={shared.visuallyHidden}>{legend}</legend>
      {options.map((option) => (
        <label key={option.value} className={styles.option}>
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            className={styles.input}
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}
