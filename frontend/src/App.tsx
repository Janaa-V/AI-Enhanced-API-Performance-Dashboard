import styles from './App.module.css'

function App() {
  return (
    <>
      <div className={styles.strip} aria-hidden="true" />
      <main className={styles.page}>
        <h1 className={styles.title}>API Performance Dashboard</h1>
        <p className={styles.lead}>Latency, throughput and errors for the demo API.</p>
      </main>
    </>
  )
}

export default App
