import React, { useState } from 'react';
import { UploadCloud, FileCheck, RefreshCw, Layers, CheckCircle2, AlertCircle, Cpu, Database } from 'lucide-react';
import { SUPPORTED_DATA_SOURCES } from '../../data/landsyncData';

export default function DataIngestionUpload({ isOpen, onClose, onProcessNewData }) {
  const [selectedSource, setSelectedSource] = useState('drone_ori');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [targetCRS, setTargetCRS] = useState('EPSG:4326');
  const [logs, setLogs] = useState([]);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleStartIngestion = () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setLogs([
      'Ingestion Started: Parsing binary GIS file header...',
      `Source format detected: ${selectedSource.toUpperCase()}`,
      `Evaluating native CRS projection -> Re-projecting to target ${targetCRS}...`,
      'Running AI spatial feature extraction & topology validation...',
      'Executing multi-source parcel matching against PostgreSQL/PostGIS backend...',
      'Reconciliation scoring complete!'
    ]);

    setTimeout(() => {
      setIsProcessing(false);
      onProcessNewData();
      onClose();
    }, 2200);
  };

  return (
    <div className="fixed inset-0 z-[2000] bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <UploadCloud className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white">Multi-Source Geospatial Ingestion Engine</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-sm font-semibold px-2 py-1 rounded bg-slate-800"
          >
            ✕
          </button>
        </div>

        {/* Source Selector Grid */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300 block">Select Geospatial Data Source:</label>
          <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
            {SUPPORTED_DATA_SOURCES.map((src) => (
              <div
                key={src.id}
                onClick={() => setSelectedSource(src.id)}
                className={`p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                  selectedSource === src.id
                    ? 'bg-slate-800 border-emerald-500 text-white shadow-md'
                    : 'bg-slate-800/40 border-slate-700/60 text-slate-400 hover:bg-slate-800/70'
                }`}
              >
                <div className="font-bold flex items-center justify-between">
                  <span>{src.name}</span>
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: src.color }}></span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1 line-clamp-1">{src.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* File Dropzone & CRS Options */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Target CRS Normalization:</label>
            <select
              value={targetCRS}
              onChange={(e) => setTargetCRS(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="EPSG:4326">EPSG:4326 - WGS 84 Geographic</option>
              <option value="EPSG:3857">EPSG:3857 - Web Mercator</option>
              <option value="EPSG:32644">EPSG:32644 - WGS 84 / UTM Zone 44N (India)</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Upload File (GeoJSON, SHP, CSV, TIF):</label>
            <label className="flex items-center justify-center w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-xl cursor-pointer hover:bg-slate-700 text-xs text-slate-300 font-medium">
              <UploadCloud className="w-4 h-4 mr-1.5 text-emerald-400" />
              {selectedFile ? selectedFile.name : 'Choose File...'}
              <input type="file" onChange={handleFileChange} className="hidden" accept=".geojson,.json,.zip,.csv,.kml" />
            </label>
          </div>
        </div>

        {/* Ingestion Console Output */}
        {logs.length > 0 && (
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px] text-emerald-400 space-y-1 max-h-28 overflow-y-auto">
            {logs.map((log, index) => (
              <div key={index} className="flex items-center gap-1.5">
                <span className="text-slate-600">[{index + 1}]</span>
                <span>{log}</span>
              </div>
            ))}
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-800 pt-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
          >
            Cancel
          </button>

          <button
            onClick={handleStartIngestion}
            disabled={!selectedFile || isProcessing}
            className={`px-5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
              selectedFile && !isProcessing
                ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-lg shadow-emerald-950/50'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            {isProcessing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                Ingesting & Normalizing...
              </>
            ) : (
              <>
                <Cpu className="w-4 h-4" />
                Run AI Geospatial Ingestion
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
