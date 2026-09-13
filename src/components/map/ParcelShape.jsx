import React from 'react'
import { CircleMarker, Polygon } from 'react-leaflet'
import { priorityOf } from '../../validation'

export default function ParcelShape({ parcel, selected, dimmed, onSelect, boundaryMode }) {
  const coordinates = parcel?.boundaries?.cadastral?.coordinates?.[0]
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

  const droneCoordinates = parcel?.boundaries?.drone_ori?.coordinates?.[0]
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
