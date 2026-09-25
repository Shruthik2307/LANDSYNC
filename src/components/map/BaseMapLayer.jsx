import { useRef, useState } from 'react'
import { TileLayer } from 'react-leaflet'

const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || ''
// CARTO basemaps require ?key= on the /rastertiles/ path (not the legacy /dark_all/ path).
// Without a valid key, tiles are served with an "API KEY REQUIRED" watermark.
const CARTO_TILE_URL = CARTO_API_KEY
  ? `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(CARTO_API_KEY)}`
  : 'https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key='
const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

export default function BaseMapLayer() {
  const [source, setSource] = useState('carto')
  const failCount = useRef(0)

  if (source === 'osm') {
    return (
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        opacity={0.65}
      />
    )
  }

  return (
    <TileLayer
      url={CARTO_TILE_URL}
      subdomains="abcd"
      maxNativeZoom={20}
      maxZoom={22}
      attribution={CARTO_ATTRIBUTION}
      opacity={0.88}
      eventHandlers={{
        tileerror: () => {
          failCount.current += 1
          if (failCount.current >= 8) setSource('osm')
        },
      }}
    />
  )
}
