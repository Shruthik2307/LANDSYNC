import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { SatelliteTokenManager, tileToBBox } from './satellite-utils.mjs'

const root = fileURLToPath(new URL('../contract/mock/', import.meta.url))
const baseParcels = JSON.parse(await readFile(`${root}/parcels.json`, 'utf8'))
const baseConflicts = JSON.parse(await readFile(`${root}/conflicts.json`, 'utf8'))
const priorityOrder = { HIGH: 3, MEDIUM: 2, LOW: 1 }
let activeDatasetSize = 0

const tokenManager = new SatelliteTokenManager()

// --- Original Server Logic ---

function generatedParcels(size) {
  return Array.from({ length: size }, (_, index) => {
    const row = Math.floor(index / 12)
    const column = index % 12
    const lng = 77.56 + column * 0.002
    const lat = 12.94 + row * 0.002
    const priority = index % 3 === 0 ? 'HIGH' : index % 3 === 1 ? 'MEDIUM' : 'LOW'
    const geometryConflict = index % 4 === 0
    return {
      parcel_id: String(2000 + index), confidence: 60 + index % 40, priority,
      area_difference: index % 5, geometry_conflict: geometryConflict,
      attribute_conflict: index % 5 === 0, duplicate_id: false,
      recommendation: geometryConflict ? 'Field verification' : 'Review source records',
      boundaries: {
        cadastral: { type: 'Polygon', coordinates: [[[lng, lat], [lng + 0.001, lat], [lng + 0.001, lat + 0.001], [lng, lat + 0.001], [lng, lat]]] },
        ...(geometryConflict ? { drone_ori: { type: 'Polygon', coordinates: [[[lng, lat], [lng + 0.0011, lat], [lng + 0.001, lat + 0.0011], [lng, lat + 0.001], [lng, lat]]] } } : {}),
      },
    }
  })
}

function response(res, status, body, contentType = 'application/json') {
  res.writeHead(status, { 'Content-Type': contentType, 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' })
  res.end(body)
}

function mode(url) {
  return url.searchParams.get('mode')
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function bodyOf(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1')
  if (req.method === 'OPTIONS') return response(res, 204, '')
  if (mode(url) === 'hang') return undefined
  if (mode(url) === '500') return response(res, 500, JSON.stringify({ detail: 'Synthetic server failure' }))
  if (mode(url) === 'malformed') return response(res, 200, '{malformed')

  // Satellite Tile Proxy Route
  const satelliteMatch = url.pathname.match(/^\/api\/satellite-tile\/(\d+)\/(\d+)\/(\d+)$/)
  if (req.method === 'GET' && satelliteMatch) {
    const [, zStr, xStr, yStr] = satelliteMatch
    const z = parseInt(zStr, 10), x = parseInt(xStr, 10), y = parseInt(yStr, 10)

    try {
      let token = await tokenManager.getToken()
      const bbox = tileToBBox(z, x, y)

      const fetchTile = async (t) => {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 10000) // 10s timeout

        try {
          const shResponse = await fetch('https://sh.dataspace.copernicus.eu/api/v1/process', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${t}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              input: {
                bounds: { bbox: [bbox.west, bbox.south, bbox.east, bbox.north], crs: 'EPSG:4326' },
                id: 'sentinel-2-l2a'
              },
              output: {
                responses: [{
                  identifier: 'default',
                  format: { type: 'image/png' }
                }]
              },
              // Simplified request for TRUE_COLOR
              evalscript: 'function setup() { return { bands: { B04: { data: "B04", scale: 0.0001 }, B03: { data: "B03", scale: 0.0001 }, B02: { data: "B02", scale: 0.0001 } } } function main() { return [B04, B03, B02] }'
            }),
            signal: controller.signal
          })
          clearTimeout(timeoutId)
          return shResponse
        } catch (e) {
          clearTimeout(timeoutId)
          throw e
        }
      }

      let shResponse = await fetchTile(token)

      // Retry logic for auth failure
      if (shResponse.status === 401) {
        tokenManager.invalidateToken()
        token = await tokenManager.getToken()
        shResponse = await fetchTile(token)
      }

      if (!shResponse.ok) {
        // Return 204 or 404 on any upstream failure
        return response(res, shResponse.status >= 500 || shResponse.status === 403 ? 204 : 404, '')
      }

      const buffer = await shResponse.arrayBuffer()
      return response(res, 200, Buffer.from(buffer), shResponse.headers.get('content-type') || 'image/png')

    } catch (e) {
      // Log server-side error but return fallback
      console.error(`[Satellite Proxy Error]: ${e.message}`)
      return response(res, 204, '')
    }
  }

  if (req.method === 'POST' && url.pathname === '/api/upload') {
    const body = await bodyOf(req)
    await delay(250)
    activeDatasetSize = body.includes('load-120') ? 120 : 0
    return response(res, 200, JSON.stringify({ dataset_id: `server-${Date.now()}` }))
  }
  if (req.method === 'POST' && url.pathname === '/api/process') {
    await bodyOf(req)
    await delay(1200)
    return response(res, 200, JSON.stringify({ job_status: 'complete' }))
  }
  if (req.method === 'GET' && url.pathname === '/api/parcels') {
    const parcels = activeDatasetSize > 0 ? generatedParcels(activeDatasetSize) : Number(url.searchParams.get('size')) > 0 ? generatedParcels(Number(url.searchParams.get('size'))) : baseParcels
    return response(res, 200, JSON.stringify(parcels))
  }
  if (req.method === 'GET' && url.pathname === '/api/conflicts') {
    const parcels = activeDatasetSize > 0 ? generatedParcels(activeDatasetSize) : Number(url.searchParams.get('size')) > 0 ? generatedParcels(Number(url.searchParams.get('size'))) : baseConflicts
    const conflicts = parcels.filter((parcel) => parcel.geometry_conflict || parcel.attribute_conflict || parcel.duplicate_id).sort((a, b) => priorityOrder[b.priority] - priorityOrder[a.priority] || b.confidence - a.confidence)
    return response(res, 200, JSON.stringify(conflicts))
  }
  if (req.method === 'GET' && url.pathname.startsWith('/api/parcels/')) {
    const id = decodeURIComponent(url.pathname.split('/').pop())
    const parcel = baseParcels.find((item) => item.parcel_id === id)
    return parcel ? response(res, 200, JSON.stringify(parcel)) : response(res, 404, JSON.stringify({ detail: 'Parcel not found' }))
  }
  return response(res, 404, JSON.stringify({ detail: 'Not found' }))
})

const port = Number(process.env.PORT || 8000)
server.listen(port, '127.0.0.1', () => console.log(`LANDSYNC contract server listening on http://127.0.0.1:${port}`))
