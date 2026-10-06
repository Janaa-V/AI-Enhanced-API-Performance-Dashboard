import type { ReactNode } from 'react'
import styles from './DashboardLayout.module.css'

interface DashboardLayoutProps {
  header: ReactNode
  // Page-level messages above the panels, such as a failed refresh.
  notice?: ReactNode
  kpis?: ReactNode
  // The AI insights panel, under the KPIs: a summary to read before the details.
  insights?: ReactNode
  // Two columns from 1024 px, one on narrower screens.
  charts?: ReactNode
  tables?: ReactNode
}

// The page grid: KPIs across the top, then AI insights, charts side by side on wide screens and
// tables full width.
export function DashboardLayout({
  header,
  notice,
  kpis,
  insights,
  charts,
  tables,
}: DashboardLayoutProps) {
  return (
    <>
      {header}
      <main className={styles.main}>
        {notice}
        {kpis && <div className={styles.kpis}>{kpis}</div>}
        {insights}
        {charts && <div className={styles.charts}>{charts}</div>}
        {tables && <div className={styles.tables}>{tables}</div>}
      </main>
    </>
  )
}
