import parcelsFixture from '../contract/mock/parcels.json'
import conflictsFixture from '../contract/mock/conflicts.json'

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// Prod builds default to same-origin API calls ('' → fetch('/api/…')) — the
// unified Render service serves the SPA and the API from one URL. Override
// via VITE_API_BASE_URL or window/localStorage for split deployments.
const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && (window.__LANDSYNC_API_BASE_URL__ || localStorage.getItem('LANDSYNC_API_BASE_URL'))) ||
  ''
export const API_BASE_URL = (configuredApiBaseUrl || '').replace(/\/$/, '')

export function setApiBaseUrl(url) {
  if (typeof window !== 'undefined') {
    if (url) {
      localStorage.setItem('LANDSYNC_API_BASE_URL', url)
    } else {
      localStorage.removeItem('LANDSYNC_API_BASE_URL')
    }
  }
}
// Static deployments without a backend (e.g. GitHub Pages) can build with
// VITE_DEFAULT_DEMO_MODE=true so the site boots straight into the demo fixture.
let forceDemoMode = import.meta.env.VITE_DEFAULT_DEMO_MODE === 'true'


export function isDemoMode() {
  return forceDemoMode
}

export function setDemoMode(enabled) {
  forceDemoMode = Boolean(enabled)
}

async function request(path, options = {}, timeoutMs = 15000) {
  if (isDemoMode()) {
    if (path === '/api/parcels') return structuredClone(parcelsFixture)
    if (path === '/api/conflicts') return structuredClone(conflictsFixture)
    if (path === '/api/health') return { status: 'ok', engine: 'loaded (demo)', parcel_count: parcelsFixture.length }
    throw new Error('The demo fixture does not cover this request.')
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal: controller.signal })
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('This request timed out. Check that the backend is responding, then retry.')
    }
    throw new Error(`The live backend at ${API_BASE_URL || 'this origin'} could not be reached. Check your connection and retry.`)
  } finally {
    clearTimeout(timeout)
  }

  if (response.status === 404) {
    throw new Error(`Resource not found (404) at ${path}.`)
  }

  if (response.status === 500) {
    let detail = ''
    try {
      const errJson = await response.json()
      detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail || errJson)
    } catch {
      // Non-JSON 500 body; fall back to the generic message below.
    }
    throw new Error(`Server error (500): ${detail || 'Internal server error while processing request.'}`)
  }

  if (!response.ok) {
    let detail = ''
    try {
      const contentType = response.headers.get('Content-Type')
      if (contentType && contentType.includes('application/json')) {
        const errJson = await response.json()
        detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail || errJson)
      } else {
        detail = await response.text()
      }
    } catch {
      // Non-JSON error body; fall back to the status text below.
    }
    const message = detail
      ? `LANDSYNC request failed (${response.status}): ${detail}`
      : `LANDSYNC request failed (${response.status})`
    throw new ApiError(message, response.status, detail || response.statusText)
  }


  try {
    const contentType = response.headers.get('Content-Type')
    if (contentType && contentType.includes('application/json')) {
      return await response.json()
    }
    const text = await response.text()
    throw new Error(`Expected JSON response but received ${contentType}: ${text.slice(0, 100)}`)
  } catch (parseError) {
    if (parseError instanceof Error && parseError.message.startsWith('Expected JSON')) throw parseError
    throw new Error('The backend returned data in an unexpected format (malformed JSON).')
  }

}

/** @returns {Promise<{status: string, engine: string, parcel_count: number, cadastral_crs?: string, municipal_crs?: string}>} */
export function getHealth() {
  if (isDemoMode()) {
    return Promise.resolve({
      status: 'ok',
      engine: 'loaded',
      parcel_count: parcelsFixture.length,
    })
  }
  return request('/api/health')
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
    if (files && files.length > 0) {
      // Pick the GeoJSON or JSON file first if present
      const geoFile = files.find(f => {
        const name = (f.name || '').toLowerCase()
        return name.endsWith('.geojson') || name.endsWith('.json')
      }) || files[0]
      body.append('file', geoFile, geoFile?.name || 'source.geojson')
    }
    return request('/api/upload', { method: 'POST', body })
  }
  return new Promise((resolve) => setTimeout(() => resolve({ dataset_id: `mock-${Date.now()}-${files.length}` }), 700))
}

/** @param {string} [datasetId] @returns {Promise<{job_status: string}>} */
export function processDataset(datasetId) {
  if (!isDemoMode()) {
    return request(
      '/api/process',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: datasetId || 'sample' })
      },
      30000
    )
  }
  return new Promise((resolve) => setTimeout(() => resolve({ job_status: 'complete' }), 3400))
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
