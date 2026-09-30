import { LatencyPanel } from './components/charts/LatencyPanel'
import { StatusCodeChart } from './components/charts/StatusCodeChart'
import { RefreshControl } from './components/controls/RefreshControl'
import { WindowSelector } from './components/controls/WindowSelector'
import { ErrorState } from './components/feedback/ErrorState'
import { Panel, type PanelStatus } from './components/feedback/Panel'
import { StaleDataBanner } from './components/feedback/StaleDataBanner'
import { DashboardLayout } from './components/layout/DashboardLayout'
import { KpiGrid } from './components/kpis/KpiGrid'
import { Header } from './components/layout/Header'
import { useDashboardControls } from './hooks/useDashboardControls'
import { REFRESH_INTERVAL_MS, useMetrics } from './hooks/useMetrics'

// Calls useMetrics once and hands each panel its slice of the one response.
function App() {
  const { preset, autoRefresh, setPreset, setAutoRefresh } = useDashboardControls()
  const metrics = useMetrics(preset, { autoRefresh })
  const { data, error, isPending, isFetching, isPlaceholderData, dataUpdatedAt } = metrics
  const refetch = () => void metrics.refetch()

  const header = (
    <Header
      controls={
        <>
          <WindowSelector value={preset} onChange={setPreset} />
          <RefreshControl
            updatedAt={data ? dataUpdatedAt : 0}
            isFetching={isFetching}
            autoRefresh={autoRefresh}
            refreshSeconds={REFRESH_INTERVAL_MS / 1000}
            onAutoRefreshChange={setAutoRefresh}
            onRefresh={refetch}
          />
        </>
      }
    />
  )

  // Nothing to show yet and the request failed: one error for the page, not one per panel.
  if (!data && !isPending) {
    return (
      <DashboardLayout header={header} notice={<ErrorState error={error} onRetry={refetch} />} />
    )
  }

  const isEmpty = data?.summary.total_requests === 0
  // The previous window's data, shown dimmed while the chosen one loads.
  const busy = isPlaceholderData
  const status = (empty: boolean): PanelStatus => (!data ? 'loading' : empty ? 'empty' : 'ready')

  return (
    <DashboardLayout
      header={header}
      notice={
        // A refresh failed after a success: keep the last data, say how old it is.
        data &&
        error &&
        !isPlaceholderData && (
          <StaleDataBanner updatedAt={dataUpdatedAt} message={error.message} onRetry={refetch} />
        )
      }
      kpis={
        // Never "empty": with no requests the cards show counts of 0 and "—" for the rest.
        <Panel title={`Last ${preset.label}`} status={status(false)} busy={busy} loadingRows={2}>
          {data && <KpiGrid summary={data.summary} />}
        </Panel>
      }
      charts={
        <>
          <LatencyPanel status={status(isEmpty)} busy={busy} data={data} />
          <Panel title="Status codes" status={status(isEmpty)} busy={busy} loadingRows={4}>
            {data && <StatusCodeChart codes={data.status_codes} />}
          </Panel>
        </>
      }
    />
  )
}

export default App
