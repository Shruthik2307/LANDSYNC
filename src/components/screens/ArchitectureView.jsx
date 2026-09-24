import React from 'react'
import BrandHeader from '../layout/BrandHeader'
import { Layers, ShieldCheck, Database, Cpu, MapPin, Eye, Compass, ShieldAlert } from 'lucide-react'

export default function ArchitectureView({ demoMode, onToggleDemo, onClose }) {
  const stages = [
    { name: 'Sources', icon: Database, desc: 'Cadastral RoR, Drone Surveys, Sentinel-2 L2A' },
    { name: 'Ingestion', icon: Layers, desc: 'GeoJSON, SHP, CSV, TIFF Multi-format parser' },
    { name: 'CRS Normalization', icon: Compass, desc: 'Reprojection into WGS84 (EPSG:4326)' },
    { name: 'Spatial Matching', icon: MapPin, desc: 'Polygon intersection & Hausdorff distance' },
    { name: 'Conflict Detection', icon: ShieldAlert, desc: 'Boundary shifts, overlaps, duplicate parcel IDs' },
    { name: 'Confidence Scoring', icon: Cpu, desc: 'Weighted algorithmic consensus calculation' },
    { name: 'Verification Queue', icon: Eye, desc: 'Priority-sorted human inspection stream' },
    { name: 'PostGIS', icon: Database, desc: 'Spatial database index & topological storage' },
    { name: 'FastAPI', icon: Layers, desc: 'High-performance REST API services' },
    { name: 'Dashboard', icon: ShieldCheck, desc: 'GIS tactical command interface' },
  ]

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30">
      <BrandHeader 
        step="How it works" 
        demoMode={demoMode} 
        onToggleDemo={onToggleDemo} 
        onArchitecture={onClose} 
        architectureOpen 
      />

      <main className="flex-1 flex items-center justify-center p-4 sm:p-8 md:p-12 relative overflow-hidden">
        {/* Ambient Glows */}
        <div className="absolute top-1/3 left-1/3 w-[600px] h-[600px] bg-cyan-500/5 blur-[160px] rounded-full pointer-events-none" />

        <div className="w-full max-w-5xl space-y-8 relative z-10">
          {/* Header */}
          <div className="text-center space-y-3">
            <span className="text-[11px] font-mono uppercase tracking-widest text-cyan-400 bg-cyan-950/70 border border-cyan-500/30 px-3 py-1 rounded-full">
              System Architecture & Evidence Pipeline
            </span>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
              How LANDSYNC connects the evidence.
            </h1>
            <p className="text-slate-400 text-sm max-w-2xl mx-auto leading-relaxed">
              Each source stays traceable while automated reconciliation turns raw discrepancies into a focused, priority-ranked verification queue for authorized survey personnel.
            </p>
          </div>

          {/* Architecture Pipeline Nodes Grid */}
          <div 
            className="p-6 sm:p-8 rounded-2xl bg-slate-900/80 backdrop-blur-xl border border-cyan-500/20 shadow-2xl space-y-6"
            aria-label="LANDSYNC architecture pipeline"
          >
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {stages.map((stage, index) => {
                const Icon = stage.icon
                return (
                  <div
                    key={stage.name}
                    className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-cyan-500/40 hover:bg-slate-900/60 transition-all duration-200 group flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[11px] font-mono text-cyan-400 font-bold">
                          0{index + 1}
                        </span>
                        <Icon size={14} className="text-slate-400 group-hover:text-cyan-400 transition-colors" />
                      </div>
                      <span className="text-xs font-bold text-slate-200 block mb-1">
                        {stage.name}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-snug font-mono mt-1">
                      {stage.desc}
                    </p>
                  </div>
                )
              })}
            </div>

            {/* Legal & Governance Boundary Note */}
            <div className="p-4 sm:p-5 rounded-xl bg-amber-500/5 border border-amber-500/25 text-xs text-slate-300 leading-relaxed font-sans space-y-2">
              <div className="flex items-center gap-2 text-amber-300 font-bold text-sm">
                <ShieldAlert size={16} className="text-amber-400" />
                <strong>Where LANDSYNC fits</strong>
              </div>
              <p className="text-slate-400">
                This is a reconciliation and quality-control layer, not a replacement for Bhuvan, Bhu-Naksha, or NAKSHA. It does not legally decide ownership, encroachment, or title; its outputs are recommendations for authorized human verification. All parcel data shown here is synthetic demo data.
              </p>
            </div>
          </div>

          {/* Close / Return CTA */}
          <div className="text-center">
            <button
              onClick={onClose}
              className="px-6 py-2.5 rounded-lg bg-cyan-400 text-black font-bold text-xs tracking-wide hover:bg-white shadow-[0_0_20px_rgba(0,240,255,0.3)] transition-all"
            >
              Return to Workspace
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
