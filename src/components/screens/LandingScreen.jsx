import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { MapPin, Database, ShieldCheck, ArrowRight, Sparkles, Compass } from 'lucide-react'
import BrandHeader from '../layout/BrandHeader'

export default function LandingScreen({ 
  onInitiate, 
  onExploreDemo,
  demoMode = true,
  onToggleDemo,
  onArchitecture
}) {
  const reduceMotion = useReducedMotion()

  const heroRise = (delay) =>
    reduceMotion
      ? {}
      : {
          initial: { opacity: 0, y: 18 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.55, delay, ease: 'easeOut' },
        }

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
        
        {/* Subtle Ambient Radial Glows — slow positional drift */}
        <motion.div
          className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-cyan-500/10 blur-[130px] rounded-full pointer-events-none"
          animate={reduceMotion ? undefined : { x: [0, 40, 0], y: [0, -18, 0] }}
          transition={reduceMotion ? undefined : { duration: 20, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute bottom-1/4 right-1/4 w-[450px] h-[450px] bg-blue-600/10 blur-[140px] rounded-full pointer-events-none"
          animate={reduceMotion ? undefined : { x: [0, -30, 0], y: [0, 22, 0] }}
          transition={reduceMotion ? undefined : { duration: 26, repeat: Infinity, ease: 'easeInOut' }}
        />

        {/* Tactical Cadastral Contour Lines SVG — animated */}
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
          {/* Simulated Cadastral Boundaries — slow line-draw + drift */}
          <motion.g
            animate={reduceMotion ? undefined : {
              strokeDashoffset: [0, -70],
              x: [0, 6, 0],
              y: [0, -4, 0],
            }}
            transition={reduceMotion ? undefined : {
              strokeDashoffset: { duration: 24, repeat: Infinity, ease: 'linear' },
              x: { duration: 18, repeat: Infinity, ease: 'easeInOut' },
              y: { duration: 22, repeat: Infinity, ease: 'easeInOut' },
            }}
            style={{ strokeDashoffset: 0 }}
          >
            <polygon points="120,180 340,160 390,320 180,360" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="4 4" />
            <polygon points="340,160 580,140 620,290 390,320" fill="rgba(0,240,255,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1" />
            <polygon points="580,140 850,110 890,260 620,290" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="3 6" />
            <polygon points="210,410 460,390 510,560 270,590" fill="rgba(59,130,246,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1.2" />
            <polygon points="460,390 720,360 780,520 510,560" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" />
            <polygon points="720,360 980,320 1020,480 780,520" fill="rgba(0,240,255,0.03)" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="6 3" />
          </motion.g>
        </svg>

        {/* Recon Scan Sweep — vertical light band crossing the viewport */}
        {!reduceMotion && (
          <motion.div
            className="absolute left-0 right-0 h-24 pointer-events-none"
            style={{
              background: 'linear-gradient(to bottom, transparent, rgba(0,240,255,0.06), transparent)',
            }}
            initial={{ top: '-10%' }}
            animate={{ top: '110%' }}
            transition={{ duration: 9, repeat: Infinity, ease: 'linear', repeatDelay: 4 }}
          />
        )}

        {/* Floating Telemetry Coordinates Markers */}
        <div className="absolute top-24 left-8 text-[11px] font-mono text-cyan-400/40 hidden lg:block tracking-widest">
          + LAT: 17.385044° N<br/>
          + LNG: 78.486671° E<br/>
          + DATUM: WGS84
        </div>
        <div className="absolute bottom-16 right-8 text-[11px] font-mono text-cyan-400/40 hidden lg:block text-right tracking-widest">
          SYS: RECONCILIATION ENGINE 2.4<br/>
          RESOL: 0.1M / SUB-PARCEL<br/>
          HARMONIZATION: ACTIVE
        </div>
      </div>

      {/* Main Hero Stage */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-16 sm:py-20 text-center max-w-5xl mx-auto">
        {/* Mission Signal Pill */}
        <motion.div
          {...heroRise(0)}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-xs font-mono uppercase tracking-widest mb-8 shadow-[0_0_20px_rgba(0,240,255,0.15)]"
        >
          <Sparkles size={13} className="text-cyan-400" />
          <span>Land Records Reconciliation Platform</span>
        </motion.div>

        {/* Primary Typography Hierarchy */}
        <motion.img
          {...heroRise(0.08)}
          src="/brand/landsync-mark@256.png"
          alt="LANDSYNC GIS"
          width={96}
          height={96}
          className="h-20 w-20 sm:h-24 sm:w-24 mb-6"
          draggable={false}
        />
        <motion.h1
          {...heroRise(0.16)}
          className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white mb-4 leading-[1.08]"
        >
          <span className="bg-clip-text text-transparent bg-gradient-to-b from-white via-slate-100 to-slate-400">
            LANDSYNC
          </span>
        </motion.h1>

        <motion.p
          {...heroRise(0.24)}
          className="text-xl sm:text-2xl md:text-3xl font-mono text-cyan-400 font-medium tracking-tight mb-6"
        >
          Land Intelligence. Reconciled.
        </motion.p>

        <motion.p
          {...heroRise(0.32)}
          className="max-w-2xl text-base sm:text-lg text-slate-300 font-normal leading-relaxed mb-10"
        >
          Reconcile land records, surveys and imagery into one trusted view.
          Compare what is recorded with what is observed — and flag what needs field verification.
        </motion.p>

        {/* Action CTAs */}
        <motion.div
          {...heroRise(0.4)}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full max-w-md mb-16"
        >
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
        </motion.div>

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
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3 group-hover:bg-cyan-500/20 group-hover:scale-105 transition-all">
              <ShieldCheck size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Verified Consensus</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Weighted Reconciliation Scores express agreement between survey documents and observed imagery —
              they are methodology scores, not calibrated accuracy.
            </p>
          </div>
        </div>
      </main>

      {/* Footer System Status Bar */}
      <footer className="relative z-10 border-t border-slate-800/60 py-3.5 px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-slate-500 bg-[#030712]/70 backdrop-blur">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-cyan-400">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            CORE ONLINE
          </span>
          <span>Supports GeoJSON · SHP · CSV · TIFF · PDF</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Decision-support prototype — not an official record</span>
        </div>
      </footer>
    </div>
  )
}
