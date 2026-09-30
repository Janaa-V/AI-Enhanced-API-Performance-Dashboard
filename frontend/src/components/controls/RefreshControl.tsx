import { useNow } from '../../hooks/useNow'
import { formatRelative, formatTime } from '../../lib/format'
import shared from '../../styles/shared.module.css'
import styles from './RefreshControl.module.css'

interface RefreshControlProps {
  // Epoch milliseconds of the data on screen; 0 before the first success.
  updatedAt: number
  isFetching: boolean
  autoRefresh: boolean
  refreshSeconds: number
  onAutoRefreshChange: (autoRefresh: boolean) => void
  onRefresh: () => void
}

export function RefreshControl({
  updatedAt,
  isFetching,
  autoRefresh,
  refreshSeconds,
  onAutoRefreshChange,
  onRefresh,
}: RefreshControlProps) {
  return (
    <div className={styles.refresh}>
      <UpdatedLabel updatedAt={updatedAt} />
      <label className={styles.checkbox}>
        <input
          type="checkbox"
          checked={autoRefresh}
          onChange={(event) => onAutoRefreshChange(event.target.checked)}
        />
        Auto-refresh every {refreshSeconds} s
      </label>
      <button type="button" className={shared.button} onClick={onRefresh} disabled={isFetching}>
        {isFetching ? 'Refreshing…' : 'Refresh now'}
      </button>
    </div>
  )
}

// Its own component, so only this label re-renders every second. Not a live region: a label
// that changes every second would keep interrupting a screen reader.
function UpdatedLabel({ updatedAt }: { updatedAt: number }) {
  const now = useNow()
  if (!updatedAt) return <span className={styles.updated}>Not loaded yet</span>
  return (
    <span className={styles.updated}>
      Updated{' '}
      <time dateTime={new Date(updatedAt).toISOString()} title={formatTime(updatedAt)}>
        {formatRelative(updatedAt, now)}
      </time>
    </span>
  )
}
