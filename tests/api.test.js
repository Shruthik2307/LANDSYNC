import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { getConflicts, getParcelById, getParcels, isDemoMode, processDataset, setDemoMode, uploadDataset } from '../src/api.js'
import { clampConfidence, normalizePriority } from '../src/validation.js'

const server = 'http://127.0.0.1:8000'
let liveBackend = false

describe('LANDSYNC API contract', () => {
  beforeAll(async () => {
    try {
      await fetch(`${server}/api/parcels`, { signal: AbortSignal.timeout(2500) })
      liveBackend = true
      setDemoMode(false)
      await uploadDataset([new File(['default'], 'default.geojson')])
    } catch {
      liveBackend = false
      setDemoMode(true)
    }
  })
  afterAll(() => setDemoMode(true))

  it('loads parcels and sorted conflicts over HTTP', async (context) => {
    if (!liveBackend) context.skip()
    const parcels = await getParcels()
    const conflicts = await getConflicts()
    expect(parcels).toHaveLength(8)
    expect(conflicts[0].priority).toBe('HIGH')
    expect(conflicts.every((parcel) => parcel.geometry_conflict || parcel.attribute_conflict || parcel.duplicate_id)).toBe(true)
  })

  it('round-trips upload, process, and parcel detail', async (context) => {
    if (!liveBackend) context.skip()
    const upload = await uploadDataset([new File(['demo'], 'source.geojson')])
    expect(upload.dataset_id).toMatch(/^server-/)
    expect(await processDataset(upload.dataset_id)).toEqual({ job_status: 'complete' })
    expect((await getParcelById('1042')).parcel_id).toBe('1042')
  })

  it('keeps demo mode available without HTTP', async () => {
    setDemoMode(true)
    expect(isDemoMode()).toBe(true)
    expect((await getParcels()).length).toBe(8)
    expect((await processDataset('demo')).job_status).toBe('complete')
    setDemoMode(!liveBackend)
  })

  it('server exposes explicit failure routes', async (context) => {
    if (!liveBackend) context.skip()
    const failed = await fetch(`${server}/api/parcels?mode=500`)
    const malformed = await fetch(`${server}/api/parcels?mode=malformed`)
    const missing = await fetch(`${server}/api/parcels/not-found`)
    expect(failed.status).toBe(500)
    expect(await malformed.text()).toBe('{malformed')
    expect(missing.status).toBe(404)
  })

  it('satellite-tile endpoint returns fallback on missing credentials', async (context) => {
    if (!liveBackend) context.skip()
    const res = await fetch(`${server}/api/satellite-tile/10/512/340`)
    // Should return 204 or 404 instead of 500 when credentials are missing
    expect([204, 404]).toContain(res.status)
  })

  it('normalizes unsafe scoring values before display', () => {
    expect(clampConfidence(-20)).toBe(0)
    expect(clampConfidence(140)).toBe(100)
    expect(normalizePriority('unexpected')).toBe('LOW')
    expect(normalizePriority('high')).toBe('HIGH')
  })
})
