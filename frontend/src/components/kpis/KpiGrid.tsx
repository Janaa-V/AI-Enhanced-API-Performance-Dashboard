import { formatCount, formatLatency, formatPercent, formatRate } from '../../lib/format'
import type { Summary } from '../../models/metrics'
import { KpiCard } from './KpiCard'
import styles from './KpiGrid.module.css'

// The window's headline numbers. An empty window shows "—", never 0, for what it cannot measure.
export function KpiGrid({ summary }: { summary: Summary }) {
  return (
    <dl className={styles.grid}>
      <KpiCard label="Requests" value={formatCount(summary.total_requests)} />
      <KpiCard label="Requests per minute" value={formatRate(summary.requests_per_minute)} />
      <KpiCard
        label="Error rate"
        value={formatPercent(summary.error_rate)}
        // Only 5xx count as errors; 4xx are the client's mistakes, counted separately.
        detail={
          <>
            {formatCount(summary.server_errors)} server (5xx) · {formatCount(summary.client_errors)}{' '}
            client (4xx)
          </>
        }
      />
      <KpiCard label="Average latency" value={formatLatency(summary.avg_latency_ms)} />
      <KpiCard
        label="p95 latency"
        value={formatLatency(summary.p95_latency_ms)}
        detail="95% of requests took this long or less"
      />
    </dl>
  )
}
