import { useEffect, useState } from 'react'

// The current time, updated every `intervalMs`. Only components that call it re-render on each
// tick, so keep it in the smallest component that shows a relative time.
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
  return now
}
