import difference from '@turf/difference'
import { polygon, featureCollection } from '@turf/helpers'

/**
 * Compute the rings of land that do not overlap between two boundary
 * geometries (symmetric difference), returned as Leaflet [lat, lng] rings.
 *
 * Handles both `Polygon` and `MultiPolygon` results from @turf/difference —
 * disjoint slivers between two boundaries produce a MultiPolygon.
 *
 * @param {number[][][]} cadastralCoordinates GeoJSON Polygon coordinates (source A)
 * @param {number[][][]} droneCoordinates     GeoJSON Polygon coordinates (source B)
 * @returns {number[][][]|null} Array of [lat, lng] rings, or null when the
 *   inputs are unusable or the sources overlap completely.
 */
export function computeDisputedRings(cadastralCoordinates, droneCoordinates) {
  if (!Array.isArray(cadastralCoordinates) || !Array.isArray(droneCoordinates)) return null
  try {
    const cadastralPoly = polygon(cadastralCoordinates)
    const dronePoly = polygon(droneCoordinates)

    // turf v7 signature: difference(featureCollection([a, b])) computes a - b
    const rings = []
    for (const geom of [
      difference(featureCollection([cadastralPoly, dronePoly]))?.geometry,
      difference(featureCollection([dronePoly, cadastralPoly]))?.geometry,
    ]) {
      const polys =
        geom?.type === 'MultiPolygon'
          ? geom.coordinates
          : geom?.type === 'Polygon'
            ? [geom.coordinates]
            : []
      for (const poly of polys) {
        for (const ring of poly) {
          if (Array.isArray(ring) && ring.length >= 3) {
            rings.push(ring.map(([lng, lat]) => [lat, lng]))
          }
        }
      }
    }
    return rings.length > 0 ? rings : null
  } catch {
    // Malformed rings / invalid geometries: the map renders without the overlay.
    return null
  }
}
