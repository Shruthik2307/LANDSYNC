import React, { useState, useEffect, useRef } from 'react'
import { Info, Settings2, ArrowLeft, Activity } from 'lucide-react'
import { getHealth } from '../../api'
import { SourceBadge } from '../result/Provenance'

export default function BrandHeader({
  step = 'Workspace',
  demoMode = false,
  onToggleDemo,
  onArchitecture,
  architectureOpen = false,
  onNavigateLanding,
}) {
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(false)
  const [sysPanelOpen, setSysPanelOpen] = useState(false)
  const sysRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    async function checkHealth() {
      try {
        const h = await getHealth()
        if (!cancelled) {
          setHealth(h)
          setHealthError(false)
        }
      } catch {
        if (!cancelled) {
          setHealth(null)
          setHealthError(true)
        }
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  // Close the system panel on outside click
  useEffect(() => {
    if (!sysPanelOpen) return undefined
    function handleClick(e) {
      if (sysRef.current && !sysRef.current.contains(e.target)) setSysPanelOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [sysPanelOpen])

  const statusLabel = healthError
    ? 'Offline'
    : health?.status === 'ok'
      ? 'Operational'
      : 'Starting'

  return (
    <header className="sticky top-0 z-[800] w-full h-14 shrink-0 bg-[#070D1A]/95 backdrop-blur-xl border-b border-slate-800 flex items-center justify-between px-3 sm:px-4 gap-2 select-none">
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {/* Back navigation */}
        {onNavigateLanding && step !== 'Overview' && (
          <button
            onClick={onNavigateLanding}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-slate-300 hover:text-cyan-300 hover:bg-slate-800/70 border border-transparent hover:border-slate-700 transition-colors text-[13px] font-medium shrink-0"
            title="Back to Overview"
            aria-label="Back to overview"
          >
            <ArrowLeft size={15} />
            <span className="hidden sm:inline">Back</span>
          </button>
        )}

        {/* Brand block: logo + wordmark. Clicking returns to the overview. */}
        <button
          onClick={onNavigateLanding}
          className="group flex items-center gap-2.5 min-w-0 focus:outline-none"
          title="LANDSYNC — back to overview"
        >
          {/* LANDSYNC GIS brand mark — high-definition supersampled mark */}
          <img
            src="/brand/landsync-mark@256.png"
            alt="LANDSYNC GIS"
            width={32}
            height={32}
            className="h-8 w-8 shrink-0 object-contain drop-shadow-[0_2px_10px_rgba(0,240,255,0.25)]"
            draggable={false}
          />
          <div className="text-left min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[15px] font-bold tracking-[0.14em] text-white group-hover:text-cyan-300 transition-colors">
                LAND<span className="text-cyan-400">SYNC</span>
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Info size={10} className="text-cyan-400" aria-hidden="true" />
                GIS
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden md:block tracking-wide whitespace-nowrap font-mono uppercase text-[10px]">
              Precision Geospatial Intelligence
            </p>
          </div>
        </button>

        {/* Source provenance badge — what is actually loaded (sample/upload) */}
        <span className="inline-flex">
          <SourceBadge health={health} demoMode={demoMode} />
        </span>
      </div>

      {/* Right cluster: current screen, data mode, help, system info */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Current screen — plain language */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900/90 border border-slate-800">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          <span className="text-slate-300 text-[12px] font-medium uppercase tracking-wide">{step}</span>
        </div>

        {/* Data source toggle — plain language, amber = demo data in use */}
        <button
          onClick={onToggleDemo}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-medium transition-all duration-200 border ${
            demoMode
              ? 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20'
              : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/20'
          }`}
          title={demoMode ? 'Switch to live backend data' : 'Switch to sample data'}
          aria-label={demoMode ? 'Use live backend' : 'Use demo data'}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${demoMode ? 'bg-amber-400' : 'bg-cyan-400'}`} />
          <span>{demoMode ? 'Sample Data' : 'Live Data'}</span>
        </button>

        {/* Help (preserves exact button name 'How it works' for tests) */}
        {onArchitecture && (
          <button
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded text-[13px] font-medium transition-all duration-200 border ${
              architectureOpen
                ? 'bg-cyan-500 text-black border-cyan-400'
                : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:text-cyan-300 hover:border-cyan-500/40 hover:bg-slate-800'
            }`}
            onClick={onArchitecture}
          >
            <Info size={13} className={architectureOpen ? 'text-black' : 'text-cyan-400'} aria-hidden="true" />
            <span>{architectureOpen ? 'Back to run' : 'How it works'}</span>
          </button>
        )}

        {/* System status + diagnostics popover — technical detail lives here,
            not in the main bar. One glanceable dot + word. */}
        <div className="relative" ref={sysRef}>
          <button
            onClick={() => setSysPanelOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[12px] font-mono border transition-colors ${
              healthError
                ? 'bg-red-500/10 text-red-300 border-red-500/30'
                : 'bg-slate-900/90 text-slate-300 border-slate-800 hover:border-slate-600'
            }`}
            aria-expanded={sysPanelOpen}
            aria-haspopup="dialog"
            title="System status details"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                healthError ? 'bg-red-400' : 'bg-cyan-400'
              } ${healthError ? '' : 'animate-pulse'}`}
            />
            <span className="hidden sm:inline">{statusLabel}</span>
            <Activity size={12} className="text-slate-500" aria-hidden="true" />
          </button>

          {sysPanelOpen && (
            <div
              role="dialog"
              aria-label="System information"
              className="absolute right-0 top-9 w-72 p-3 rounded-xl bg-[#070D1A]/98 backdrop-blur-xl border border-slate-700 shadow-2xl z-[900] space-y-2"
            >
              <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500">
                System Information
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[12px] font-mono">
                <dt className="text-slate-500">Status</dt>
                <dd className={healthError ? 'text-red-300' : 'text-cyan-300'}>
                  {healthError ? 'Backend unreachable' : statusLabel}
                </dd>
                {!healthError && (
                  <>
                    <dt className="text-slate-500">Engine</dt>
                    <dd className="text-slate-200">
                      {health?.engine ? health.engine.charAt(0).toUpperCase() + health.engine.slice(1) : 'Loaded'}
                    </dd>
                    <dt className="text-slate-500">Parcels loaded</dt>
                    <dd className="text-slate-200">{health?.parcel_count ?? '—'}</dd>
                    <dt className="text-slate-500">CRS</dt>
                    <dd className="text-slate-200">{health?.cadastral_crs || 'EPSG:4326'}</dd>
                    <dt className="text-slate-500">Data source</dt>
                    <dd className="text-slate-200">
                      {health?.cadastral_source === 'USER_UPLOADED_REAL'
                        ? 'Uploaded file'
                        : 'Built-in sample'}
                    </dd>
                    {health?.cadastral_filename && (
                      <>
                        <dt className="text-slate-500">File</dt>
                        <dd className="text-slate-300 truncate" title={health.cadastral_filename}>
                          {health.cadastral_filename}
                        </dd>
                      </>
                    )}
                  </>
                )}
              </dl>
              <div className="pt-1 text-[11px] text-slate-500 border-t border-slate-800">
                Decision-support prototype — not an official land record.
              </div>
            </div>
          )}
        </div>

        {/* Quick settings gear (preserves toggle functionality) */}
        <button
          className="settings-button p-1.5 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 border border-transparent hover:border-slate-700 transition-colors"
          onClick={onToggleDemo}
          aria-label={demoMode ? 'Use live backend' : 'Use demo data'}
          title={demoMode ? 'Switch to live data' : 'Switch to sample data'}
        >
          <Settings2 size={16} />
        </button>
      </div>
    </header>
  )
}
