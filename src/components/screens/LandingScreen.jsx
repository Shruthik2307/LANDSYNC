import React from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { MapPin, Database, ShieldCheck, ArrowRight, Layers, Compass } from 'lucide-react'
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
          initial: { opacity: 0, y: 16 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.5, delay, ease: 'easeOut' },
        }

  return (
    <div className="relative min-h-screen bg-[#030712] text-slate-100 flex flex-col overflow-x-hidden selection:bg-cyan-500/30">
      {/* Top Navigation */}
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
        <div className="absolute inset-0 bg-tactical-grid opacity-25 [mask-image:radial-gradient(ellipse_80%_60%_at_50%_40%,#000_70%,transparent_100%)]" />
        
        {/* Subtle Ambient Spatial Depth — stable background lighting */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[450px] bg-cyan-950/20 blur-[140px] rounded-full pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-[450px] h-[450px] bg-blue-950/20 blur-[150px] rounded-full pointer-events-none" />

        {/* Cadastral Boundary Vectors */}
        <svg
          className="absolute inset-0 w-full h-full opacity-15"
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
          <polygon points="120,180 340,160 390,320 180,360" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="4 4" />
          <polygon points="340,160 580,140 620,290 390,320" fill="rgba(0,240,255,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1" />
          <polygon points="580,140 850,110 890,260 620,290" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="3 6" />
          <polygon points="210,410 460,390 510,560 270,590" fill="rgba(59,130,246,0.02)" stroke="url(#cadastralGrad)" strokeWidth="1.2" />
          <polygon points="460,390 720,360 780,520 510,560" fill="none" stroke="url(#cadastralGrad)" strokeWidth="1" />
          <polygon points="720,360 980,320 1020,480 780,520" fill="rgba(0,240,255,0.03)" stroke="url(#cadastralGrad)" strokeWidth="1" strokeDasharray="6 3" />
        </svg>
      </div>

      {/* Main Hero Stage */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-16 sm:py-20 text-center max-w-5xl mx-auto">
        {/* Mission Signal Pill — Institutional GovTech */}
        <motion.div
          {...heroRise(0)}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/90 border border-slate-700/70 text-slate-300 text-xs font-mono uppercase tracking-wider mb-8 shadow-sm"
        >
          <Layers size={13} className="text-cyan-400" />
          <span>SIH26013 • Cadastral & Municipal Boundary Harmonization Engine</span>
        </motion.div>

        {/* Primary Typography Hierarchy */}
        <motion.img
          {...heroRise(0.08)}
          src="/brand/landsync-mark@512.png"
          alt="LANDSYNC GIS"
          width={96}
          height={96}
          className="h-20 w-20 sm:h-24 sm:w-24 mb-6 object-contain drop-shadow-[0_0_20px_rgba(0,240,255,0.2)]"
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
          className="text-xl sm:text-2xl md:text-3xl font-mono text-cyan-400 font-semibold tracking-tight mb-4"
        >
          Deterministic Cadastral Reconciliation & Auditing
        </motion.p>

        <motion.p
          {...heroRise(0.32)}
          className="max-w-2xl text-base sm:text-lg text-slate-300 font-normal leading-relaxed mb-6"
        >
          Reconcile legacy revenue land records, GIS shapefiles, and satellite imagery into one unified geometry.
          Quantify boundary shifts, detect overlap conflicts via 14-feature machine learning, and verify title integrity.
        </motion.p>

        {/* Enterprise GIS Telemetry Dock */}
        <motion.div
          {...heroRise(0.36)}
          className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 text-[11px] font-mono text-slate-400 mb-10 py-1.5 px-4 rounded-lg bg-slate-900/60 border border-slate-800"
        >
          <span className="flex items-center gap-1.5 text-slate-300">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            CRS: EPSG:4326 / EPSG:3857
          </span>
          <span className="text-slate-600 hidden sm:inline">•</span>
          <span>MODEL: RF-TGRAC-V1.0 (14 FEAT)</span>
          <span className="text-slate-600 hidden sm:inline">•</span>
          <span>PARSERS: CAD · SHP · GPKG · KML · TIFF · PDF</span>
          <span className="text-slate-600 hidden sm:inline">•</span>
          <span className="text-cyan-400">AUDIT PROVENANCE: ACTIVE</span>
        </motion.div>

        {/* Action CTAs */}
        <motion.div
          {...heroRise(0.4)}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full max-w-md mb-16"
        >
          <button
            onClick={onInitiate}
            className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm tracking-wide shadow-md hover:shadow-cyan-500/20 active:translate-y-0.5 transition-all duration-150"
          >
            <span>Upload Land Records</span>
            <ArrowRight size={16} />
          </button>

          <button
            onClick={onExploreDemo}
            className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-lg bg-slate-900/90 text-slate-200 font-semibold text-sm tracking-wide border border-slate-700/80 hover:border-slate-500 hover:text-white hover:bg-slate-800 transition-all duration-150 shadow-sm"
          >
            <Compass size={16} className="text-cyan-400" />
            <span>Explore Interactive Demo</span>
          </button>
        </motion.div>

        {/* Three Pillar Value Prop Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full text-left">
          {/* Pillar 1 */}
          <div className="p-5 rounded-xl bg-slate-900/50 backdrop-blur-md border border-slate-800/80 hover:border-slate-700 transition-colors">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3">
              <Database size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Multi-Format Ingestion</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Ingest ESRI Shapefiles, AutoCAD DXF, GeoTIFF, KML, GeoPackage, and text/scanned deed records with ZipSlip protection.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="p-5 rounded-xl bg-slate-900/50 backdrop-blur-md border border-slate-800/80 hover:border-slate-700 transition-colors">
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-3">
              <MapPin size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>Geometric Harmonization</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Dual CRS re-projection with Shapely planar topology, boundary buffer differences, and Hausdorff drift quantification.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="p-5 rounded-xl bg-slate-900/50 backdrop-blur-md border border-slate-800/80 hover:border-slate-700 transition-colors">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3">
              <ShieldCheck size={18} />
            </div>
            <h2 className="text-sm font-bold text-slate-100 mb-1 flex items-center gap-1.5">
              <span>14-Feature ML Consensus</span>
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Deterministic Random Forest classification providing defensible match and discrepancy advisories with human review overrides.
            </p>
          </div>
        </div>
      </main>

      {/* Footer System Status Bar */}
      <footer className="relative z-10 border-t border-slate-800/60 py-3.5 px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] font-mono text-slate-500 bg-[#030712]/80 backdrop-blur">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            CORE ENGINE: ONLINE (EPSG:4326 / EPSG:3857)
          </span>
          <span>ML: RF-TGRAC-V1.0 (14 FEAT)</span>
        </div>
        <div className="flex items-center gap-4">
          <span>Cadastral Decision-Support System · SIH26013</span>
        </div>
      </footer>
    </div>
  )
}
