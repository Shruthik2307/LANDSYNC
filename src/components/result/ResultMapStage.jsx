import React from 'react'
import { MapContainer, useMap } from 'react-leaflet'
import { Satellite, Plus, Minus, ShieldAlert } from 'lucide-react'
import BaseMapLayer from '../map/BaseMapLayer'
import MapViewport from '../map/MapViewport'
import SatelliteLayer from '../map/SatelliteLayer'
import ParcelShape from '../map/ParcelShape'

// Helper component for custom zoom controls (rendered as a Leaflet control inside MapContainer)
function CustomZoomControls() {
  const map = useMap()
  return (
    <div className="leaflet-top leaflet-right" style={{ top: '64px', right: '12px', pointerEvents: 'auto', zIndex: 1000 }}>
      <div className="leaflet-control flex flex-col rounded-lg bg-[#070D1A]/90 border border-cyan-500/20 shadow-lg overflow-hidden backdrop-blur-md">
        <button
          onClick={() => map.zoomIn()}
          className="p-2 text-slate-300 hover:text-cyan-400 hover:bg-cyan-500/10 border-b border-slate-800 transition-colors"
          title="Zoom in"
          aria-label="Zoom in"
        >
          <Plus size={14} />
        </button>
        <button
          onClick={() => map.zoomOut()}
          className="p-2 text-slate-300 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
          title="Zoom out"
          aria-label="Zoom out"
        >
          <Minus size={14} />
        </button>
      </div>
    </div>
  )
}

export default function ResultMapStage({
  selected,
  setSelected,
  boundaryMode,
  setBoundaryMode,
  satelliteMode,
  setSatelliteMode,
  satelliteStatus,
  setSatelliteStatus,
  unavailableSatelliteParcels,
  setUnavailableSatelliteParcels,
  orderedParcels = [],
  matchesFilter,
  invalidParcels = [],
  satelliteEnabled = true,
  sentinelHubInstanceId,
  cachedSatelliteUrl
}) {
  const selectedParcelId = String(selected?.parcel_id || '')
  const canShowSatellite = Boolean(selected) && (satelliteEnabled && (sentinelHubInstanceId || cachedSatelliteUrl(selected) || !sentinelHubInstanceId)) && !unavailableSatelliteParcels.has(selectedParcelId)

  function selectParcel(parcel) {
    setSelected(parcel)
    setSatelliteMode(false)
    setSatelliteStatus(null)
  }

  const getBounds = (parcel) => {
    const points = parcel?.boundaries?.cadastral?.coordinates?.[0]
    if (!points) return null
    const lats_raw = points.map(p => p[1])
    const lngs_raw = points.map(p => p[0])
    return [
      [Math.min(...lats_raw), Math.min(...lngs_raw)],
      [Math.max(...lats_raw), Math.max(...lngs_raw)]
    ]
  }

  return (
    <section 
      className="relative w-full h-full overflow-hidden bg-[#030712] select-none"
      aria-label="Parcel reconciliation map"
    >
      {/* Top Floating GIS Control Bar */}
      <div className="absolute top-3 left-3 right-3 z-[500] pointer-events-none flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5">
        
        {/* Left: Map Stage Identifier */}
        <div className="pointer-events-auto px-3.5 py-2 rounded-xl bg-[#070D1A]/90 backdrop-blur-xl border border-cyan-500/20 shadow-xl flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <div>
            <span className="text-[9px] font-mono text-cyan-400 uppercase tracking-widest block font-semibold">
              GIS RECONCILIATION VIEWPORT
            </span>
            <span className="text-xs font-bold text-slate-100 font-mono">
              {selected ? `PARCEL ${selected.parcel_id}` : 'SURVEY SECTOR ALPHA'}
            </span>
          </div>
        </div>

        {/* Right: Floating Tactical Layer & Boundary Controls */}
        <div className="pointer-events-auto flex items-center gap-2">
          {/* Boundary Filter Segmented Control */}
          <div 
            className="flex items-center rounded-lg bg-[#070D1A]/90 backdrop-blur-xl border border-cyan-500/20 p-1 shadow-xl font-mono text-xs"
            role="group" 
            aria-label="Boundary visibility"
          >
            {[
              { id: 'cadastral', label: 'Cadastral (RoR)' },
              { id: 'drone', label: 'Municipal (Survey)' },
              { id: 'both', label: 'Consensus (Both)' },
            ].map((mode) => (
              <button
                key={mode.id}
                onClick={() => { setBoundaryMode(mode.id); setSatelliteMode(false); }}
                className={`px-2.5 py-1 rounded text-[11px] transition-all duration-150 ${
                  boundaryMode === mode.id
                    ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30 shadow-[0_0_10px_rgba(0,240,255,0.15)]'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {mode.label}
              </button>
            ))}

            {/* Satellite Overlay Toggle */}
            {satelliteEnabled && canShowSatellite && (
              <button
                onClick={() => { 
                  setSatelliteMode((prev) => !prev)
                  setSatelliteStatus(null) 
                }}
                className={`ml-1 px-2.5 py-1 rounded text-[11px] flex items-center gap-1.5 transition-all duration-150 border ${
                  satelliteMode
                    ? 'bg-sky-500/20 text-sky-300 font-bold border-sky-400/50 shadow-[0_0_12px_rgba(56,189,248,0.2)]'
                    : 'text-slate-400 border-transparent hover:text-sky-300 hover:bg-sky-950/40'
                }`}
                aria-pressed={satelliteMode}
              >
                <Satellite size={12} className={satelliteMode ? 'text-sky-400 animate-pulse' : ''} />
                <span>+ Satellite</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Satellite Status Banner */}
      {satelliteMode && satelliteStatus && (
        <div 
          className="absolute bottom-16 right-3 z-[490] px-3 py-1.5 rounded-lg bg-[#070D1A]/90 backdrop-blur-md border border-sky-500/30 text-[11px] font-mono text-sky-300 shadow-xl flex items-center gap-2 animate-fadeIn"
          role="status"
        >
          <Satellite size={13} className="text-sky-400" />
          <span>{satelliteStatus}</span>
        </div>
      )}

      {/* CRS Warning if Invalid Coordinates */}
      {invalidParcels.length > 0 && (
        <div 
          className="absolute top-16 left-1/2 -translate-x-1/2 z-[490] px-3.5 py-1.5 rounded-lg bg-amber-500/10 backdrop-blur-md border border-amber-500/30 text-xs font-mono text-amber-300 shadow-xl flex items-center gap-2"
          role="status"
        >
          <ShieldAlert size={14} className="text-amber-400 shrink-0" />
          <span>This parcel&apos;s coordinates look off — check CRS normalization</span>
        </div>
      )}

      {/* Map Canvas (Centerpiece of the Application) */}
      <MapContainer 
        center={[17.388, 78.510]} 
        zoom={16} 
        zoomControl={false} 
        className="w-full h-full"
      >
        <BaseMapLayer />
        <MapViewport selectedParcel={selected} />
        <CustomZoomControls />

        {/* Satellite Layer with Silent Fallback */}
        {satelliteMode && selected && canShowSatellite && (
          <SatelliteLayer
            parcel={selected}
            bounds={getBounds(selected)}
            cachedAsset={cachedSatelliteUrl(selected)}
            sentinelHubInstanceId={sentinelHubInstanceId}
            satelliteEnabled={satelliteEnabled}
            onStatus={setSatelliteStatus}
            onUnavailable={(parcelId) => {
              setUnavailableSatelliteParcels((current) => new Set(current).add(parcelId))
              setSatelliteMode(false)
              setSatelliteStatus(null)
            }}
          />
        )}

        {/* Parcel Polygons */}
        {orderedParcels.map((parcel, index) => (
          <ParcelShape
            key={`${parcel.parcel_id}-${index}`}
            parcel={parcel}
            selected={selected?.parcel_id === parcel.parcel_id}
            dimmed={!matchesFilter(parcel)}
            onSelect={selectParcel}
            boundaryMode={boundaryMode}
          />
        ))}
      </MapContainer>

      {/* Bottom-Left Tactical Legend */}
      <div 
        className="absolute bottom-4 left-3 z-[490] p-2.5 sm:p-3 rounded-xl bg-[#070D1A]/90 backdrop-blur-xl border border-cyan-500/20 text-[10px] font-mono shadow-xl space-y-1.5 text-slate-300"
        aria-label="Map legend"
      >
        <div className="text-[9px] text-cyan-400/80 uppercase tracking-widest font-bold pb-1 border-b border-slate-800">
          GIS OVERLAY LEGEND
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-0.5 bg-cyan-400 inline-block shadow-[0_0_6px_rgba(0,240,255,0.8)]" />
          <span>Cadastral RoR (Source A)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-0.5 bg-amber-400 inline-block border-t border-dashed border-amber-400 shadow-[0_0_6px_rgba(255,184,0,0.8)]" />
          <span>Municipal Survey (Source B)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
          <span>High Priority Conflict</span>
        </div>
      </div>
    </section>
  )
}
