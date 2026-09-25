import React, { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, Tooltip, LayerGroup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Layers, Sliders } from 'lucide-react';


delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const ParcelLayer = React.memo(function ParcelLayer({ parcels, selectedParcelId, onSelectParcel, priorityColor }) {
  return (
    <LayerGroup>
      {parcels.map((parcel) => {
        const isSelected = parcel.parcel_id === selectedParcelId;
        const color = priorityColor(parcel.priority);
        return (
          <Polygon
            key={`cadastral-${parcel.parcel_id}`}
            positions={parcel.coordinates}
            pathOptions={{
              color: isSelected ? '#38bdf8' : color,
              weight: isSelected ? 4 : 2.5,
              fillColor: color,
              fillOpacity: isSelected ? 0.45 : 0.25
            }}
            eventHandlers={{ click: () => onSelectParcel(parcel.parcel_id) }}
          >
            <Tooltip sticky direction="top">
              <div className="p-1">
                <div className="font-bold text-slate-900">Parcel #{parcel.parcel_id}</div>
                <div className="text-xs text-slate-600">Owner: {parcel.owner_name}</div>
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </LayerGroup>
  );
});

function MapRecenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, 17, { duration: 1.2 });
  }, [center, map]);
  return null;
}

export default function LandsyncMap({ parcels, selectedParcelId, onSelectParcel, activeLayers, onToggleLayer }) {
  const [mapTile, setMapTile] = useState('satellite');
  const [droneOpacity, setDroneOpacity] = useState(0.65);

  const defaultCenter = [17.4468, 78.3765];
  const selectedParcel = parcels.find(p => p.parcel_id === selectedParcelId);
  const mapCenter = selectedParcel ? selectedParcel.coordinates[0] : defaultCenter;

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'HIGH': return '#ef4444';
      case 'MEDIUM': return '#f59e0b';
      case 'LOW': return '#10b981';
      default: return '#3b82f6';
    }
  };

  const cadastralLayer = useMemo(() => (
    <ParcelLayer
      parcels={parcels}
      selectedParcelId={selectedParcelId}
      onSelectParcel={onSelectParcel}
      priorityColor={getPriorityColor}
    />
  ), [parcels, selectedParcelId, onSelectParcel]);

  const droneLayer = useMemo(() => (
    <LayerGroup>
      {parcels.map((parcel) => parcel.drone_coordinates && (
        <Polygon
          key={`drone-${parcel.parcel_id}`}
          positions={parcel.drone_coordinates}
          pathOptions={{ color: '#10b981', weight: 2, fillColor: '#10b981', fillOpacity: droneOpacity * 0.35, dashArray: '3, 3' }}
        />
      ))}
    </LayerGroup>
  ), [parcels, droneOpacity]);

  return (
    <div className="relative w-full h-[620px] rounded-2xl overflow-hidden border border-slate-700/60 shadow-2xl bg-slate-900">

      <div className="absolute top-4 left-4 z-[1000] flex flex-wrap items-center gap-2 bg-slate-900/90 backdrop-blur-md px-4 py-2.5 rounded-xl border border-slate-700/80 shadow-lg">
        <div className="flex items-center gap-2 pr-3 border-r border-slate-700">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Web-GIS Layers</span>
        </div>

        <button
          onClick={() => onToggleLayer('cadastral')}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeLayers.cadastral ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Cadastral Boundary
        </button>

        <button
          onClick={() => onToggleLayer('drone_ori')}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeLayers.drone_ori ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-500"></span> Drone ORI Layer
        </button>

        <button
          onClick={() => onToggleLayer('ground_truthing')}
          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
            activeLayers.ground_truthing ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50' : 'bg-slate-800 text-slate-400'
          }`}
        >
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span> GNSS GT Points
        </button>

        <div className="ml-auto flex items-center gap-1 bg-slate-800 p-0.5 rounded-lg border border-slate-700">
          <button onClick={() => setMapTile('satellite')} className={`px-2 py-0.5 text-[11px] rounded font-medium ${mapTile === 'satellite' ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400'}`}>Satellite</button>
          <button onClick={() => setMapTile('dark')} className={`px-2 py-0.5 text-[11px] rounded font-medium ${mapTile === 'dark' ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400'}`}>Dark Vector</button>
        </div>
      </div>

      {activeLayers.drone_ori && (
        <div className="absolute bottom-4 left-4 z-[1000] flex items-center gap-3 bg-slate-900/90 backdrop-blur-md px-3.5 py-2 rounded-xl border border-slate-700 shadow-lg">
          <Sliders className="w-4 h-4 text-cyan-400" />
          <span className="text-xs text-slate-300 font-medium">Drone Opacity:</span>
          <input type="range" min="0.1" max="1.0" step="0.05" value={droneOpacity} onChange={(e) => setDroneOpacity(parseFloat(e.target.value))} className="w-24 accent-cyan-500 cursor-pointer" />
          <span className="text-xs font-bold text-cyan-400 w-8">{Math.round(droneOpacity * 100)}%</span>
        </div>
      )}

      <MapContainer center={defaultCenter} zoom={16} scrollWheelZoom={true} preferCanvas={true} className="w-full h-full">
        <MapRecenter center={mapCenter} />
        {mapTile === 'satellite' ? (
          <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
        ) : (
          <TileLayer url={`https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${encodeURIComponent(import.meta.env.VITE_CARTO_API_KEY || '')}`} />
        )}

        {activeLayers.cadastral && cadastralLayer}
        {activeLayers.drone_ori && droneLayer}
      </MapContainer>
    </div>
  );
}
