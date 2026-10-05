import { useState } from 'react'
import { LATENCY_METRIC_LABELS, type LatencyMetric } from '../../lib/chartData'
import type { MetricsResponse } from '../../models/metrics'
import { SegmentedControl } from '../controls/SegmentedControl'
import { Panel, type PanelStatus } from '../feedback/Panel'
import { LatencyChart } from './LatencyChart'

const METRIC_OPTIONS = (Object.keys(LATENCY_METRIC_LABELS) as LatencyMetric[]).map((value) => ({
  value,
  label: LATENCY_METRIC_LABELS[value],
}))

// The latency chart with its p95 / average switch. p95 first: averages hide the slow tail.
export function LatencyPanel({
  status,
  busy,
  data,
}: {
  status: PanelStatus
  busy?: boolean
  data: MetricsResponse | undefined
}) {
  const [metric, setMetric] = useState<LatencyMetric>('p95_latency_ms')
  return (
    <Panel
      title="Latency over time"
      status={status}
      busy={busy}
      loadingRows={6}
      actions={
        <SegmentedControl
          legend="Latency measure"
          options={METRIC_OPTIONS}
          value={metric}
          onChange={setMetric}
        />
      }
    >
      {data && <LatencyChart trend={data.latency_trend} metric={metric} range={data.window} />}
    </Panel>
  )
}
