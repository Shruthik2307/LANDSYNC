import React from 'react'
import { priorityOf } from '../../validation'
import { AlertTriangle, AlertCircle, CheckCircle2, RefreshCw, Loader2, BarChart3, Map } from 'lucide-react'

export default function SummaryStrip({ 
  parcels = [], 
  onProcess, 
  processStatus = 'idle', 
  processError = '',
  viewMode = 'map',
  onToggleView
}) {
  const count = (priority) => parcels.filter((parcel) => priorityOf(parcel) === priority).length
  const highCount = count('HIGH')
  const medCount = count('MEDIUM')
  const lowCount = count('LOW')

  // Calculate average confidence for display
  const avgConfidence = parcels.length 
    ? Math.round(parcels.reduce((acc, p) => acc + (Number(p.confidence) || 0), 0) / parcels.length)
    : 0

  return (
    <div className="h-12 bg-[#050B17] border-b border-cyan-500/15 px-4 md:px-6 flex items-center justify-between overflow-x-auto text-xs font-mono select-none">
      {/* Metrics Section */}
      <div className="flex items-center gap-4 sm:gap-6 shrink-0">
        {/* Total Parcels */}
        <div className="summary-total flex items-center gap-2 pr-4 border-r border-slate-800">
          <span className="text-[10px] text-cyan-400/80 uppercase tracking-wider font-semibold">
            SURVEYED:
          </span>
          <span className="text-sm font-bold text-slate-100">{parcels.length}</span>
          <span className="text-[11px] text-slate-400">parcels</span>
        </div>

        {/* High Priority Conflicts */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-red-400">
          <AlertCircle size={13} className="text-red-400" />
          <span className="font-bold">{highCount}</span>
          <span className="text-[10px] text-red-300/80 uppercase">High Priority</span>
        </div>

        {/* Medium Priority */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <AlertTriangle size={13} className="text-amber-400" />
          <span className="font-bold">{medCount}</span>
          <span className="text-[10px] text-amber-300/80 uppercase">Medium</span>
        </div>

        {/* Low / Verified Clear */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
          <CheckCircle2 size={13} className="text-emerald-400" />
          <span className="font-bold">{lowCount}</span>
          <span className="text-[10px] text-emerald-300/80 uppercase">Consensus Clear</span>
        </div>
      </div>

      {/* Source Agreement Telemetry & Process Trigger (Right Side) */}
      <div className="flex items-center gap-4 text-[11px] shrink-0">
        <div className="hidden lg:flex items-center gap-1.5 text-slate-400">
          <span className="text-slate-500">CONSENSUS SCORE:</span>
          <span className="font-bold text-cyan-400 bg-cyan-950/50 px-1.5 py-0.5 rounded border border-cyan-500/30">
            {avgConfidence}%
          </span>
        </div>

        <div className="hidden xl:flex items-center gap-3 pl-3 border-l border-slate-800 text-[10px] text-slate-400">
          <span className="flex items-center gap-1 text-slate-300" title="Cadastral Revenue Records">
            <span className="text-cyan-400 font-bold">✓</span> Cadastral RoR
          </span>
          <span className="flex items-center gap-1 text-slate-300" title="Municipal Geospatial Survey">
            <span className="text-amber-400 font-bold">✓</span> Municipal Survey
          </span>
          <span className="flex items-center gap-1 text-slate-300" title="Satellite Base Verification">
            <span className="text-emerald-400 font-bold">✓</span> Sentinel-2
          </span>
        </div>

        {/* View Switcher: GIS Map vs Analytics Dashboard */}
        {onToggleView && (
          <div className="flex items-center p-0.5 rounded-lg bg-slate-950 border border-slate-800 ml-2">
            <button
              onClick={() => onToggleView('map')}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center gap-1.5 ${
                viewMode === 'map'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-[0_0_8px_rgba(0,240,255,0.15)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Switch to GIS Map View"
            >
              <Map size={12} />
              <span>Map View</span>
            </button>
            <button
              onClick={() => onToggleView('dashboard')}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center gap-1.5 ${
                viewMode === 'dashboard'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-[0_0_8px_rgba(0,240,255,0.15)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Switch to Executive Analytics Dashboard"
            >
              <BarChart3 size={12} />
              <span>Dashboard</span>
            </button>
          </div>
        )}

        {/* Process / Reconcile Button */}
        {onProcess && (
          <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
            <button
              onClick={onProcess}
              disabled={processStatus === 'processing'}
              className={`process-button inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-mono font-semibold transition-all border ${
                processStatus === 'processing'
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/50 animate-pulse'
                  : processStatus === 'complete'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/50'
                  : processStatus === 'error'
                  ? 'bg-red-500/20 text-red-300 border-red-400/50'
                  : 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border-cyan-500/30 hover:border-cyan-400'
              }`}
              title="Run LANDSYNC engine reconciliation (POST /api/process)"
            >
              {processStatus === 'processing' ? (
                <>
                  <Loader2 size={13} className="animate-spin text-cyan-400" />
                  <span>Reconciling…</span>
                </>
              ) : processStatus === 'complete' ? (
                <>
                  <CheckCircle2 size={13} className="text-emerald-400" />
                  <span>Reconciled</span>
                </>
              ) : processStatus === 'error' ? (
                <>
                  <AlertCircle size={13} className="text-red-400" />
                  <span>Error</span>
                </>
              ) : (
                <>
                  <RefreshCw size={13} className="text-cyan-400" />
                  <span>Process Engine</span>
                </>
              )}
            </button>
            {processError && (
              <span className="text-red-400 text-[10px]" title={processError}>
                Failed
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
