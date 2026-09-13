import React from 'react'
import { Search, RefreshCw, X, AlertOctagon } from 'lucide-react'
import QueueRow from '../ui/QueueRow'

export default function QueuePanel({
  datasetId,
  parcels = [],
  conflicts = [],
  selected,
  setSelected,
  priorityFilter,
  setPriorityFilter,
  search,
  setSearch,
  onRestart,
  matchesFilter
}) {
  const filteredConflicts = conflicts.filter(matchesFilter)

  return (
    <aside 
      className="w-full h-full flex flex-col bg-[#070D1A]/90 backdrop-blur-xl border-l border-cyan-500/15 overflow-hidden"
      aria-label="Conflict queue"
    >
      {/* Panel Header */}
      <div className="p-3.5 sm:p-4 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-[9px] font-mono text-cyan-400 uppercase tracking-widest block">
              RECONCILIATION MONITOR
            </span>
            <div className="flex items-center gap-2 mt-0.5">
              <h2 className="text-base font-bold text-slate-100 tracking-tight flex items-center gap-2">
                <span>Conflict Queue</span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  {filteredConflicts.length}
                </span>
              </h2>
            </div>
          </div>

          {datasetId && (
            <div className="text-[10px] font-mono px-2 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400 max-w-[120px] truncate" title={datasetId}>
              {datasetId}
            </div>
          )}
        </div>

        {/* Filter & Search Bar */}
        <div className="space-y-2">
          {/* Search Box */}
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search parcel ID…"
              aria-label="Search parcel ID"
              className="w-full pl-8 pr-7 py-1.5 bg-slate-950/80 border border-slate-800 rounded text-xs text-slate-200 placeholder-slate-500 font-mono focus:border-cyan-400 focus:outline-none transition-colors"
            />
            {search && (
              <button 
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                title="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Priority Select */}
          <div className="flex items-center gap-2">
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              aria-label="Filter by priority"
              className="w-full py-1.5 px-2 bg-slate-950/80 border border-slate-800 rounded text-xs text-slate-300 font-mono focus:border-cyan-400 focus:outline-none transition-colors cursor-pointer"
            >
              <option value="ALL">All priorities ({conflicts.length})</option>
              <option value="HIGH">High Priority (Shift / Duplicate)</option>
              <option value="MEDIUM">Medium Priority (Variance)</option>
              <option value="LOW">Low / Minor Discrepancy</option>
            </select>
          </div>
        </div>
      </div>

      {/* Parcels List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredConflicts.length > 0 ? (
          filteredConflicts.map((parcel, idx) => (
            <QueueRow
              key={`${parcel.parcel_id}-${idx}`}
              parcel={parcel}
              selected={selected?.parcel_id === parcel.parcel_id}
              onSelect={setSelected}
            />
          ))
        ) : (
          <div className="h-48 flex flex-col items-center justify-center text-center p-4 text-slate-500 font-mono text-xs">
            <AlertOctagon size={24} className="mb-2 text-slate-600" />
            <p className="text-slate-400">No parcels match this filter.</p>
            <button
              onClick={() => { setPriorityFilter('ALL'); setSearch(''); }}
              className="mt-3 px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-cyan-400 hover:bg-slate-800 text-xs font-sans transition-colors"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {/* Footer System Status */}
      <div className="p-3 border-t border-slate-800/80 bg-[#050A14] flex items-center justify-between text-xs font-mono shrink-0">
        <span className="text-slate-400 text-[11px]">
          {parcels.length} parcels surveyed
        </span>
        <button
          onClick={onRestart}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 hover:border-cyan-500/50 hover:text-cyan-300 text-slate-300 text-[11px] transition-colors"
        >
          <RefreshCw size={12} />
          <span>New run</span>
        </button>
      </div>
    </aside>
  )
}
