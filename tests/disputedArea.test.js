import { describe, expect, it } from 'vitest'
import { computeDisputedRings } from '../src/components/map/disputedArea'

// Two squares that partially overlap: symmetric difference = two slivers
const A = [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]] // GeoJSON [lng, lat]
const B = [[[1, 0], [3, 0], [3, 2], [1, 2], [1, 0]]]

// Identical squares: no disputed land at all
const C = [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]

// Disjoint squares: difference is the whole square (one Polygon), twice
const D = [[[20, 20], [21, 20], [21, 21], [20, 21], [20, 20]]]
const E = [[[30, 30], [31, 30], [31, 31], [30, 31], [30, 30]]]

// Wide rectangle minus a middle bar: each difference is a MultiPolygon
// (two disjoint pieces on either side of the bar)
const F = [[[0, 0], [4, 0], [4, 1], [0, 1], [0, 0]]]
const G = [[[1.5, -1], [2.5, -1], [2.5, 2], [1.5, 2], [1.5, -1]]]

describe('computeDisputedRings', () => {
  it('returns rings for partially overlapping boundaries', () => {
    const rings = computeDisputedRings(A, B)
    expect(rings).not.toBeNull()
    expect(rings.length).toBeGreaterThanOrEqual(2)
    // Every ring is a valid Leaflet ring of [lat, lng] points
    for (const ring of rings) {
      expect(ring.length).toBeGreaterThanOrEqual(3)
      for (const point of ring) {
        expect(point).toHaveLength(2)
        expect(Number.isFinite(point[0])).toBe(true)
        expect(Number.isFinite(point[1])).toBe(true)
      }
    }
  })

  it('swaps coordinate order to [lat, lng] for Leaflet', () => {
    const rings = computeDisputedRings(A, B)
    const flat = rings.flat()
    // GeoJSON lng was 0..3, lat 0..2. After swap, no lat may exceed 2
    // and lng values (originally lat) stay <= 2... verify swap by domain:
    const lats = flat.map((p) => p[0])
    expect(Math.max(...lats)).toBeLessThanOrEqual(2.0000001)
    expect(Math.min(...lats)).toBeGreaterThanOrEqual(-0.0000001)
  })

  it('returns multiple rings when the difference is a MultiPolygon', () => {
    // Rectangle minus a middle bar: F-G is a 2-piece MultiPolygon and G-F
    // contributes the bar segments above/below the rectangle.
    const rings = computeDisputedRings(F, G)
    expect(rings.length).toBeGreaterThanOrEqual(2)
    for (const ring of rings) {
      expect(ring.length).toBeGreaterThanOrEqual(3)
    }
  })

  it('returns null for identical boundaries (consensus)', () => {
    expect(computeDisputedRings(C, C)).toBeNull()
  })

  it('returns rings for fully disjoint boundaries', () => {
    const rings = computeDisputedRings(D, E)
    expect(rings).not.toBeNull()
    expect(rings.length).toBe(2)
  })

  it('returns null for malformed or missing inputs', () => {
    expect(computeDisputedRings(null, B)).toBeNull()
    expect(computeDisputedRings(A, undefined)).toBeNull()
    expect(computeDisputedRings([[['oops']]], B)).toBeNull()
  })
})
