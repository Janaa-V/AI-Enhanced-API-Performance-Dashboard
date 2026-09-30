import { formatTime } from '../../lib/format'
import shared from '../../styles/shared.module.css'
import styles from './StaleDataBanner.module.css'

// A refresh failed after a success: the last data stays on screen, labelled with its time,
// instead of being replaced by an error.
export function StaleDataBanner({
  updatedAt,
  message,
  onRetry,
}: {
  updatedAt: number
  message: string
  onRetry: () => void
}) {
  return (
    <div className={styles.banner} role="status">
      <p>
        <span className={styles.label}>
          <span aria-hidden="true">⚠ </span>
          Showing data from {formatTime(updatedAt)}.
        </span>{' '}
        The last refresh failed: {message}
      </p>
      <button type="button" className={shared.button} onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
