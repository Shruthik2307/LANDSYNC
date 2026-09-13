import React, { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, AlertCircle, RefreshCw, Cpu, Activity } from 'lucide-react'
import { processDataset } from '../../api'
import BrandHeader from '../layout/BrandHeader'

const PIPELINE_STEPS = [
  { title: 'Normalizing CRS', detail: 'Aligning coordinate reference systems across source files' },
  { title: 'Matching parcels', detail: 'Linking cadastral, drone, and revenue records' },
  { title: 'Checking geometry & attributes', detail: 'Comparing boundaries and record fields' },
  { title: 'Scoring confidence', detail: 'Ranking each reconciliation result' },
]

export default function ProcessingScreen({ datasetId, onComplete, demoMode, onToggleDemo, onArchitecture, onNavigateLanding }) {
  const [activeStep, setActiveStep] = useState(0)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    const interval = window.setInterval(() => {
      setActiveStep((step) => Math.min(step + 1, PIPELINE_STEPS.length - 1))
    }, 750)

    let cancelled = false
    processDataset(datasetId)
      .then((result) => {
        if (cancelled) return
        if (result.job_status === 'complete') {
          onComplete()
        } else {
          setError(`The backend returned “${result.job_status}” instead of a completed result.`)
        }
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError?.message || 'Processing failed.')
      })

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [datasetId, retryKey, demoMode, onComplete])

  function retryProcessing() {
    setActiveStep(0)
    setError('')
    setRetryKey((key) => key + 1)
  }

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30">
      <BrandHeader 
        step="Processing" 
        demoMode={demoMode} 
        onToggleDemo={onToggleDemo} 
        onArchitecture={onArchitecture}
        onNavigateLanding={onNavigateLanding}
      />

      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 md:p-10 relative overflow-hidden">
        {/* Subtle Background Glows */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-cyan-500/5 blur-[140px] rounded-full pointer-events-none" />

        <div className="w-full max-w-3xl space-y-8 relative z-10">
          {/* Header Card */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/70 border border-cyan-500/30 text-cyan-300 text-xs font-mono tracking-widest uppercase">
              <Cpu size={14} className="text-cyan-400 animate-pulse" />
              <span>Synthesis Engine Active</span>
            </div>

            <h1 className="text-2xl sm:text-4xl font-bold tracking-tight text-white">
              Reconciling Multimodal Data Streams.
            </h1>

            <p className="text-slate-400 text-sm max-w-xl mx-auto leading-relaxed">
              Harmonizing boundary geometries, validating record attributes, and computing multi-factor consensus.
            </p>

            {datasetId && (
              <div className="inline-block pt-1 font-mono text-[11px] text-cyan-400/70">
                SESSION ID: <span className="text-slate-200">{datasetId}</span>
              </div>
            )}
          </div>

          {/* Pipeline Monitor Card */}
          <div className="p-6 sm:p-8 rounded-2xl bg-slate-900/80 backdrop-blur-xl border border-cyan-500/20 shadow-[0_20px_50px_rgba(0,0,0,0.6)] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs font-mono text-slate-400">
              <span className="flex items-center gap-2">
                <Activity size={14} className="text-cyan-400" />
                Reconciliation pipeline
              </span>
              <span className="text-cyan-400">
                {activeStep + 1} / {PIPELINE_STEPS.length} STEPS
              </span>
            </div>

            {/* Steps List */}
            <div className="space-y-3 pt-2">
              {PIPELINE_STEPS.map((step, idx) => {
                const isDone = idx < activeStep
                const isActive = idx === activeStep

                return (
                  <div
                    key={step.title}
                    className={`flex items-start gap-4 p-3.5 rounded-xl border transition-all duration-300 ${
                      isActive
                        ? 'bg-cyan-950/30 border-cyan-500/40 shadow-[0_0_20px_rgba(0,240,255,0.1)]'
                        : isDone
                        ? 'bg-slate-950/40 border-emerald-500/20'
                        : 'bg-slate-950/20 border-slate-800/60 opacity-50'
                    }`}
                  >
                    {/* Status Icon */}
                    <div className="mt-0.5 shrink-0">
                      {isDone ? (
                        <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-400 flex items-center justify-center text-emerald-400">
                          <CheckCircle2 size={14} />
                        </div>
                      ) : isActive ? (
                        <div className="w-6 h-6 rounded-full bg-cyan-500/20 border border-cyan-400 flex items-center justify-center text-cyan-400 animate-spin">
                          <Loader2 size={14} />
                        </div>
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] font-mono text-slate-400">
                          {idx + 1}
                        </div>
                      )}
                    </div>

                    {/* Step Description */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-semibold tracking-wide ${
                          isActive ? 'text-cyan-300' : isDone ? 'text-slate-200' : 'text-slate-400'
                        }`}>
                          {step.title}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-wider">
                          {isDone ? (
                            <span className="text-emerald-400">Complete</span>
                          ) : isActive ? (
                            <span className="text-cyan-400 animate-pulse">Running…</span>
                          ) : (
                            <span className="text-slate-500">Queued</span>
                          )}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {step.detail}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Error Message if Any */}
            {error && (
              <div className="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-xs flex items-start justify-between gap-3 animate-fadeIn" role="alert">
                <div className="flex items-start gap-2.5">
                  <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-semibold block text-red-100">Processing needs attention.</strong>
                    <span className="text-red-300">{error}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={retryProcessing}
                  className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 border border-red-400/40 text-red-200 font-medium text-xs flex items-center gap-1.5 transition-colors shrink-0"
                >
                  <RefreshCw size={13} />
                  <span>Retry processing</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
