import { useEffect, useState } from 'react'
import { SERIES_SLOT_COUNT } from '../lib/series'

export interface ChartColors {
  // series[0] is --color-series-1.
  series: string[]
  text: string
  textMuted: string
  axis: string
  grid: string
  surface: string
  surfaceRaised: string
  border: string
  success: string
  warning: string
  danger: string
}

function readColors(): ChartColors {
  const style = getComputedStyle(document.documentElement)
  const token = (name: string) => style.getPropertyValue(name).trim()
  return {
    series: Array.from({ length: SERIES_SLOT_COUNT }, (_, index) =>
      token(`--color-series-${index + 1}`),
    ),
    text: token('--color-text'),
    textMuted: token('--color-text-muted'),
    axis: token('--color-axis'),
    grid: token('--color-grid'),
    surface: token('--color-surface'),
    surfaceRaised: token('--color-surface-raised'),
    border: token('--color-border'),
    success: token('--color-success'),
    warning: token('--color-warning'),
    danger: token('--color-danger'),
  }
}

// The theme's colours as values. Recharts sets colours through SVG attributes, where CSS
// variables are not reliably resolved, so charts get the resolved tokens instead. They are read
// again when the theme changes: data-theme on <html>, or the operating system's setting.
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState(readColors)

  useEffect(() => {
    const update = () => setColors(readColors())
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    const scheme = window.matchMedia('(prefers-color-scheme: dark)')
    scheme.addEventListener('change', update)
    return () => {
      observer.disconnect()
      scheme.removeEventListener('change', update)
    }
  }, [])

  return colors
}
