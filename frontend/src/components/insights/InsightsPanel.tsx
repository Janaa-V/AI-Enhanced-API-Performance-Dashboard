import { useState } from 'react'
import { useAnalysis } from '../../hooks/useAnalysis'
import { useNow } from '../../hooks/useNow'
import { formatWait } from '../../lib/format'
import shared from '../../styles/shared.module.css'
import { EmptyState } from '../feedback/EmptyState'
import { ErrorState, type ErrorInfo } from '../feedback/ErrorState'
import { Panel } from '../feedback/Panel'
import { AnalysisResult } from './AnalysisResult'
import styles from './InsightsPanel.module.css'

// What the panel needs from a failed analysis. An ApiError has this shape; components do not
// import api/.
interface AnalysisErrorInfo extends ErrorInfo {
  code?: string | undefined
  retryAfterSeconds?: number | undefined
}

interface InsightsPanelProps {
  windowMinutes: number
  // "1 hour", from the window selector.
  windowLabel: string
}

// On-demand AI analysis of the selected window. Nothing is sent until the user asks: each call
// may spend the server's AI quota. App gives it a key per window, so switching windows starts
// a fresh panel and an answer never sits under the wrong window's label.
export function InsightsPanel({ windowMinutes, windowLabel }: InsightsPanelProps) {
  const analysis = useAnalysis()
  const { data, error, isPending } = analysis
  const run = () => analysis.mutate(windowMinutes)

  return (
    <Panel
      title="AI insights"
      status="ready"
      actions={
        data &&
        !isPending && (
          <button type="button" className={shared.button} onClick={run}>
            Analyse again
          </button>
        )
      }
    >
      {isPending ? (
        <p className={styles.muted} role="status">
          Analysing the last {windowLabel}. This usually takes a few seconds.
        </p>
      ) : error ? (
        <AnalysisError error={error} onRetry={run} />
      ) : data?.status === 'ok' && data.analysis ? (
        <AnalysisResult analysis={data.analysis} response={data} />
      ) : data ? (
        <EmptyState>
          <p className={styles.emptyTitle}>Too little traffic to analyse</p>
          <p>
            The last {windowLabel} has too few requests for a useful analysis. Generate traffic with{' '}
            <code className={styles.code}>make traffic</code> in{' '}
            <code className={styles.code}>backend/</code>, or pick a longer window.
          </p>
        </EmptyState>
      ) : (
        <div className={styles.intro}>
          <p>
            Ask an AI model to summarise the last {windowLabel}: what stands out, what might explain
            it and what to check next.
          </p>
          <p className={styles.muted}>
            It sees only aggregate numbers, never individual requests, and it can be wrong.
          </p>
          <button type="button" className={shared.button} onClick={run}>
            Analyse the last {windowLabel}
          </button>
        </div>
      )}
    </Panel>
  )
}

// One message per failure the backend can give, each with the action that can fix it.
function AnalysisError({ error, onRetry }: { error: AnalysisErrorInfo; onRetry: () => void }) {
  if (error.code === 'ai_disabled') {
    // Not transient: retrying cannot help until someone configures the server.
    return (
      <ErrorState error={error} title="AI analysis is turned off">
        <p>
          Set <code className={styles.code}>AI_PROVIDER</code> in{' '}
          <code className={styles.code}>backend/.env</code> (
          <code className={styles.code}>fake</code> needs no key) and restart the backend.
        </p>
      </ErrorState>
    )
  }
  if (error.kind === 'rate_limited') {
    return (
      <ErrorState error={error} title="Analysis limit reached">
        <RetryButton waitSeconds={error.retryAfterSeconds ?? 0} onRetry={onRetry} />
      </ErrorState>
    )
  }
  const title =
    error.code === 'ai_unavailable' ? 'The AI provider did not answer' : 'The analysis failed'
  return <ErrorState error={error} title={title} onRetry={onRetry} />
}

// "Try again", disabled until the server's Retry-After has passed, with the seconds left.
function RetryButton({ waitSeconds, onRetry }: { waitSeconds: number; onRetry: () => void }) {
  // Counted from when the error is shown, which is when the response arrived.
  const [retryAt] = useState(() => Date.now() + waitSeconds * 1000)
  const now = useNow()
  const secondsLeft = Math.ceil((retryAt - now) / 1000)
  const waiting = secondsLeft > 0
  return (
    <button type="button" className={shared.button} disabled={waiting} onClick={onRetry}>
      {waiting ? `Try again in ${formatWait(secondsLeft)}` : 'Try again'}
    </button>
  )
}
