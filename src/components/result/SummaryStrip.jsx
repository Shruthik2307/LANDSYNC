import React from 'react'
import { priorityOf } from '../../validation'
import { AlertTriangle, AlertCircle, CheckCircle2 } from 'lucide-react'

export default function SummaryStrip({ parcels = [] }) {
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

      {/* Source Agreement Telemetry (Right Side) */}
      <div className="hidden lg:flex items-center gap-4 text-[11px] shrink-0">
        <div className="flex items-center gap-1.5 text-slate-400">
          <span className="text-slate-500">CONSENSUS SCORE:</span>
          <span className="font-bold text-cyan-400 bg-cyan-950/50 px-1.5 py-0.5 rounded border border-cyan-500/30">
            {avgConfidence}%
          </span>
        </div>

        <div className="flex items-center gap-3 pl-3 border-l border-slate-800 text-[10px] text-slate-400">
          <span className="flex items-center gap-1 text-slate-300">
            <span className="text-cyan-400 font-bold">✓</span> Cadastral RoR
          </span>
          <span className="flex items-center gap-1 text-slate-300">
            <span className="text-amber-400 font-bold">✓</span> Drone ORI
          </span>
          <span className="flex items-center gap-1 text-slate-300">
            <span className="text-emerald-400 font-bold">✓</span> Sentinel-2
          </span>
        </div>
      </div>
    </div>
  )
}
