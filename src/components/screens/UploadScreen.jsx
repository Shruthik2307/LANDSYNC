import React, { useState, useRef } from 'react'
import { Upload, FileUp, X, AlertCircle, FileText, Shield, ArrowRight, CheckCircle2, Sparkles, Settings } from 'lucide-react'
import { uploadDataset, API_BASE_URL, setApiBaseUrl } from '../../api'
import BrandHeader from '../layout/BrandHeader'
import sampleCadastral from '../../data/cadastral.geojson'

export default function UploadScreen({ onComplete, demoMode, onToggleDemo, onArchitecture, onNavigateLanding }) {
  const [files, setFiles] = useState([])
  const [isDragging, setIsDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const [error, setError] = useState('')
  const [showConfig, setShowConfig] = useState(false)
  const [customBackendUrl, setCustomBackendUrl] = useState(API_BASE_URL || 'https://landsync-cmcg.onrender.com')
  const fileInputRef = useRef(null)

  function addFiles(nextFiles) {
    if (!nextFiles || !nextFiles.length) return
    const incoming = Array.from(nextFiles)
    setFiles((current) => {
      const existingNames = new Set(current.map(f => f.name))
      const deduplicated = incoming.filter(f => !existingNames.has(f.name))
      return [...current, ...deduplicated]
    })
    setError('')
    setUploadSuccess(null)
  }

  function removeFile(indexToRemove) {
    setFiles(current => current.filter((_, idx) => idx !== indexToRemove))
    setUploadSuccess(null)
  }

  function loadSampleData() {
    try {
      const blob = new Blob([JSON.stringify(sampleCadastral)], { type: 'application/geo+json' })
      const sampleFile = new File([blob], 'hyd_cadastral.geojson', { type: 'application/geo+json' })
      addFiles([sampleFile])
    } catch (e) {
      console.error('Failed to load sample dataset', e)
    }
  }

  function handleSaveBackendUrl(e) {
    e.preventDefault()
    setApiBaseUrl(customBackendUrl.trim())
    window.location.reload()
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (!files.length || submitting) return
    setSubmitting(true)
    setError('')

    // Validate that at least one file is a GeoJSON or JSON file
    const hasGeoJson = files.some(f => {
      const name = (f.name || '').toLowerCase()
      return name.endsWith('.geojson') || name.endsWith('.json')
    })

    if (!hasGeoJson && !demoMode) {
      setSubmitting(false)
      setError('Please upload a valid GeoJSON dataset (.geojson or .json). The LANDSYNC engine reconciles cadastral and municipal boundary FeatureCollections.')
      return
    }

    uploadDataset(files)
      .then(({ dataset_id }) => {
        setSubmitting(false)
        onComplete(dataset_id)
      })
      .catch((requestError) => {
        setSubmitting(false)
        const detail = requestError?.detail
        let msg = requestError?.message || 'Upload operation failed. Please check network connection and try again.'
        if (detail && !msg.includes(typeof detail === 'string' ? detail : '')) {
          msg = `${msg}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
        }
        setError(msg)
      })
  }

  const getFileBadgeColor = (fileName) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    switch (ext) {
      case 'geojson':
      case 'json':
        return 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
      case 'shp':
      case 'shx':
        return 'bg-blue-500/15 text-blue-300 border-blue-500/30'
      case 'csv':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
      case 'pdf':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
      default:
        return 'bg-purple-500/15 text-purple-300 border-purple-500/30'
    }
  }

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col selection:bg-cyan-500/30">
      <BrandHeader 
        step="Upload" 
        demoMode={demoMode} 
        onToggleDemo={onToggleDemo} 
        onArchitecture={onArchitecture}
        onNavigateLanding={onNavigateLanding}
      />

      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 md:p-10 relative overflow-hidden">
        {/* Subtle Background Glows */}
        <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-cyan-500/5 blur-[120px] rounded-full pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/5 blur-[120px] rounded-full pointer-events-none" />

        <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center relative z-10">
          
          {/* Left Column: Context & Capabilities */}
          <div className="lg:col-span-5 space-y-6">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-400 bg-cyan-950/60 border border-cyan-500/30 px-2.5 py-1 rounded-full">
                Phase 1: Ingestion
              </span>
              <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mt-4 mb-3">
                Ingest Source Intelligence.
              </h1>
              <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
                Upload geospatial and registry files that describe the same cadastral parcel from different operational perspectives.
              </p>
            </div>

            {/* Ingestion Channels */}
            <div className="space-y-3 pt-2">
              <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <div className="p-1.5 rounded bg-cyan-500/10 text-cyan-400 mt-0.5">
                  <FileText size={16} />
                </div>
                <div>
                  <h2 className="text-xs font-semibold text-slate-200">Cadastral & Revenue Records</h2>
                  <p className="text-[11px] text-slate-400">RoR, survey numbers, ownership deeds (PDF, CSV, SHP)</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-900/50 border border-slate-800">
                <div className="p-1.5 rounded bg-blue-500/10 text-blue-400 mt-0.5">
                  <Upload size={16} />
                </div>
                <div>
                  <h2 className="text-xs font-semibold text-slate-200">Municipal Survey Records</h2>
                  <p className="text-[11px] text-slate-400">High-resolution spatial boundary vectors (GeoJSON, GeoTIFF)</p>
                </div>
              </div>
            </div>

            {/* Mode Banner */}
            <div className="p-3.5 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Shield size={18} className={demoMode ? 'text-amber-400' : 'text-emerald-400'} />
                  <div className="text-xs">
                    <span className="text-slate-300 font-medium">
                      {demoMode ? 'Local Isolated Mode' : 'Live Backend Engine'}
                    </span>
                    <p className="text-slate-500 text-[11px]">
                      {demoMode ? 'Processes against prepared verification datasets.' : `Target: ${API_BASE_URL || 'Current Origin'}/api/upload`}
                    </p>
                  </div>
                </div>
                {!demoMode && (
                  <button
                    type="button"
                    onClick={() => setShowConfig(!showConfig)}
                    className="text-slate-400 hover:text-cyan-400 p-1 rounded hover:bg-slate-800 transition-colors"
                    title="Configure Backend URL"
                    aria-label="Configure Backend URL"
                  >
                    <Settings size={14} />
                  </button>
                )}
              </div>

              {showConfig && !demoMode && (
                <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
                  <span className="text-[10px] text-slate-400 block">Render Backend URL (saved in browser):</span>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={customBackendUrl}
                      onChange={(e) => setCustomBackendUrl(e.target.value)}
                      placeholder="https://your-backend.onrender.com"
                      className="flex-1 bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                    />
                    <button
                      type="button"
                      onClick={handleSaveBackendUrl}
                      className="px-2.5 py-1 bg-cyan-400 text-slate-950 font-bold rounded text-xs hover:bg-white transition-all"
                    >
                      Save
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: High-End Drop Zone & File List */}
          <div className="lg:col-span-7">
            <form 
              onSubmit={handleSubmit}
              className="p-6 sm:p-8 rounded-2xl bg-slate-900/70 backdrop-blur-xl border border-cyan-500/20 shadow-[0_20px_50px_rgba(0,0,0,0.6)] relative"
            >
              {/* Drop Target */}
              <div
                className={`group relative flex flex-col items-center justify-center p-8 sm:p-10 rounded-xl border-2 border-dashed transition-all duration-300 cursor-pointer text-center ${
                  isDragging 
                    ? 'border-cyan-400 bg-cyan-500/10 scale-[1.01] shadow-[0_0_30px_rgba(0,240,255,0.2)]'
                    : 'border-slate-700/80 bg-slate-950/40 hover:border-cyan-500/40 hover:bg-slate-900/60'
                }`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setIsDragging(false)
                  if (e.dataTransfer.files) addFiles(e.dataTransfer.files)
                }}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
                aria-label="Upload land records file drop zone"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => addFiles(e.target.files)}
                />

                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-transform duration-300 ${
                  isDragging ? 'scale-110 bg-cyan-400 text-black' : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 group-hover:scale-105'
                }`}>
                  <FileUp size={28} />
                </div>

                <div className="space-y-1.5">
                  <p className="text-sm sm:text-base font-bold text-slate-100 tracking-wide">
                    {isDragging ? 'Release to Ingest Sources' : 'DROP LAND RECORDS'}
                  </p>
                  <p className="text-xs text-slate-400 font-mono">
                    GeoJSON • JSON (FeatureCollection)
                  </p>
                  <p className="text-[11px] text-cyan-400/80 pt-1">
                    or <span className="underline underline-offset-2 font-medium">Browse Files</span> from your computer
                  </p>
                </div>
              </div>

              {/* Instant Load Sample Data Button */}
              <button
                type="button"
                onClick={loadSampleData}
                className="mt-3 text-xs text-cyan-300 hover:text-cyan-200 flex items-center justify-center gap-1.5 w-full font-mono py-2 px-3 rounded-lg border border-cyan-500/30 bg-cyan-950/40 hover:bg-cyan-900/50 transition-all shadow-sm"
              >
                <Sparkles size={13} className="text-cyan-400 shrink-0" />
                <span>Quick-Load Sample Hyderabad Dataset (cadastral.geojson)</span>
              </button>

              {/* Uploaded File List */}
              {files.length > 0 && (
                <div className="mt-5 space-y-2 max-h-48 overflow-y-auto pr-1" aria-label="Selected files">
                  <div className="flex items-center justify-between text-xs text-slate-400 font-mono px-1">
                    <span>STAGED SOURCES ({files.length})</span>
                    <button 
                      type="button" 
                      onClick={() => setFiles([])}
                      className="text-slate-500 hover:text-red-400 text-[10px]"
                    >
                      Clear all
                    </button>
                  </div>
                  {files.map((file, idx) => (
                    <div 
                      key={`${file.name}-${idx}`}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs text-slate-200"
                    >
                      <div className="flex items-center gap-2.5 truncate max-w-[80%]">
                        <span className={`px-1.5 py-0.5 rounded font-mono text-[9px] font-bold border uppercase ${getFileBadgeColor(file.name)}`}>
                          {file.name.split('.').pop() || 'FILE'}
                        </span>
                        <span className="truncate font-medium">{file.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[10px] text-slate-400">
                          {Math.max(1, Math.round(file.size / 1024))} KB
                        </span>
                        <button
                          type="button"
                          onClick={() => removeFile(idx)}
                          className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                          title="Remove file"
                        >
                          <X size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Action Button */}
              <div className="mt-6">
                <button
                  type="submit"
                  disabled={!files.length || submitting}
                  className="w-full py-3.5 px-6 rounded-lg bg-cyan-400 text-[#030712] font-bold text-sm tracking-wide shadow-[0_0_25px_rgba(0,240,255,0.35)] hover:bg-white hover:shadow-[0_0_35px_rgba(0,240,255,0.5)] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-cyan-400 disabled:hover:shadow-none flex items-center justify-center gap-2 transition-all duration-200"
                >
                  {submitting ? (
                    <>
                      <span className="w-4 h-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                      <span>
                        {files[0]?.size > 5 * 1024 * 1024
                          ? `Uploading large file (${Math.round(files[0].size / (1024 * 1024))} MB)… please wait`
                          : 'Preparing dataset…'}
                      </span>
                    </>
                  ) : (
                    <>
                      <span>
                        {files.length === 0 
                          ? 'Select files to continue' 
                          : `Process ${files.length} source${files.length === 1 ? '' : 's'}`}
                      </span>
                      {files.length > 0 && <ArrowRight size={16} />}
                    </>
                  )}
                </button>
              </div>

              {/* Upload Success Banner */}
              {uploadSuccess && (
                <div className="mt-4 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex flex-col sm:flex-row items-center justify-between gap-3 animate-fadeIn" role="status">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
                    <div>
                      <strong className="font-semibold text-emerald-200 block">Upload Successful!</strong>
                      <span className="font-mono text-[11px] text-slate-300">Dataset ID: {uploadSuccess.dataset_id}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onComplete(uploadSuccess.dataset_id)}
                    className="px-3.5 py-1.5 rounded-lg bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-[0_0_15px_rgba(0,240,255,0.4)] hover:bg-white transition-all shrink-0"
                  >
                    <span>Proceed to Reconciliation</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              )}

              {/* Error Banner */}
              {error && (
                <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start gap-2.5 animate-fadeIn" role="alert">
                  <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <strong className="font-semibold block text-red-200">Upload didn&apos;t finish.</strong>
                    <span>{error}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setError('')}
                    className="text-red-400 hover:text-white text-xs underline underline-offset-2 ml-2"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              <p className="mt-4 text-center text-[10px] text-slate-500 font-mono">
                {demoMode 
                  ? 'Demo mode keeps your files local and uses synthetic parcel results.' 
                  : 'Files will be sent to the configured FastAPI backend.'}
              </p>
            </form>
          </div>
        </div>
      </main>
    </div>
  )
}
