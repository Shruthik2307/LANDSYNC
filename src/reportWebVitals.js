import { onCLS, onINP, onFCP, onLCP, onTTFB } from 'web-vitals'

export function reportWebVitals(onPerfEntry) {
  if (onPerfEntry && onPerfEntry instanceof Function) {
    onCLS(onPerfEntry)
    onINP(onPerfEntry)
    onFCP(onPerfEntry)
    onLCP(onPerfEntry)
    onTTFB(onPerfEntry)
  }
}

// Log performance metrics in development
export function logWebVitals() {
  if (import.meta.env.DEV) {
    reportWebVitals((metric) => {
      // eslint-disable-next-line no-console
      console.log(`[Web Vitals] ${metric.name}: ${metric.value.toFixed(2)}ms`)
    })
  }
}
