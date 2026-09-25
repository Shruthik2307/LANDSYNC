import React, { useEffect, useState } from 'react'
import { ImageOverlay, TileLayer } from 'react-leaflet'

export default function SatelliteLayer({ 
  parcel, 
  onStatus, 
  onUnavailable, 
  bounds, 
  cachedAsset,
}) {
  const parcelId = String(parcel?.parcel_id || '')
  const [tier, setTier] = useState('sentinel') // 'sentinel' | 'offline'

  useEffect(() => {
    if (tier === 'offline') {
      if (onStatus) onStatus('Cached observation view (fallback imagery)')
    } else {
      // Honest label: this is Esri World Imagery — a dated mosaic, not a live feed,
      // and not established as the latest capture available for the location.
      if (onStatus) onStatus('Satellite imagery · dated mosaic (not live)')
    }
  }, [onStatus, parcelId, tier])

  if (!bounds) return null

  // Tier B / Offline Fallback using cached SVG/raster asset
  if (tier === 'offline') {
    if (!cachedAsset) return null
    return (
      <ImageOverlay
        url={cachedAsset}
        bounds={bounds}
        opacity={0.8}
        attribution="LANDSYNC · Cached Satellite Composite (Tier B)"
        eventHandlers={{
          error: () => {
            // Silently notify parent if even offline asset is missing
            if (onUnavailable) onUnavailable(parcelId)
          },
        }}
      />
    )
  }

  // Primary observation imagery via the backend proxy (Esri World Imagery,
  // with real per-location acquisition metadata served by /api/imagery/info).
  const primaryTileUrl = '/api/satellite-tile/{z}/{x}/{y}'

  return (
    <TileLayer
      key={`${parcelId}-${tier}`}
      url={primaryTileUrl}
      opacity={0.8}
      attribution="Esri World Imagery · dated mosaic (not live)"
      eventHandlers={{
        tileerror: () => {
          // Configured fallback (clearly identified, not a silent swap)
          if (cachedAsset) {
            setTier('offline')
            if (onStatus) onStatus('Source temporarily unavailable — showing cached fallback imagery')
          } else {
            if (onUnavailable) onUnavailable(parcelId)
          }
        },
      }}
    />
  )
}
