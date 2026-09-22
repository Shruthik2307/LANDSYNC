import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

export default function MapViewport({ selectedParcel }) {
  const map = useMap()
  useEffect(() => {
    if (!selectedParcel) return
    const coordinates = selectedParcel?.boundaries?.cadastral?.coordinates?.[0]
    if (coordinates) {
      const points = coordinates.map(([lng, lat]) => [lat, lng])
      map.fitBounds(points, { padding: [80, 80], maxZoom: 17, animate: !window.matchMedia('(prefers-reduced-motion: reduce)').matches })
    }
  }, [map, selectedParcel])
  return null
}
