import type { ReactNode } from 'react'
import styles from './EmptyState.module.css'

// No requests in the window. The default message says how to create some.
export function EmptyState({ children }: { children?: ReactNode }) {
  return (
    <div className={styles.empty}>
      {children ?? (
        <>
          <p className={styles.title}>No requests in this window</p>
          <p>
            Generate some traffic with <code className={styles.code}>make traffic</code> in{' '}
            <code className={styles.code}>backend/</code>, or pick a longer window.
          </p>
        </>
      )}
    </div>
  )
}
