import { useId, type ReactNode } from 'react'
import { CONFIDENCE_LABELS, METRIC_LABELS, observationScope } from '../../lib/analysis'
import { formatTime } from '../../lib/format'
import type { Analysis, AnalysisResponse } from '../../models/analysis'
import styles from './AnalysisResult.module.css'

// The model's answer, in the order an engineer reads it: the headline, what the numbers show,
// what might explain them, and what to check. Observations and hypotheses stay visibly apart,
// as the backend's prompt keeps them apart.
export function AnalysisResult({
  analysis,
  response,
}: {
  analysis: Analysis
  response: AnalysisResponse
}) {
  const { headline, observations, hypotheses, next_steps: nextSteps } = analysis
  return (
    <div className={styles.result}>
      <p className={styles.headline}>{headline}</p>

      {observations.length > 0 && (
        <Section title="Observations">
          <ul className={styles.list}>
            {observations.map((observation, index) => (
              <li key={index}>
                <span className={styles.tag}>
                  {observationScope(observation.endpoint)} · {METRIC_LABELS[observation.metric]}
                </span>{' '}
                {observation.text}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {hypotheses.length > 0 && (
        <Section title="Possible causes" note="Ideas to check, not findings.">
          <ul className={styles.list}>
            {hypotheses.map((hypothesis, index) => (
              <li key={index}>
                <span className={styles.tag}>{CONFIDENCE_LABELS[hypothesis.confidence]}</span>{' '}
                {hypothesis.text}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {nextSteps.length > 0 && (
        <Section title="What to check next">
          <ol className={styles.list}>
            {nextSteps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </Section>
      )}

      <AnalysisFooter response={response} />
    </div>
  )
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  const headingId = useId()
  return (
    <section className={styles.section} aria-labelledby={headingId}>
      <h3 id={headingId} className={styles.sectionTitle}>
        {title}
      </h3>
      {note && <p className={styles.note}>{note}</p>}
      {children}
    </section>
  )
}

// Where the answer came from and which data it covers, so nobody mistakes it for a measurement.
function AnalysisFooter({ response }: { response: AnalysisResponse }) {
  const { provider, model, generated_at: generatedAt, cached, window } = response
  // "groq (openai/gpt-oss-120b)"; the model alone is left out when it repeats the provider.
  const source = provider && model && model !== provider ? `${provider} (${model})` : provider
  const from = formatTime(window.start, { seconds: false })
  const to = formatTime(window.end, { seconds: false })
  return (
    <footer className={styles.footer}>
      <p>
        <strong>AI-assisted analysis</strong> of {from}–{to}
        {source && ` by ${source}`}, generated at {formatTime(generatedAt)}
        {cached && ' (cached)'}.
      </p>
      <p>It can be wrong: check the numbers against the charts before acting on them.</p>
    </footer>
  )
}
