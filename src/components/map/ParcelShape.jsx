import React, { useMemo } from 'react'
import PropTypes from 'prop-types'
import { CircleMarker, Polygon } from 'react-leaflet'
import { priorityOf } from '../../validation'
import { computeDisputedRings } from './disputedArea'

export default function ParcelShape({ parcel, selected, dimmed, onSelect, boundaryMode }) {
  const coordinates = parcel?.boundaries?.cadastral?.coordinates?.[0]
  const droneRing = parcel?.boundaries?.drone_ori?.coordinates?.[0]

  // Compute disputed area (geometry difference) for geometry_conflict parcels
  const disputedArea = useMemo(() => {
    if (!selected || !parcel?.geometry_conflict || !droneRing) return null
    // computeDisputedRings takes full GeoJSON Polygon coordinate arrays
    return computeDisputedRings(
      parcel.boundaries.cadastral.coordinates,
      parcel.boundaries.drone_ori.coordinates,
    )
  }, [selected, parcel, droneRing])

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

  const dronePoints = Array.isArray(droneRing) && droneRing.length >= 4
    ? droneRing.map(([lng, lat]) => [lat, lng])
    : null

  const isDroneOnly = boundaryMode === 'drone'
  const isBoth = boundaryMode === 'both'
  const primaryPoints = isDroneOnly && dronePoints ? dronePoints : points
  const primaryStroke = selected ? '#FFFFFF' : isDroneOnly ? '#FFB800' : fill
  const primaryFill = isDroneOnly ? '#FFB800' : fill

  return (
    <>
      {/* Primary Boundary Polygon (Cadastral in Cadastral/Both mode; Municipal in Drone mode) */}
      <Polygon
        positions={primaryPoints}
        pathOptions={{
          color: primaryStroke,
          fillColor: primaryFill,
          fillOpacity: opacity,
          opacity: dimmed ? 0.2 : 0.95,
          weight: selected ? 3.5 : 1.8,
          dashArray: isDroneOnly ? '6 4' : undefined,
          className: `cursor-pointer transition-all duration-200 ${selected ? 'parcel-selected' : ''}`,
        }}
        eventHandlers={{ 
          click: () => onSelect(parcel),
        }}
      />

      {/* Overlay Municipal Survey Boundary in 'both' (Consensus) mode when not selected */}
      {!selected && isBoth && dronePoints && (
        <Polygon
          positions={dronePoints}
          pathOptions={{
            color: '#FFB800',
            fillColor: '#FFB800',
            fillOpacity: opacity * 0.6,
            opacity: dimmed ? 0.2 : 0.9,
            weight: 1.8,
            dashArray: '6 4',
            className: 'cursor-pointer transition-all duration-200',
          }}
          eventHandlers={{
            click: () => onSelect(parcel),
          }}
        />
      )}

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
                fillOpacity: 0.45,
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

ParcelShape.propTypes = {
  parcel: PropTypes.shape({
    parcel_id: PropTypes.string.isRequired,
    geometry_conflict: PropTypes.bool,
    boundaries: PropTypes.shape({
      cadastral: PropTypes.shape({
        coordinates: PropTypes.array.isRequired,
      }).isRequired,
      drone_ori: PropTypes.shape({
        coordinates: PropTypes.array,
      }),
    }).isRequired,
  }).isRequired,
  selected: PropTypes.bool.isRequired,
  dimmed: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
  boundaryMode: PropTypes.oneOf(['cadastral', 'drone', 'both']).isRequired,
}
