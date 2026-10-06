import type { ReactNode } from 'react'
import { API_URL } from '../../config'
import shared from '../../styles/shared.module.css'
import styles from './ErrorState.module.css'

// What the error state needs to know. An ApiError has this shape; components do not import api/.
export interface ErrorInfo {
  kind: string
  message: string
}

const TITLES: Record<string, string> = {
  network: 'Cannot reach the API',
  timeout: 'The API is not responding',
  server: 'The API could not load the metrics',
  validation: 'The API rejected the request',
  rate_limited: 'Too many requests',
}

export function ErrorState({
  error,
  onRetry,
  title,
  children,
}: {
  error?: ErrorInfo | null | undefined
  onRetry?: (() => void) | undefined
  // Replaces the title picked from the error kind, for errors that are not about the metrics.
  title?: string | undefined
  // Extra content under the message, such as a setup hint or a custom retry button.
  children?: ReactNode
}) {
  const kind = error?.kind ?? 'unknown'
  return (
    <div className={styles.error} role="alert">
      <p className={styles.title}>
        <span aria-hidden="true">⚠ </span>
        {title ?? TITLES[kind] ?? 'Something went wrong'}
      </p>
      <p>{error?.message ?? 'The metrics could not be loaded.'}</p>
      {(kind === 'network' || kind === 'timeout') && (
        <p>
          The dashboard is configured to use <code className={styles.code}>{API_URL}</code>.
        </p>
      )}
      {children}
      {onRetry && (
        <button type="button" className={shared.button} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}
