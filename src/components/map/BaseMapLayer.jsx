import { useRef, useState } from 'react'
import { TileLayer } from 'react-leaflet'

const DEFAULT_CARTO_KEY = 'cb1_3jja_1_c1643a41b30964720658c0ac'
const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || DEFAULT_CARTO_KEY
// CARTO basemaps require ?key= on the /rastertiles/ path (not the legacy /dark_all/ path).
const CARTO_TILE_URL = `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(CARTO_API_KEY)}`
const CARTO_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'

const SATELLITE_TILE_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const SATELLITE_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'

export default function BaseMapLayer({ mode = 'dark' }) {
  const [source, setSource] = useState('carto')
  const failCount = useRef(0)

  if (mode === 'satellite') {
    return (
      <TileLayer
        url={SATELLITE_TILE_URL}
        maxNativeZoom={19}
        maxZoom={22}
        attribution={SATELLITE_ATTRIBUTION}
        opacity={0.92}
      />
    )
  }

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
