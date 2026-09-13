import parcelsFixture from '../contract/mock/parcels.json'
import conflictsFixture from '../contract/mock/conflicts.json'

const configuredApiBaseUrl = import.meta.env.DEV
  ? import.meta.env.VITE_API_BASE_URL
  : globalThis.__LANDSYNC_API_BASE_URL__
const API_BASE_URL = configuredApiBaseUrl?.replace(/\/$/, '')
let forceDemoMode = false

export function isDemoMode() {
  return forceDemoMode || !API_BASE_URL
}

export function setDemoMode(enabled) {
  forceDemoMode = enabled
}

async function request(path, options = {}, timeoutMs = 15000) {
  if (isDemoMode()) {
    if (path === '/api/parcels') return structuredClone(parcelsFixture)
    if (path === '/api/conflicts') return structuredClone(conflictsFixture)
    throw new Error('The demo fixture does not cover this request.')
  }

  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal: controller.signal })
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('This is taking longer than expected — retry?')
    throw new Error('The live backend could not be reached. Check that FastAPI is running, then retry.')
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) throw new Error(`LANDSYNC request failed: ${response.status}`)
  try {
    return await response.json()
  } catch {
    throw new Error('The backend returned data in an unexpected format. Check the API response and retry.')
  }
}

/** @returns {Promise<Parcel[]>} */
export function getParcels() {
  return request('/api/parcels')
}

/** @returns {Promise<Parcel[]>} */
export function getConflicts() {
  return request('/api/conflicts')
}

/** @param {string} id @returns {Promise<Parcel>} */
export function getParcelById(id) {
  return !isDemoMode()
    ? request(`/api/parcels/${encodeURIComponent(id)}`)
    : getParcels().then((parcels) => {
      const parcel = parcels.find((item) => item.parcel_id === id)
      if (!parcel) throw new Error('Parcel not found in the demo dataset.')
      return parcel
    })
}

/** @param {File[]} files @returns {Promise<{dataset_id: string}>} */
export function uploadDataset(files) {
  if (!isDemoMode()) {
    const body = new FormData()
    files.forEach((file) => body.append('file', file))
    return request('/api/upload', { method: 'POST', body })
  }
  return new Promise((resolve) => window.setTimeout(() => resolve({ dataset_id: `mock-${Date.now()}-${files.length}` }), 700))
}

/** @param {string} datasetId @returns {Promise<{job_status: string}>} */
export function processDataset(datasetId) {
  if (!isDemoMode()) return request('/api/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dataset_id: datasetId }) }, 30000)
  return new Promise((resolve) => window.setTimeout(() => resolve({ job_status: 'complete' }), 3400))
}

/**
 * Shared contract shape. Geometry fields are an addition to the original flat
 * source contract because the map needs both boundary sources.
 * @typedef {Object} GeoJSONPolygon
 * @property {'Polygon'} type
 * @property {number[][][]} coordinates
 */

/**
 * @typedef {Object} Parcel
 * @property {string} parcel_id
 * @property {number} confidence
 * @property {'HIGH'|'MEDIUM'|'LOW'} priority
 * @property {number} area_difference
 * @property {boolean} geometry_conflict
 * @property {boolean} attribute_conflict
 * @property {boolean} duplicate_id
 * @property {string} recommendation
 * @property {{cadastral: GeoJSONPolygon, drone_ori?: GeoJSONPolygon}} boundaries
 */
