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
  // Web Vitals logging disabled
}
