// @vitest-environment node
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { getConflicts, getParcelById, getParcels, isDemoMode, processDataset, setApiBaseUrl, setDemoMode, uploadDataset } from '../src/api.js'
import { clampConfidence, normalizePriority } from '../src/validation.js'

const server = 'http://127.0.0.1:8000'
let liveBackend = false

const sampleGeoJson = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { parcel_id: 'TEST-100' },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [78.509, 17.388],
            [78.510, 17.388],
            [78.510, 17.389],
            [78.509, 17.389],
            [78.509, 17.388]
          ]
        ]
      }
    }
  ]
})

describe('LANDSYNC API contract', () => {
  beforeAll(async () => {
    try {
      const res = await fetch(`${server}/api/health`, { signal: AbortSignal.timeout(2500) })
      if (res.ok) {
        liveBackend = true
        setApiBaseUrl(server)
        setDemoMode(false)
      } else {
        liveBackend = false
        setDemoMode(true)
      }
    } catch {
      liveBackend = false
      setDemoMode(true)
    }
  })
  afterAll(() => {
    setDemoMode(false)
    setApiBaseUrl('')
  })

  it('loads parcels and sorted conflicts over HTTP', async (context) => {
    if (!liveBackend) context.skip()
    const parcels = await getParcels()
    const conflicts = await getConflicts()
    expect(parcels).toHaveLength(25)
    expect(conflicts.length).toBeGreaterThan(0)
    expect(conflicts[0].priority).toBe('HIGH')
    expect(conflicts.every((parcel) => parcel.geometry_conflict || parcel.attribute_conflict || parcel.duplicate_id)).toBe(true)
  })

  it('round-trips upload, process, and parcel detail', async (context) => {
    if (!liveBackend) context.skip()
    const upload = await uploadDataset([new File([sampleGeoJson], 'source.geojson')])
    expect(upload.dataset_id).toMatch(/^(server-|ds_)/)
    expect(await processDataset(upload.dataset_id)).toEqual({ job_status: 'complete' })

    // The reconciled results must now come from the UPLOADED dataset (the
    // uploaded cadastral source paired against the sample municipal survey),
    // not from the built-in sample parcels — this is the regression guard
    // for the bug where /api/process ignored the dataset_id entirely.
    const processedParcels = await getParcels()
    expect(processedParcels.length).toBeGreaterThan(0)
    expect(processedParcels.some((p) => p.parcel_id === 'TEST-100')).toBe(true)

    // Restoring the sample dataset must bring the sample parcels back.
    expect(await processDataset('sample')).toEqual({ job_status: 'complete' })
    const parcel = await getParcelById('HYD-REV-1000')
    expect(parcel.parcel_id).toBe('HYD-REV-1000')
    expect(parcel.confidence).toBeGreaterThanOrEqual(0)
  })

  it('keeps demo mode available without HTTP', async () => {
    setDemoMode(true)
    expect(isDemoMode()).toBe(true)
    expect((await getParcels()).length).toBe(8)
    expect((await processDataset('demo')).job_status).toBe('complete')
    setDemoMode(!liveBackend)
  })

  it('handles 404 for nonexistent parcel', async (context) => {
    if (!liveBackend) context.skip()
    const missing = await fetch(`${server}/api/parcels/NONEXISTENT-9999`)
    expect(missing.status).toBe(404)
  })

  it('satellite-tile endpoint returns fallback on missing credentials', async (context) => {
    if (!liveBackend) context.skip()
    const res = await fetch(`${server}/api/satellite-tile/10/512/340`)
    expect([200, 204, 404]).toContain(res.status)
  })

  it('normalizes unsafe scoring values before display', () => {
    expect(clampConfidence(-20)).toBe(0)
    expect(clampConfidence(140)).toBe(100)
    expect(normalizePriority('unexpected')).toBe('LOW')
    expect(normalizePriority('high')).toBe('HIGH')
  })
})
