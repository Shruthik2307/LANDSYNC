import React, { useState } from 'react'
import { Search, RefreshCw, X, AlertOctagon, Layers, AlertTriangle } from 'lucide-react'
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
  matchesFilter,
  onProcess,
  processStatus = 'idle'
}) {
  const [activeTab, setActiveTab] = useState('conflicts')
  const sourceList = activeTab === 'conflicts' ? conflicts : parcels
  const filteredList = sourceList.filter(matchesFilter)

  return (
    <aside 
      className="w-full h-full flex flex-col bg-[#070D1A]/90 backdrop-blur-xl border-l border-cyan-500/15 overflow-hidden"
      aria-label="Parcel and conflict queue"
    >
      {/* Panel Header */}
      <div className="p-3.5 sm:p-4 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center justify-between mb-2.5">
          <div>
            <span className="text-[11px] font-mono text-cyan-400 uppercase tracking-widest block font-semibold">
              RECONCILIATION MONITOR
            </span>
            <div className="flex items-center gap-2 mt-0.5">
              <h2 className="text-base font-bold text-slate-100 tracking-tight flex items-center gap-2">
                <span>{activeTab === 'conflicts' ? 'Conflict Queue' : 'Parcel Dashboard'}</span>
                <span className="px-2 py-0.5 text-xs font-mono font-bold rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  {filteredList.length}
                </span>
              </h2>
            </div>
          </div>

          {datasetId && (
            <div className="text-[11px] font-mono px-2 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400 max-w-[120px] truncate" title={datasetId}>
              {datasetId}
            </div>
          )}
        </div>

        {/* Tab Switcher: All 25 Parcels vs Conflicts */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-slate-950/80 border border-slate-800 mb-2.5 font-mono text-xs">
          <button
            onClick={() => setActiveTab('all')}
            className={`flex-1 py-1 px-2 rounded text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'all'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,240,255,0.15)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers size={12} />
            <span>All Parcels</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {parcels.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('conflicts')}
            className={`flex-1 py-1 px-2 rounded text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'conflicts'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_8px_rgba(255,184,0,0.15)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <AlertTriangle size={12} />
            <span>Conflicts</span>
            <span className="text-[11px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
              {conflicts.length}
            </span>
          </button>
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
        {filteredList.length > 0 ? (
          filteredList.map((parcel) => (
            <QueueRow
              key={parcel.parcel_id}
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

      {/* Footer System Status & Reconcile / Restart Actions */}
      <div className="p-3 border-t border-slate-800/80 bg-[#050A14] flex items-center justify-between text-xs font-mono shrink-0">
        <span className="text-slate-400 text-[11px]">
          {parcels.length} parcels surveyed
        </span>
        <div className="flex items-center gap-2">
          {onProcess && (
            <button
              onClick={onProcess}
              disabled={processStatus === 'processing'}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-cyan-950/60 border border-cyan-500/30 hover:border-cyan-400 hover:text-white text-cyan-300 text-[11px] transition-colors"
              title="Run LANDSYNC engine reconciliation"
            >
              <RefreshCw size={12} className={processStatus === 'processing' ? 'animate-spin' : ''} />
              <span>{processStatus === 'processing' ? 'Reconciling…' : 'Reconcile'}</span>
            </button>
          )}
          <button
            onClick={onRestart}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 hover:border-cyan-500/50 hover:text-cyan-300 text-slate-300 text-[11px] transition-colors"
          >
            <RefreshCw size={12} />
            <span>New run</span>
          </button>
        </div>
      </div>
    </aside>
  )
}
