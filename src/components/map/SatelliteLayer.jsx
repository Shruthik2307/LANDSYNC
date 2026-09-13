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
      if (onStatus) onStatus('Cached satellite view (Tier B fallback)')
    } else {
      if (onStatus) onStatus('Sentinel-2 L2A Multi-spectral · Active Satellite Layer')
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

  // Primary Sentinel-2 Imagery via Backend Proxy
  const primaryTileUrl = '/api/satellite-tile/{z}/{x}/{y}'

  return (
    <TileLayer
      key={`${parcelId}-${tier}`}
      url={primaryTileUrl}
      opacity={0.8}
      attribution="Copernicus Sentinel-2 · European Space Agency"
      eventHandlers={{
        tileerror: () => {
          // Silently fall back to Tier B cached asset without user-facing error
          if (cachedAsset) {
            setTier('offline')
            if (onStatus) onStatus('Cached satellite view (Tier B fallback)')
          } else {
            if (onUnavailable) onUnavailable(parcelId)
          }
        },
      }}
    />
  )
}
