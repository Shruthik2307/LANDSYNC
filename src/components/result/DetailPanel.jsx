import React, { useEffect } from 'react'
import ConfidenceDial from '../ui/ConfidenceDial'
import { priorityOf } from '../../validation'
import { X, FileSearch } from 'lucide-react'

export default function DetailPanel({ parcel, onClose }) {
  // Allow closing via Escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && onClose) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  if (!parcel) {
    return (
      <div className="absolute bottom-4 left-4 right-4 sm:right-auto sm:w-96 p-3 rounded-lg bg-slate-900/80 backdrop-blur-md border border-slate-800 text-xs text-slate-400 font-mono shadow-xl z-[600] flex items-center gap-2 select-none">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        <span>Select a parcel on the map or in the queue to inspect its reconciliation.</span>
      </div>
    )
  }

  const issue = parcel.geometry_conflict 
    ? 'Boundary shift detected' 
    : parcel.attribute_conflict 
    ? 'Attribute mismatch detected' 
    : parcel.duplicate_id 
    ? 'Duplicate parcel ID detected' 
    : 'Sources agree'

  const priority = priorityOf(parcel)
  const area = Math.round((Number(parcel.area_difference) || 0) * 100) / 100
  const reason = parcel.geometry_conflict && area !== 0 
    ? `Lowered by a ${Math.abs(area)} m² boundary mismatch between cadastral and municipal sources.` 
    : parcel.attribute_conflict 
    ? 'Lowered by a mismatch in the source attributes.' 
    : parcel.duplicate_id 
    ? 'Lowered because this parcel ID appears more than once.' 
    : 'No conflict fields were reported by the source records.'

  const geometryFactor = parcel.geometry_conflict ? 'affected' : 'clear'
  const attributeFactor = parcel.attribute_conflict ? 'affected' : 'clear'

  const isHigh = priority === 'HIGH'
  const isMed = priority === 'MEDIUM'

  return (
    <section 
      className="detail-panel absolute bottom-4 left-4 right-4 z-[600] p-4 sm:p-5 rounded-2xl bg-[#070D1A]/95 backdrop-blur-2xl border border-cyan-500/25 shadow-[0_20px_60px_rgba(0,0,0,0.8),0_0_20px_rgba(0,240,255,0.1)] animate-fadeIn font-sans"
      aria-label={`Details for parcel ${parcel.parcel_id}`}
    >
      {/* Header Strip */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <FileSearch size={16} />
          </div>
          <div>
            <span className="text-[9px] font-mono text-cyan-400 uppercase tracking-widest block">
              SELECTED PARCEL INTELLIGENCE
            </span>
            <div className="flex items-center gap-2">
              <h2 className="text-xl sm:text-2xl font-bold font-mono text-white tracking-tight detail-id">
                {String(parcel.parcel_id)}
              </h2>
              <span className={`text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded border priority priority--${priority.toLowerCase()} ${
                isHigh ? 'bg-red-500/20 text-red-300 border-red-500/40' : isMed ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              }`}>
                {priority} PRIORITY
              </span>
              {parcel.duplicate_id && (
                <span className="text-[10px] font-mono uppercase bg-red-500/20 text-red-300 border border-red-500/40 px-1.5 py-0.5 rounded">
                  DUPLICATE RECORD
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:border-slate-700 transition-colors close-button"
          aria-label="Close parcel details"
          title="Close inspector (Esc)"
        >
          <X size={16} />
        </button>
      </div>

      {/* Main Analytical Grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-center">
        {/* Left Column: Confidence Radial Gauge */}
        <div className="md:col-span-3 flex flex-col items-center justify-center p-3 rounded-xl bg-slate-950/50 border border-slate-800/80">
          <ConfidenceDial value={Number(parcel.confidence) || 0} />
          <div className="mt-2 text-center">
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              CONFIDENCE MATRIX
            </span>
          </div>
        </div>

        {/* Middle Column: Findings & Attributes Breakdown */}
        <div className="md:col-span-5 space-y-3">
          <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800/80 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 font-mono text-[10px] uppercase">ANALYSIS FINDING</span>
              <span className={`font-mono font-semibold text-xs ${
                parcel.geometry_conflict ? 'text-amber-400' : parcel.attribute_conflict ? 'text-purple-400' : 'text-emerald-400'
              }`}>
                {issue}
              </span>
            </div>

            <div className="text-xs text-slate-300 font-mono pt-1">
              <span>Confidence factors: </span>
              <strong className="text-slate-100">Geometry {geometryFactor} · Attributes {attributeFactor}</strong>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed font-sans pt-1">
              {reason}
            </p>
          </div>

          {/* Metric Stats */}
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">AREA VARIANCE</span>
              <span className="text-sm font-bold text-slate-100">{area} m²</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
              <span className="text-[10px] text-slate-500 uppercase block">RECONCILIATION</span>
              <span className="text-sm font-bold text-cyan-400">
                {parcel.geometry_conflict ? 'Mismatch' : 'Consensus'}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Recommendation & Next Action */}
        <div className="md:col-span-4 p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-500/20 flex flex-col justify-between h-full space-y-2">
          <div>
            <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block font-semibold">
              RECOMMENDED ACTION
            </span>
            <strong className="text-sm text-slate-100 block mt-1">
              {issue}
            </strong>
            <p className="text-xs text-slate-300 mt-1 leading-relaxed">
              {parcel.recommendation || 'Review source records'}
            </p>
          </div>

          <div className="pt-2">
            <div className="text-[10px] font-mono text-slate-500 uppercase">
              AUTHORITY: Human Verification Required
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
