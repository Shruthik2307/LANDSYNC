import React, { useEffect, useMemo, useRef, useState } from 'react'
import PropTypes from 'prop-types'
import { getImageryInfo } from '../../api'
import { Satellite, AlertTriangle, RefreshCw, ShieldQuestion } from 'lucide-react'

/**
 * SourceBadge — honest data-provenance label.
 *
 * The badge always tells the truth about what is loaded:
 *   - both sources are user uploads  → "REAL → REAL RECONCILIATION"
 *   - only cadastral is an upload    → "REAL + SAMPLE MIXED" (with warning)
 *   - both sources synthetic         → "SYNTHETIC DEMO DATA"
 * Never claims "government verified" or "live" — those words are reserved
 * for evidence the system does not have.
 */
export function SourceBadge({ health }) {
  if (!health) return null
  const cad = health.cadastral_source
  const mun = health.municipal_source

  if (cad === 'upload' && mun === 'upload') {
    return (
      <span
        data-testid="source-badge"
        className="inline-flex items-center gap-1 text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/40"
        title={`Real source data: ${health.cadastral_filename || 'cadastral'} + ${health.municipal_filename || 'municipal'}`}
      >
        REAL → REAL RECONCILIATION
      </span>
    )
  }
  if (cad === 'upload' || mun === 'upload') {
    return (
      <span
        data-testid="source-badge"
        className="inline-flex items-center gap-1 text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/40"
        title="One source is a real upload; the other is the built-in synthetic sample. Scores comparing them are not a like-for-like reconciliation."
      >
        <AlertTriangle size={10} />
        REAL + SAMPLE MIXED
      </span>
    )
  }
  return (
    <span
      data-testid="source-badge"
      className="inline-flex items-center gap-1 text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-slate-500/15 text-slate-300 border border-slate-500/40"
      title="Built-in synthetic sample parcels — for demonstration, not real land records."
    >
      SYNTHETIC DEMO DATA
    </span>
  )
}

SourceBadge.propTypes = {
  health: PropTypes.shape({
    cadastral_source: PropTypes.string,
    municipal_source: PropTypes.string,
    cadastral_filename: PropTypes.string,
    municipal_filename: PropTypes.string,
  }),
}

/**
 * Single-source notice: a real dataset was loaded but reconciliation ran
 * against the synthetic sample. Shown once, honestly, instead of silently
 * comparing real against fake data.
 */
export function MixedSourceNotice({ health }) {
  const mixed =
    health &&
    (health.cadastral_source === 'upload') !== (health.municipal_source === 'upload')
  if (!mixed) return null
  const uploaded = health.cadastral_source === 'upload' ? 'cadastral' : 'municipal'
  return (
    <div
      data-testid="mixed-source-notice"
      role="status"
      className="mx-4 mt-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] font-mono text-amber-300 flex items-start gap-2"
    >
      <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-400" />
      <span>
        Real {uploaded} data loaded ({uploaded === 'cadastral' ? health.cadastral_filename : health.municipal_filename}).
        {' '}A second compatible real source is required for real-to-real reconciliation —
        the other side is the built-in synthetic sample, so Reconciliation Scores
        are indicative only — they are not a like-for-like comparison.
      </span>
    </div>
  )
}

MixedSourceNotice.propTypes = {
  health: PropTypes.shape({
    cadastral_source: PropTypes.string,
    municipal_source: PropTypes.string,
    cadastral_filename: PropTypes.string,
    municipal_filename: PropTypes.string,
  }),
}

/**
 * ImageryProvenancePanel — IMAGERY PROVENANCE facts.
 *
 * Shows the provider's REAL acquisition metadata from /api/imagery/info for
 * the queried point. Never says "live" (Esri World Imagery is a dated
 * mosaic). When the acquisition date is unavailable it says exactly that —
 * no invented dates, and "latest available" is never claimed because the
 * metadata service does not establish that the capture shown is the most
 * recent one published for the location.
 */
export function ImageryProvenancePanel({ lng, lat, source = 'esri_wayback' }) {
  const [state, setState] = useState({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    if (lng == null || lat == null) return undefined
    // Async metadata fetch — state updates happen in the promise callbacks,
    // not synchronously in the effect body.
    let cancelled = false
    getImageryInfo(lng, lat, source)
      .then((res) => {
        if (mounted.current && !cancelled) setState({ status: 'ready', imagery: res.imagery })
      })
      .catch((err) => {
        if (mounted.current && !cancelled) setState({ status: 'error', message: err.message })
      })
    return () => {
      cancelled = true
      mounted.current = false
    }
  }, [lng, lat, source, attempt])

  const info = useMemo(() => (state.status === 'ready' ? state.imagery : null), [state])

  if (state.status === 'loading') {
    return (
      <div
        data-testid="imagery-panel"
        className="px-3 py-2 rounded-lg bg-[#070D1A]/90 backdrop-blur-md border border-sky-500/25 text-[11px] font-mono text-sky-300/80 flex items-center gap-2"
      >
        <Satellite size={12} className="animate-pulse text-sky-400" />
        <span>Querying imagery metadata…</span>
      </div>
    )
  }

  if (state.status === 'error') {
    // No silent fallback — say the source is unavailable and let the user retry.
    return (
      <div
        data-testid="imagery-panel"
        role="status"
        className="px-3 py-2 rounded-lg bg-[#070D1A]/90 backdrop-blur-md border border-amber-500/30 text-[11px] font-mono text-amber-300 flex items-center gap-2"
      >
        <AlertTriangle size={12} className="text-amber-400" />
        <span>Imagery metadata: source temporarily unavailable.</span>
        <button
          onClick={() => setAttempt((n) => n + 1)}
          className="ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/15 border border-amber-400/40 hover:bg-amber-500/25 transition-colors"
        >
          <RefreshCw size={10} /> Retry
        </button>
      </div>
    )
  }

  const acquired = info.acquisition_date_available && info.acquired
    ? info.acquired
    : 'DATE UNAVAILABLE'
  const resolution = info.resolution_m_per_px
    ? `${info.resolution_m_per_px} m/px`
    : 'UNAVAILABLE'

  return (
    <div
      data-testid="imagery-panel"
      className="px-3 py-2 rounded-lg bg-[#070D1A]/90 backdrop-blur-md border border-sky-500/25 text-[11px] font-mono text-slate-300 space-y-0.5 shadow-lg"
    >
      <div className="flex items-center gap-1.5 text-sky-300 font-semibold tracking-wider">
        <Satellite size={12} className="text-sky-400" />
        IMAGERY PROVENANCE
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <span className="text-slate-500">Provider:</span>
        <span className="text-slate-200">{info.provider}</span>
        <span className="text-slate-500">Imagery acquisition:</span>
        <span className={info.acquisition_date_available ? 'text-slate-200' : 'text-amber-300'}>
          {acquired}
          {info.sensor ? ` · ${info.sensor}` : ''}
        </span>
        <span className="text-slate-500">Resolution:</span>
        <span className="text-slate-200">{resolution}</span>
      </div>
      {/* Honest scope limitation — Sentinel-2 cannot verify parcel boundaries */}
      {info.suitability && (
        <div className="pt-1 text-amber-300/90 flex items-start gap-1.5">
          <ShieldQuestion size={11} className="mt-0.5 shrink-0" />
          <span>{info.suitability}</span>
        </div>
      )}
      <div className="pt-0.5 text-slate-500 text-[11px]">
        Basemap is a mosaic of dated captures — not a live view.
      </div>
    </div>
  )
}

ImageryProvenancePanel.propTypes = {
  lng: PropTypes.number,
  lat: PropTypes.number,
  source: PropTypes.oneOf(['esri_wayback', 'sentinel2']),
}
