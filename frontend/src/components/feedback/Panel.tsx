import { useId, type ReactNode } from 'react'
import { EmptyState } from './EmptyState'
import { ErrorState, type ErrorInfo } from './ErrorState'
import { LoadingState } from './LoadingState'
import styles from './Panel.module.css'

export type PanelStatus = 'loading' | 'error' | 'empty' | 'ready'

interface PanelProps {
  title: string
  status: PanelStatus
  error?: ErrorInfo | null
  onRetry?: () => void
  // Shown instead of the default empty message.
  emptyMessage?: ReactNode
  // Skeleton rows while loading, roughly the height of the content, so the layout does not jump.
  loadingRows?: number
  // Controls in the heading row, such as a metric toggle.
  actions?: ReactNode
  // Rendered only when status is 'ready'.
  children: ReactNode
}

// The frame every dashboard section uses. It picks what to show from the status, so every
// section handles loading, error, empty and ready the same way.
export function Panel({
  title,
  status,
  error,
  onRetry,
  emptyMessage,
  loadingRows,
  actions,
  children,
}: PanelProps) {
  const headingId = useId()
  return (
    <section className={styles.panel} aria-labelledby={headingId}>
      <div className={styles.heading}>
        <h2 id={headingId} className={styles.title}>
          {title}
        </h2>
        {actions && status === 'ready' && <div className={styles.actions}>{actions}</div>}
      </div>
      <div className={styles.body}>
        {status === 'loading' && <LoadingState rows={loadingRows} />}
        {status === 'error' && <ErrorState error={error} onRetry={onRetry} />}
        {status === 'empty' && <EmptyState>{emptyMessage}</EmptyState>}
        {status === 'ready' && children}
      </div>
    </section>
  )
}
