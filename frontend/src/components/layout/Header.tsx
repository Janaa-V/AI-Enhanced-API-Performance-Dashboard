import type { ReactNode } from 'react'
import styles from './Header.module.css'
import { ThemeToggle } from './ThemeToggle'

// Title and theme toggle, with the dashboard's controls below.
export function Header({ controls }: { controls: ReactNode }) {
  return (
    <header className={styles.header}>
      <div className={styles.strip} aria-hidden="true" />
      <div className={styles.inner}>
        <div className={styles.titleRow}>
          <div>
            <h1 className={styles.title}>API Performance Dashboard</h1>
            <p className={styles.lead}>Latency, throughput and errors for the demo API.</p>
          </div>
          <ThemeToggle />
        </div>
        <div className={styles.controls}>{controls}</div>
      </div>
    </header>
  )
}
