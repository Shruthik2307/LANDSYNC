import React, { useEffect, useState, useMemo } from 'react'
import { getConflicts, getHealth, getParcels, processDataset } from '../../api'
import BrandHeader from '../layout/BrandHeader'
import SummaryStrip from '../result/SummaryStrip'
import ResultMapStage from '../result/ResultMapStage'
import QueuePanel from '../result/QueuePanel'
import DetailPanel from '../result/DetailPanel'
import ExecutiveDashboard from '../analytics/ExecutiveDashboard'
import { MixedSourceNotice } from '../result/Provenance'
import ToastSystem from '../ui/ToastSystem'
import { priorityOf } from '../../validation'
import { AlertCircle, RefreshCw, Loader2 } from 'lucide-react'

const PRIORITY_ORDER = { HIGH: 3, MEDIUM: 2, LOW: 1 }

export default function ResultView({ 
  datasetId, 
  onRestart, 
  demoMode, 
  onToggleDemo, 
  onArchitecture,
  onNavigateLanding 
}) {
  const [parcels, setParcels] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [selected, setSelected] = useState(null)
  const [boundaryMode, setBoundaryMode] = useState('both')
  const [satelliteMode, setSatelliteMode] = useState(false)
  const [satelliteStatus, setSatelliteStatus] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [health, setHealth] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [unavailableSatelliteParcels, setUnavailableSatelliteParcels] = useState(() => new Set())
  const [processStatus, setProcessStatus] = useState('idle')
  const [processError, setProcessError] = useState('')
  const [viewMode, setViewMode] = useState('map')
  const [toasts, setToasts] = useState([])

  function addToast(message, type = 'success') {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => removeToast(id), 5000)
  }

  function removeToast(id) {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  async function handleRunProcess() {
    if (processStatus === 'processing') return
    setProcessStatus('processing')
    setProcessError('')
    try {
      const res = await processDataset(datasetId || 'sample')
      if (res.job_status === 'complete') {
        const [allParcels, conflictParcels] = await Promise.all([
          getParcels(),
          getConflicts()
        ])
        setParcels(allParcels)
        setConflicts(
          [...conflictParcels].sort(
            (a, b) => PRIORITY_ORDER[priorityOf(b)] - PRIORITY_ORDER[priorityOf(a)] || b.confidence - a.confidence
          )
        )
        if (allParcels.length > 0) {
          setSelected(allParcels[0])
        }
        setProcessStatus('complete')
        addToast('Reconciliation successful', 'success')
        setTimeout(() => setProcessStatus('idle'), 2500)
      } else {
        setProcessStatus('error')
        setProcessError(`Reconciliation status: ${res.job_status}`)
        addToast('Processing error occurred', 'error')
      }
    } catch (err) {
      setProcessStatus('error')
      setProcessError(err.message || 'Processing failed.')
      addToast('System failure during process', 'error')
    }
  }

  useEffect(() => {
    let cancelled = false

    async function loadResults() {
      try {
        const [allParcels, conflictParcels] = await Promise.all([
          getParcels().catch((requestError) => {
            throw new Error(`Parcels could not be loaded. ${requestError.message}`)
          }),
          getConflicts().catch((requestError) => {
            throw new Error(`Conflicts could not be loaded. ${requestError.message}`)
          }),
        ])
        if (cancelled) return
        setParcels(allParcels)
        setConflicts(
          [...conflictParcels].sort(
            (a, b) => PRIORITY_ORDER[priorityOf(b)] - PRIORITY_ORDER[priorityOf(a)] || b.confidence - a.confidence
          )
        )
        if (allParcels.length > 0) {
          setSelected(allParcels[0])
        }
        setStatus('ready')
      } catch (requestError) {
        if (cancelled) return
        setError(requestError.message)
        setStatus('error')
      }
    }

    // Dataset provenance for honest source badges (demo mode = fixture data).
    // All state updates happen in promise callbacks, never synchronously here.
    if (!demoMode) {
      getHealth().then((h) => { if (!cancelled) setHealth(h) }).catch(() => {})
    } else {
      Promise.resolve().then(() => {
        if (!cancelled) setHealth({ cadastral_source: 'SYNTHETIC_DEMO', municipal_source: 'SYNTHETIC_DEMO' })
      })
    }

    loadResults()
    return () => { cancelled = true }
  }, [datasetId, retryKey, demoMode])

  function retryRequest() {
    setError('')
    setStatus('loading')
    setRetryKey((key) => key + 1)
  }

  const orderedParcels = useMemo(
    () => [...parcels].sort((a, b) => PRIORITY_ORDER[priorityOf(b)] - PRIORITY_ORDER[priorityOf(a)] || b.confidence - a.confidence),
    [parcels]
  )
  
  const invalidParcels = useMemo(
    () => orderedParcels.filter((parcel) => !parcel?.boundaries?.cadastral?.coordinates?.[0]),
    [orderedParcels]
  )

  const matchesFilter = (parcel) => 
    (priorityFilter === 'ALL' || priorityOf(parcel) === priorityFilter) && 
    String(parcel.parcel_id || '').toLowerCase().includes(search.toLowerCase())

  // Loading View
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30">
        <BrandHeader 
          step="Result" 
          demoMode={demoMode} 
          onToggleDemo={onToggleDemo} 
          onArchitecture={onArchitecture}
          onNavigateLanding={onNavigateLanding}
        />
        <div className="flex-1 flex flex-col items-center justify-center gap-4 text-cyan-400 font-mono text-sm">
          <Loader2 size={32} className="animate-spin text-cyan-400" />
          <span className="tracking-widest uppercase text-xs animate-pulse">
            Preparing reconciliation results…
          </span>
        </div>
      </div>
    )
  }

  // Error View
  if (status === 'error') {
    return (
      <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30">
        <BrandHeader 
          step="Result" 
          demoMode={demoMode} 
          onToggleDemo={onToggleDemo} 
          onArchitecture={onArchitecture}
          onNavigateLanding={onNavigateLanding}
        />
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md p-6 rounded-2xl bg-slate-900/90 border border-red-500/30 text-center space-y-4 shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 flex items-center justify-center mx-auto">
              <AlertCircle size={24} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white mb-1">Parcels couldn&apos;t be loaded.</h2>
              <p className="text-xs text-slate-400 font-mono leading-relaxed">
                {error || 'Check the backend response and try again.'}
              </p>
            </div>
            <button
              onClick={retryRequest}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-400/50 text-red-200 text-xs font-semibold tracking-wide transition-colors"
            >
              <RefreshCw size={14} />
              <span>Retry request</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Ready State: Professional Analytical GIS Workspace
  return (
    <div className="h-screen w-full bg-[#030712] text-slate-100 flex flex-col overflow-hidden selection:bg-cyan-500/30">
      <BrandHeader 
        step="Reconciliation Map" 
        demoMode={demoMode} 
        onToggleDemo={onToggleDemo} 
        onArchitecture={onArchitecture}
        onNavigateLanding={onNavigateLanding}
      />
      
      {/* Top Telemetry KPI Summary Strip */}
      <SummaryStrip 
        parcels={parcels} 
        onProcess={handleRunProcess}
        processStatus={processStatus}
        processError={processError}
        viewMode={viewMode}
        onToggleView={setViewMode}
      />

      <MixedSourceNotice health={health} />

      {viewMode === 'dashboard' ? (
        <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-[#030712] fade-in">
          <ExecutiveDashboard parcels={parcels} />
        </div>
      ) : (
        /* Main Analytical Workspace Layout */
        <main className="flex-1 min-h-0 flex flex-col lg:flex-row relative overflow-hidden bg-tactical-grid">
          <ToastSystem toasts={toasts} removeToast={removeToast} />
          {/* Hero Map Container */}
          <div className="flex-1 min-h-0 h-full relative overflow-hidden">
            <div className="absolute inset-0 bg-radial-vignette pointer-events-none z-[500]" />
            <ResultMapStage
              selected={selected}
              setSelected={setSelected}
              boundaryMode={boundaryMode}
              setBoundaryMode={setBoundaryMode}
              satelliteMode={satelliteMode}
              setSatelliteMode={setSatelliteMode}
              satelliteStatus={satelliteStatus}
              setSatelliteStatus={setSatelliteStatus}
              unavailableSatelliteParcels={unavailableSatelliteParcels}
              setUnavailableSatelliteParcels={setUnavailableSatelliteParcels}
              orderedParcels={orderedParcels}
              matchesFilter={matchesFilter}
              invalidParcels={invalidParcels}
              satelliteEnabled={import.meta.env.VITE_ENABLE_SATELLITE_OVERLAY !== 'false'}
              sentinelHubInstanceId={import.meta.env.VITE_SENTINELHUB_INSTANCE_ID}
              cachedSatelliteUrl={(parcel) =>
                new Set(['1042', '1078', '1250']).has(String(parcel?.parcel_id))
                  ? '/satellite/demo-parcel-1042.svg'
                  : null
              }
            />

            {/* Floating Analytical Detail Inspector */}
            <DetailPanel 
              parcel={selected} 
              onClose={() => setSelected(null)} 
            />
          </div>

          {/* Conflict & Reconciliation Queue (Right Side) */}
          <div className="w-full lg:w-[360px] xl:w-[380px] h-[45vh] lg:h-full shrink-0 border-t lg:border-t-0 border-slate-800 hud-glass fade-in">
            <QueuePanel
              datasetId={datasetId}
              parcels={parcels}
              conflicts={conflicts}
              selected={selected}
              setSelected={setSelected}
              priorityFilter={priorityFilter}
              setPriorityFilter={setPriorityFilter}
              search={search}
              setSearch={setSearch}
              onRestart={onRestart}
              matchesFilter={matchesFilter}
              onProcess={handleRunProcess}
              processStatus={processStatus}
            />
          </div>

        </main>
      )}
    </div>
  )
}
