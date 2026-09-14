import React, { useMemo } from 'react'
import { CircleMarker, Polygon } from 'react-leaflet'
import { priorityOf } from '../../validation'
import difference from '@turf/difference'
import { polygon } from '@turf/helpers'

export default function ParcelShape({ parcel, selected, dimmed, onSelect, boundaryMode }) {
  const coordinates = parcel?.boundaries?.cadastral?.coordinates?.[0]
  const droneCoordinates = parcel?.boundaries?.drone_ori?.coordinates?.[0]

  // Compute disputed area (geometry difference) for geometry_conflict parcels
  const disputedArea = useMemo(() => {
    if (!selected || !parcel?.geometry_conflict || !droneCoordinates) return null

    try {
      const cadastralPoly = polygon(parcel.boundaries.cadastral.coordinates)
      const dronePoly = polygon(parcel.boundaries.drone_ori.coordinates)

      // Compute symmetric difference (areas that don't overlap)
      const diff1 = difference(cadastralPoly, dronePoly)
      const diff2 = difference(dronePoly, cadastralPoly)

      const disputed = []
      if (diff1?.geometry?.coordinates) {
        diff1.geometry.coordinates.forEach(ring => {
          disputed.push(ring[0].map(([lng, lat]) => [lat, lng]))
        })
      }
      if (diff2?.geometry?.coordinates) {
        diff2.geometry.coordinates.forEach(ring => {
          disputed.push(ring[0].map(([lng, lat]) => [lat, lng]))
        })
      }

      return disputed.length > 0 ? disputed : null
    } catch {
      return null
    }
  }, [selected, parcel, droneCoordinates])

  if (!Array.isArray(coordinates) || coordinates.length < 4) return null

  const points = coordinates.map((coordinate) => {
    const [lng, lat] = coordinate
    return [lat, lng]
  })

  const priority = priorityOf(parcel)
  // Dynamic color coding: HIGH=Crimson, MEDIUM=Amber, LOW=Cyan
  const fill = priority === 'HIGH' ? '#FF4C4C' : priority === 'MEDIUM' ? '#FFB800' : '#00F0FF'
  const opacity = dimmed ? 0.05 : selected ? 0.55 : 0.25
  const strokeColor = selected ? '#FFFFFF' : fill

  const dronePoints = Array.isArray(droneCoordinates) && droneCoordinates.length >= 4
    ? droneCoordinates.map(([lng, lat]) => [lat, lng])
    : null

  return (
    <>
      {/* Primary Cadastral Polygon */}
      <Polygon
        positions={points}
        pathOptions={{
          color: strokeColor,
          fillColor: fill,
          fillOpacity: opacity,
          opacity: dimmed ? 0.2 : 0.95,
          weight: selected ? 3.5 : 1.8,
          className: `cursor-pointer transition-all duration-200 ${selected ? 'parcel-selected' : ''}`,
        }}
        eventHandlers={{ 
          click: () => onSelect(parcel),
        }}
      />

      {/* Discrepancy Comparison Overlays when Selected */}
      {selected && parcel.geometry_conflict && (
        <>
          {/* Disputed Area Highlight - Areas that don't overlap between sources */}
          {disputedArea && disputedArea.map((area, idx) => (
            <Polygon
              key={`disputed-${idx}`}
              positions={area}
              pathOptions={{
                color: '#FF4C4C',
                fillColor: '#FF4C4C',
                fillOpacity: 0.4,
                opacity: 0,
                weight: 0
              }}
            />
          ))}

          {/* Cadastral RoR Boundary in Cyan */}
          {(boundaryMode === 'cadastral' || boundaryMode === 'both') && (
            <Polygon
              positions={points}
              pathOptions={{
                color: '#00F0FF',
                fill: false,
                weight: 3,
                dashArray: '6 4',
                opacity: 0.95
              }}
            />
          )}

          {/* Drone/ORI Survey Boundary in Amber */}
          {dronePoints && (boundaryMode === 'drone' || boundaryMode === 'both') && (
            <Polygon
              positions={dronePoints}
              pathOptions={{
                color: '#FFB800',
                fill: false,
                weight: 3.5,
                dashArray: '8 8',
                opacity: 1
              }}
            />
          )}
        </>
      )}

      {/* Cadastral Origin Marker */}
      <CircleMarker
        center={points[0]}
        radius={selected ? 6 : 3.5}
        pathOptions={{ 
          color: selected ? '#00F0FF' : '#FFFFFF', 
          fillColor: fill, 
          fillOpacity: dimmed ? 0.2 : 0.95, 
          opacity: dimmed ? 0.2 : 1, 
          weight: selected ? 2 : 1 
        }}
        eventHandlers={{ click: () => onSelect(parcel) }}
      />
    </>
  )
}
