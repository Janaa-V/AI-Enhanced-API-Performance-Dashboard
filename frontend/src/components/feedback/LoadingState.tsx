import shared from '../../styles/shared.module.css'
import styles from './LoadingState.module.css'

// Grey bars in place of the content while it loads. Screen readers hear "Loading" once.
export function LoadingState({ rows = 3 }: { rows?: number | undefined }) {
  return (
    <div className={styles.skeleton} role="status">
      <span className={shared.visuallyHidden}>Loading</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className={styles.bar} aria-hidden="true" />
      ))}
    </div>
  )
}
