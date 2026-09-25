import { useRef, useState } from 'react'
import { TileLayer } from 'react-leaflet'

const DEFAULT_CARTO_KEY = 'cb1_3jja_1_c1643a41b30964720658c0ac'
const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || DEFAULT_CARTO_KEY
// CARTO basemaps require ?key= on the /rastertiles/ path (not the legacy /dark_all/ path).
const CARTO_TILE_URL = `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(CARTO_API_KEY)}`
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
