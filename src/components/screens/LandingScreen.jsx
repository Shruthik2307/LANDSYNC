import React from 'react'
import { MapPin, Database, ShieldCheck, ArrowRight, Sparkles, Compass } from 'lucide-react'
import BrandHeader from '../layout/BrandHeader'

export default function LandingScreen({ 
  onInitiate, 
  onExploreDemo,
  demoMode = true,
  onToggleDemo,
  onArchitecture
}) {
  return (
    <div className="relative min-h-screen bg-[#030712] text-slate-100 flex flex-col overflow-x-hidden selection:bg-cyan-500/30">
      {/* Sleek Top Navigation */}
      <BrandHeader 
        step="Overview" 
        demoMode={demoMode} 
        onToggleDemo={onToggleDemo} 
        onArchitecture={onArchitecture}
        onNavigateLanding={() => {}}
      />

      {/* Geospatial Coordinate Background & Tactical Elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
        {/* Coordinate Grid */}
        <div className="absolute inset-0 bg-tactical-grid opacity-30 [mask-image:radial-gradient(ellipse_80%_60%_at_50%_40%,#000_70%,transparent_100%)]" />
        
        {/* Subtle Ambient Radial Glows */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-cyan-500/10 blur-[130px] rounded-full pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-[450px] h-[450px] bg-blue-600/10 blur-[140px] rounded-full pointer-events-none" />

        {/* Tactical Cadastral Contour Lines SVG */}
        <svg 
          className="absolute inset-0 w-full h-full opacity-20" 
          xmlns="http://www.w3.org/2000/svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="cadastralGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00F0FF" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#3B82F6" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#00F0FF" stopOpacity="0.3" />
            </linearGradient>
            <pattern id="dotPattern" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1" fill="#00F0FF" fillOpacity="0.1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dotPattern)" />
          {/* Simulated Cadastral Boundaries */}
          <polygon points="120,180 340,160 390,320 180,360" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="4 4" />
          <polygon points="340,160 580,140 620,290 390,320" fill="rgba(0,240,255,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1" />
          <polygon points="580,140 850,110 890,260 620,290" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="3 6" />
          <polygon points="210,410 460,390 510,560 270,590" fill="rgba(59,130,246,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1.2" />
          <polygon points="460,390 720,360 780,520 510,560" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" />
          <polygon points="720,360 980,320 1020,480 780,520" fill="rgba(0,240,255,0.03)" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="6 3" />
        </svg>

        {/* Floating Telemetry Coordinates Markers */}
        <div className="absolute top-24 left-8 text-[10px] font-mono text-cyan-400/40 hidden lg:block tracking-widest">
          + LAT: 17.385044° N<br/>
          + LNG: 78.486671° E<br/>
          + DATUM: WGS84
        </div>
        <div className="absolute bottom-16 right-8 text-[10px] font-mono text-cyan-400/40 hidden lg:block text-right tracking-widest">
          SYS: RECONCILIATION ENGINE 2.4<br/>
          RESOL: 0.1M / SUB-PARCEL<br/>
          HARMONIZATION: ACTIVE
        </div>
      </div>

      {/* Main Hero Stage */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-16 sm:py-20 text-center max-w-5xl mx-auto">
        {/* Mission Signal Pill */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-xs font-mono uppercase tracking-widest mb-8 shadow-[0_0_20px_rgba(0,240,255,0.15)] animate-pulse">
          <Sparkles size={13} className="text-cyan-400" />
          <span>Government-Grade Geospatial Intelligence</span>
        </div>

        {/* Primary Typography Hierarchy */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white mb-4 leading-[1.08]">
          <span className="bg-clip-text text-transparent bg-gradient-to-b from-white via-slate-100 to-slate-400">
            LANDSYNC
          </span>
        </h1>

        <p className="text-xl sm:text-2xl md:text-3xl font-mono text-cyan-400 font-medium tracking-tight mb-6">
          Land Intelligence. Reconciled.
        </p>

        <p className="max-w-2xl text-base sm:text-lg text-slate-300 font-normal leading-relaxed mb-10">
          Reconcile cadastral, survey and satellite sources into one trusted land view.
          Synthesize heterogeneous parcel records into high-confidence consensus for precision governance.
        </p>

        {/* Action CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full max-w-md mb-16">
          <button
            onClick={onInitiate}
            className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-lg bg-cyan-400 text-[#030712] font-bold text-sm tracking-wide shadow-[0_0_30px_rgba(0,240,255,0.4)] hover:bg-white hover:shadow-[0_0_40px_rgba(0,240,255,0.6)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200"
          >
            <span>Upload Land Records</span>
            <ArrowRight size={16} />
          </button>

          <button
            onClick={onExploreDemo}
            className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-lg bg-slate-900/80 text-slate-200 font-semibold text-sm tracking-wide border border-slate-700 hover:border-cyan-400/60 hover:text-cyan-300 hover:bg-slate-800/90 transition-all duration-200 shadow-[0_4px_20px_rgba(0,0,0,0.4)]"
          >
            <Compass size={16} className="text-cyan-400" />
            <span>Explore Demo</span>
          </button>
        </div>

        {/* Three Pillar Value Prop Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full text-left">
          {/* Pillar 1 */}
          <div className="p-5 rounded-xl bg-slate-900/40 backdrop-blur-md border border-slate-800/80 hover:border-cyan-500/30 transition-all duration-300 group">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3 group-hover:bg-cyan-500/20 group-hover:scale-105 transition-all">
              <Database size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Multimodal Ingestion</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Harmonize legacy cadastral revenue records, GeoJSON vectors, drone orthomosaics, and Sentinel-2 imagery.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="p-5 rounded-xl bg-slate-900/40 backdrop-blur-md border border-slate-800/80 hover:border-cyan-500/30 transition-all duration-300 group">
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3 group-hover:bg-blue-500/20 group-hover:scale-105 transition-all">
              <MapPin size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Spatial Harmonization</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Dynamic CRS re-projection and boundary shift detection flag discrepancies before land registrations.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="p-5 rounded-xl bg-slate-900/40 backdrop-blur-md border border-slate-800/80 hover:border-cyan-500/30 transition-all duration-300 group">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-3 group-hover:bg-emerald-500/20 group-hover:scale-105 transition-all">
              <ShieldCheck size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Verified Consensus</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Weighted confidence dial scores agreement between survey documents and real-world ground conditions.
            </p>
          </div>
        </div>
      </main>

      {/* Footer System Status Bar */}
      <footer className="relative z-10 border-t border-slate-800/60 py-3.5 px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-slate-500 bg-[#030712]/70 backdrop-blur">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            CORE ONLINE
          </span>
          <span>INGESTION: GEOJSON · SHP · CSV · TIFF · PDF</span>
        </div>
        <div className="flex items-center gap-4">
          <span>COORDINATE CONSENSUS: ACTIVE</span>
          <span className="text-slate-400">SIH26013 · LANDSYNC</span>
        </div>
      </footer>
    </div>
  )
}
