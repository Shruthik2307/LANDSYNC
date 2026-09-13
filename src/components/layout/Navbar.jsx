import React from 'react';
import { Layers, Map, BarChart3, UploadCloud, RefreshCw, Sparkles, Shield, Server } from 'lucide-react';

export default function Navbar({ activeTab, onChangeTab, onOpenIngestModal, onRunReconciliation }) {
  return (
    <header className="sticky top-0 z-[1000] bg-slate-900/90 backdrop-blur-xl border-b border-slate-800/80 px-6 py-3 shadow-2xl">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        
        {/* Brand & SIH Badge */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 via-teal-500 to-blue-600 flex items-center justify-center text-slate-950 font-black shadow-lg shadow-emerald-950/60">
            <Layers className="w-6 h-6 text-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black text-white tracking-wider">LANDSYNC</h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                SIH26013
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">
              AI-Enabled Geospatial Reconciliation & Integration Layer
            </p>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <nav className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => onChangeTab('map_queue')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              activeTab === 'map_queue'
                ? 'bg-emerald-500 text-slate-950 shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Map className="w-4 h-4" />
            Web-GIS Map & Queue
          </button>

          <button
            onClick={() => onChangeTab('analytics')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
              activeTab === 'analytics'
                ? 'bg-emerald-500 text-slate-950 shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Executive Analytics
          </button>
        </nav>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onRunReconciliation}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 flex items-center gap-1.5 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Re-Run AI Rules
          </button>

          <button
            onClick={onOpenIngestModal}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-lg shadow-emerald-950/50 flex items-center gap-2 transition-all"
          >
            <UploadCloud className="w-4 h-4" />
            Ingest Multi-Source Data
          </button>
        </div>

      </div>
    </header>
  );
}
