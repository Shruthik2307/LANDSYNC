import React from 'react'
import ConfidenceDial from './ConfidenceDial'
import { priorityOf } from '../../validation'

export default function QueueRow({ parcel, selected, onSelect }) {
  const priority = priorityOf(parcel)
  const isHigh = priority === 'HIGH'
  const isMed = priority === 'MEDIUM'
  const areaDiff = Number(parcel.area_difference) || 0

  return (
    <button
      className={`w-full text-left p-3 rounded-lg transition-all duration-150 relative border font-mono ${
        selected
          ? 'bg-cyan-950/40 border-cyan-400 shadow-[0_0_15px_rgba(0,240,255,0.15)] ring-1 ring-cyan-400/50'
          : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-800/60 hover:border-slate-700'
      }`}
      onClick={() => onSelect(parcel)}
      aria-pressed={selected}
    >
      {/* Selected Indicator Bar */}
      {selected && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-cyan-400 rounded-r shadow-[0_0_8px_rgba(0,240,255,0.8)]" />
      )}

      {/* Row Header: Parcel ID & Priority */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-xs font-bold text-slate-100 tracking-wider truncate parcel-id">
            {String(parcel.parcel_id)}
          </span>
          {parcel.duplicate_id && (
            <span className="duplicate-flag inline-flex items-center gap-0.5 px-1 py-0.2 text-[9px] font-mono uppercase rounded bg-red-500/20 text-red-300 border border-red-500/40">
              dup
            </span>
          )}
        </div>

        {/* Priority Badge */}
        <span
          className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border priority priority--${priority.toLowerCase()} ${
            isHigh
              ? 'bg-red-500/15 text-red-300 border-red-500/30'
              : isMed
              ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
          }`}
        >
          {priority}
        </span>
      </div>

      {/* Row Footer: Confidence Score & Discrepancy Metres */}
      <div className="flex items-center justify-between text-slate-400 text-[11px]">
        <div className="flex items-center gap-2 queue-confidence">
          <ConfidenceDial value={Number(parcel.confidence) || 0} compact />
          <span className="text-[10px] text-slate-400 font-mono">confidence</span>
        </div>

        <div className="text-right area-delta">
          <span className="text-[10px] font-mono">
            {parcel.geometry_conflict && parcel.attribute_conflict ? (
              <span className="text-red-400">Geom & Attr Conflict</span>
            ) : parcel.geometry_conflict ? (
              <span className="text-amber-400">Δ {Math.round(areaDiff * 100) / 100} m²</span>
            ) : parcel.attribute_conflict ? (
              <span className="text-purple-400">Attr Mismatch</span>
            ) : (
              <span className="text-emerald-400">Aligned</span>
            )}
          </span>
        </div>
      </div>
    </button>
  )
}
