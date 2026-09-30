import type { ReactNode } from 'react'
import styles from './KpiCard.module.css'

// One headline number. The label is the term; the value is its description (dt and dd).
export function KpiCard({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail?: ReactNode
}) {
  return (
    <div className={styles.card}>
      <dt className={styles.label}>{label}</dt>
      <dd className={styles.value}>{value}</dd>
      {detail && <dd className={styles.detail}>{detail}</dd>}
    </div>
  )
}
