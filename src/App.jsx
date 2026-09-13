import React, { useState, useEffect } from 'react';
import Navbar from './components/layout/Navbar';
import LandsyncMap from './components/gis/LandsyncMap';
import ConflictResolutionQueue from './components/reconciliation/ConflictResolutionQueue';
import ExecutiveDashboard from './components/analytics/ExecutiveDashboard';
import DataIngestionUpload from './components/ingestion/DataIngestionUpload';
import { INITIAL_PARCELS } from './data/landsyncData';
import { runBatchReconciliation } from './services/reconciliationEngine';
import { Layers, Server, Code2, CheckCircle2, ShieldCheck, Sparkles, Terminal } from 'lucide-react';

export default function App() {
  const [parcels, setParcels] = useState([]);
  const [selectedParcelId, setSelectedParcelId] = useState('1042');
  const [activeTab, setActiveTab] = useState('map_queue'); // 'map_queue' | 'analytics' | 'backend_api'
  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);
  const [notification, setNotification] = useState(null);

  // Active GIS Layers State
  const [activeLayers, setActiveLayers] = useState({
    cadastral: true,
    drone_ori: true,
    ground_truthing: true,
    conflicts: true
  });

  // Initialize parcels with AI reconciliation engine scoring
  useEffect(() => {
    const reconciled = runBatchReconciliation(INITIAL_PARCELS);
    setParcels(reconciled);
  }, []);

  const handleToggleLayer = (layerKey) => {
    setActiveLayers(prev => ({
      ...prev,
      [layerKey]: !prev[layerKey]
    }));
  };

  const handleRunReconciliation = () => {
    const refreshed = runBatchReconciliation(parcels);
    setParcels(refreshed);
    showToast("AI Reconciliation Engine re-computed 100% of spatial & attribute rules!");
  };

  const handleResolveParcel = (parcelId) => {
    setParcels(prev =>
      prev.map(p => {
        if (p.parcel_id === parcelId) {
          return {
            ...p,
            priority: 'LOW',
            confidence: 99,
            geometry_conflict: false,
            attribute_conflict: false,
            recommendation: 'Auto-Harmonized — Manually approved by Authorized GIS Verification Officer.'
          };
        }
        return p;
      })
    );
    showToast(`Parcel #${parcelId} approved & harmonized!`);
  };

  const handleProcessNewData = () => {
    showToast("Multi-source geospatial dataset ingested & CRS transformed successfully!");
  };

  const showToast = (message) => {
    setNotification(message);
    setTimeout(() => {
      setNotification(null);
    }, 3500);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      
      {/* Top Glassmorphic Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        onChangeTab={setActiveTab}
        onOpenIngestModal={() => setIsIngestModalOpen(true)}
        onRunReconciliation={handleRunReconciliation}
      />

      {/* Live Toast Notification */}
      {notification && (
        <div className="fixed top-20 right-6 z-[3000] bg-emerald-500 text-slate-950 px-4 py-2.5 rounded-xl font-bold text-xs shadow-2xl flex items-center gap-2 animate-in slide-in-from-top-4 duration-300">
          <Sparkles className="w-4 h-4" />
          {notification}
        </div>
      )}

      {/* Main App Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        
        {/* Tab 1: Web-GIS Map & Reconciliation Queue */}
        {activeTab === 'map_queue' && (
          <div className="space-y-6">
            
            {/* Interactive Web-GIS Map */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  Web-GIS Interactive Parcel Map & Layer Comparison
                </h2>
                <div className="text-xs text-slate-400 font-mono">
                  Coordinates: EPSG:4326 | High-Res Drone ORI Overlay Enabled
                </div>
              </div>

              <LandsyncMap
                parcels={parcels}
                selectedParcelId={selectedParcelId}
                onSelectParcel={setSelectedParcelId}
                activeLayers={activeLayers}
                onToggleLayer={handleToggleLayer}
              />
            </div>

            {/* Conflict Resolution Queue & Explainable AI Drawer */}
            <ConflictResolutionQueue
              parcels={parcels}
              selectedParcelId={selectedParcelId}
              onSelectParcel={setSelectedParcelId}
              onResolveParcel={handleResolveParcel}
            />

          </div>
        )}

        {/* Tab 2: Executive Analytics Dashboard */}
        {activeTab === 'analytics' && (
          <ExecutiveDashboard parcels={parcels} />
        )}
      </main>

      {/* Multi-Source Ingestion Modal */}
      <DataIngestionUpload
        isOpen={isIngestModalOpen}
        onClose={() => setIsIngestModalOpen(false)}
        onProcessNewData={handleProcessNewData}
      />

    </div>
  );
}
