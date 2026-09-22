const PRIORITY_ORDER = { HIGH: 3, MEDIUM: 2, LOW: 1 }

export function priorityOf(parcel) {
  return normalizePriority(parcel?.priority)
}

/** @param {unknown} value @returns {'HIGH'|'MEDIUM'|'LOW'} */
export function normalizePriority(value) {
  const priority = String(value || 'LOW').toUpperCase()
  return PRIORITY_ORDER[priority] ? priority : 'LOW'
}

/** @param {unknown} value @returns {number} */
export function clampConfidence(value) {
  return Math.max(0, Math.min(100, Number(value) || 0))
}
