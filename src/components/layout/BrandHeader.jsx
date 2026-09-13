import React from 'react'
import { Info, Settings2, Globe } from 'lucide-react'

export default function BrandHeader({ 
  step = 'Workspace', 
  demoMode = true, 
  onToggleDemo, 
  onArchitecture, 
  architectureOpen = false,
  onNavigateLanding,
}) {
  return (
    <header className="sticky top-0 z-[1000] h-[58px] px-4 md:px-6 bg-[#030712]/80 backdrop-blur-xl border-b border-cyan-500/15 flex items-center justify-between shadow-[0_4px_30px_rgba(0,0,0,0.5)]">
      {/* Brand & Mission Title */}
      <div className="flex items-center gap-3 md:gap-4">
        <button 
          onClick={onNavigateLanding}
          className="flex items-center gap-2.5 group focus:outline-none"
          title="LANDSYNC Home"
        >
          <div className="relative w-8 h-8 rounded border border-cyan-400/50 bg-cyan-950/40 flex items-center justify-center text-cyan-300 font-mono font-bold text-xs shadow-[0_0_12px_rgba(0,240,255,0.25)] group-hover:bg-cyan-500 group-hover:text-black group-hover:border-white transition-all duration-300">
            <span>LS</span>
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping opacity-75" />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-[0.14em] text-slate-100 group-hover:text-cyan-300 transition-colors">
                LANDSYNC
              </span>
              <span className="hidden sm:inline-flex items-center gap-1 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Globe size={10} className="text-cyan-400" />
                GIS v2.4
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono hidden md:block tracking-wide">
              Cadastral Intelligence & Consensus Engine
            </p>
          </div>
        </button>

        <div className="hidden lg:flex items-center gap-1.5 pl-3 border-l border-slate-800 text-xs text-slate-400 font-mono">
          <span className="text-slate-500">CRS:</span>
          <span className="text-slate-300 bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-800 text-[10px]">
            EPSG:4326
          </span>
          <span className="text-slate-500 ml-1">SOURCE:</span>
          <span className="text-cyan-400 text-[10px]">Sentinel-2 / RoR</span>
        </div>
      </div>

      {/* Navigation and System Telemetry */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Step Badge */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900/90 border border-slate-800 text-xs font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-slate-400 text-[11px]">MODE:</span>
          <span className="text-slate-200 font-medium text-[11px] uppercase tracking-wider">{step}</span>
        </div>

        {/* Demo / Live Status Pill */}
        <button
          onClick={onToggleDemo}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono transition-all duration-200 border ${
            demoMode
              ? 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20 hover:border-amber-400/50 shadow-[0_0_12px_rgba(255,184,0,0.15)]'
              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20 hover:border-emerald-400/50 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
          }`}
          title={demoMode ? 'Click to switch to Live FastAPI Backend' : 'Click to switch to Local Demo Fixture'}
          aria-label={demoMode ? 'Use live backend' : 'Use demo data'}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${demoMode ? 'bg-amber-400 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
          <span>{demoMode ? 'Demo Fixture' : 'Live FastAPI'}</span>
        </button>

        {/* Architecture Button (Preserves exact button name 'How it works' for tests) */}
        {onArchitecture && (
          <button
            className={`architecture-button inline-flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all duration-200 border ${
              architectureOpen 
                ? 'bg-cyan-500 text-black border-cyan-400 shadow-[0_0_15px_rgba(0,240,255,0.4)]'
                : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:text-cyan-300 hover:border-cyan-500/40 hover:bg-slate-800'
            }`}
            onClick={onArchitecture}
          >
            <Info size={13} className={architectureOpen ? 'text-black' : 'text-cyan-400'} aria-hidden="true" />
            <span>{architectureOpen ? 'Back to run' : 'How it works'}</span>
          </button>
        )}

        {/* Project Meta Code */}
        <span className="project-code text-[10px] text-slate-500 font-mono hidden xl:inline-block">
          SIH26013 / Day 4 · {step}
        </span>

        {/* Quick Settings Gear (Maintains toggle functionality) */}
        <button
          className="settings-button p-1.5 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 border border-transparent hover:border-slate-700 transition-colors"
          onClick={onToggleDemo}
          aria-label={demoMode ? 'Use live backend' : 'Use demo data'}
          title={demoMode ? 'Switch to live FastAPI backend' : 'Switch to demo dataset'}
        >
          <Settings2 size={16} />
        </button>
      </div>
    </header>
  )
}
