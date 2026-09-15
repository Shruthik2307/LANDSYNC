import React, { useState } from 'react';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Search, 
  Filter, 
  ChevronRight, 
  MapPin, 
  FileText, 
  ShieldAlert, 
  Check, 
  Send, 
  Sliders, 
  Zap, 
  Info,
  ExternalLink,
  Layers
} from 'lucide-react';

export default function ConflictResolutionQueue({ 
  parcels, 
  selectedParcelId, 
  onSelectParcel,
  onResolveParcel 
}) {
  const [filterPriority, setFilterPriority] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('summary'); // 'summary' | 'side_by_side' | 'raw_contract'

  const filteredParcels = parcels.filter(parcel => {
    const matchesPriority = filterPriority === 'ALL' || parcel.priority === filterPriority;
    const matchesSearch = 
      parcel.parcel_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      parcel.survey_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      parcel.owner_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesPriority && matchesSearch;
  });

  const selectedParcel = parcels.find(p => p.parcel_id === selectedParcelId) || parcels[0];

  const getPriorityBadge = (priority) => {
    switch (priority) {
      case 'HIGH':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> HIGH</span>;
      case 'MEDIUM':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1"><Info className="w-3 h-3" /> MEDIUM</span>;
      case 'LOW':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> LOW</span>;
      default:
        return null;
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      {/* Left List: Conflict Verification Queue (5 Cols) */}
      <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col h-[620px] shadow-xl">
        
        {/* Search & Filter Header */}
        <div className="space-y-3 mb-4 pb-3 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-emerald-400" />
              Reconciliation Queue
            </h3>
            <span className="text-xs text-slate-400 font-medium">
              Showing {filteredParcels.length} of {parcels.length} parcels
            </span>
          </div>

          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search Parcel #, Survey, Owner..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            
            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="ALL">All Priorities</option>
              <option value="HIGH">High Priority</option>
              <option value="MEDIUM">Medium Priority</option>
              <option value="LOW">Low Priority</option>
            </select>
          </div>
        </div>

        {/* Parcel Cards Scrollable List */}
        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 custom-scrollbar">
          {filteredParcels.map((parcel) => {
            const isSelected = parcel.parcel_id === selectedParcel?.parcel_id;
            return (
              <div
                key={parcel.parcel_id}
                onClick={() => onSelectParcel(parcel.parcel_id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-slate-800/90 border-emerald-500 shadow-md shadow-emerald-950/40'
                    : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-start justify-between mb-1.5">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-100">Parcel #{parcel.parcel_id}</span>
                      <span className="text-xs text-slate-400 font-mono">Surv {parcel.survey_number}</span>
                    </div>
                    <div className="text-xs text-slate-300 font-medium truncate max-w-[200px]">
                      {parcel.owner_name}
                    </div>
                  </div>
                  {getPriorityBadge(parcel.priority)}
                </div>

                {/* Metrics Summary */}
                <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-700/50 mt-2">
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="text-slate-500 block text-[10px]">Confidence</span>
                      <span className={`font-bold ${parcel.confidence < 75 ? 'text-rose-400' : parcel.confidence < 90 ? 'text-amber-400' : 'text-emerald-400'}`}>
                        {parcel.confidence}%
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">Area Diff</span>
                      <span className="font-semibold text-slate-200">{parcel.area_difference} m²</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    {parcel.geometry_conflict && <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-950 text-rose-400 border border-rose-800">Geometry</span>}
                    {parcel.attribute_conflict && <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-950 text-amber-400 border border-amber-800">Attribute</span>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Inspection & Explainable AI Detail Drawer (7 Cols) */}
      <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col h-[620px] shadow-xl">
        {selectedParcel ? (
          <div className="flex flex-col h-full space-y-4">
            
            {/* Parcel Header & Actions */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-white">Parcel #{selectedParcel.parcel_id} Detail</h2>
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                    Survey {selectedParcel.survey_number}
                  </span>
                  {getPriorityBadge(selectedParcel.priority)}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {selectedParcel.village_name}, {selectedParcel.district}, {selectedParcel.state}
                </div>
              </div>

              <button
                onClick={() => onResolveParcel(selectedParcel.parcel_id)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition-all shadow-md shadow-emerald-950/50 flex items-center gap-1.5"
              >
                <Check className="w-4 h-4" />
                Approve Harmonization
              </button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-800 gap-4 text-xs font-semibold">
              <button
                onClick={() => setActiveTab('summary')}
                className={`pb-2 border-b-2 transition-all ${
                  activeTab === 'summary'
                    ? 'border-emerald-400 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Explainable AI Breakdown
              </button>
              <button
                onClick={() => setActiveTab('side_by_side')}
                className={`pb-2 border-b-2 transition-all ${
                  activeTab === 'side_by_side'
                    ? 'border-emerald-400 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                Multi-Source Side-by-Side
              </button>
              <button
                onClick={() => setActiveTab('raw_contract')}
                className={`pb-2 border-b-2 transition-all ${
                  activeTab === 'raw_contract'
                    ? 'border-emerald-400 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                SIH Shared Data Contract JSON
              </button>
            </div>

            {/* Tab 1: Explainable AI Breakdown */}
            {activeTab === 'summary' && (
              <div className="flex-1 overflow-y-auto space-y-4 pr-1 custom-scrollbar text-xs">
                
                {/* Confidence Card */}
                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/70 flex items-center justify-between">
                  <div>
                    <div className="text-slate-400 text-xs font-medium">Reconciliation Confidence Score</div>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="text-3xl font-extrabold text-emerald-400">{selectedParcel.confidence}%</span>
                      <span className="text-slate-400 text-xs">Overall System Reliability</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-slate-400 text-xs font-medium">Action Recommendation</div>
                    <div className="text-slate-200 font-semibold max-w-[260px] text-xs mt-1">
                      {selectedParcel.recommendation}
                    </div>
                  </div>
                </div>

                {/* Explainable Metric Score Breakdown */}
                {selectedParcel.score_breakdown && (
                  <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3">
                    <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                      <Zap className="w-4 h-4 text-amber-400" /> Explainable AI Metric Contributions
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                        <div className="text-slate-400 text-[11px]">Spatial Geometry Alignment</div>
                        <div className="text-sm font-bold text-slate-100 mt-0.5">
                          {selectedParcel.score_breakdown.geometry_score}/100 
                          <span className="text-slate-500 text-xs font-normal ml-1">({selectedParcel.score_breakdown.boundary_shift_meters}m shift)</span>
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                        <div className="text-slate-400 text-[11px]">Area Variance Match</div>
                        <div className="text-sm font-bold text-slate-100 mt-0.5">
                          {selectedParcel.score_breakdown.area_score}/100 
                          <span className="text-slate-500 text-xs font-normal ml-1">({selectedParcel.score_breakdown.area_diff_percent}% diff)</span>
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                        <div className="text-slate-400 text-[11px]">Attribute Fuzzy Similarity</div>
                        <div className="text-sm font-bold text-slate-100 mt-0.5">
                          {selectedParcel.score_breakdown.attribute_score}/100
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                        <div className="text-slate-400 text-[11px]">GNSS Ground Truthing</div>
                        <div className="text-sm font-bold text-slate-100 mt-0.5">
                          {selectedParcel.score_breakdown.gt_verification_score}/100
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Conflict Details Explanations */}
                <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-2">
                  <div className="font-semibold text-slate-200">Disagreement Audit Summary</div>
                  
                  <div className="space-y-1.5 text-slate-300">
                    <div className="flex items-start gap-2">
                      <span className="text-rose-400 font-bold">• Geometry:</span>
                      <span>{selectedParcel.conflict_summary?.geometry || 'No conflict'}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-amber-400 font-bold">• Area:</span>
                      <span>{selectedParcel.conflict_summary?.area || 'No conflict'}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-bold">• Attribute:</span>
                      <span>{selectedParcel.conflict_summary?.attribute || 'No conflict'}</span>
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* Tab 2: Multi-Source Side-by-Side */}
            {activeTab === 'side_by_side' && (
              <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar text-xs">
                <table className="w-full text-left border-collapse border border-slate-800">
                  <thead>
                    <tr className="bg-slate-800 text-slate-300">
                      <th className="p-2.5 border border-slate-700">Attribute Field</th>
                      <th className="p-2.5 border border-slate-700 text-blue-400">Cadastral Map</th>
                      <th className="p-2.5 border border-slate-700 text-emerald-400">Drone ORI / AI</th>
                      <th className="p-2.5 border border-slate-700 text-purple-400">Revenue Record</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200 font-mono text-[11px]">
                    <tr>
                      <td className="p-2 border border-slate-800 font-sans font-medium text-slate-400">Parcel Area</td>
                      <td className="p-2 border border-slate-800">{selectedParcel.area_cadastral_sqm} m²</td>
                      <td className="p-2 border border-slate-800 font-bold text-emerald-300">{selectedParcel.area_drone_sqm} m²</td>
                      <td className="p-2 border border-slate-800">{selectedParcel.area_cadastral_sqm} m²</td>
                    </tr>
                    <tr>
                      <td className="p-2 border border-slate-800 font-sans font-medium text-slate-400">Owner Name</td>
                      <td className="p-2 border border-slate-800">{selectedParcel.attribute_comparison?.cadastral_owner}</td>
                      <td className="p-2 border border-slate-800 text-slate-500">—</td>
                      <td className="p-2 border border-slate-800 font-bold text-purple-300">{selectedParcel.attribute_comparison?.revenue_owner}</td>
                    </tr>
                    <tr>
                      <td className="p-2 border border-slate-800 font-sans font-medium text-slate-400">Land Classification</td>
                      <td className="p-2 border border-slate-800">{selectedParcel.land_use}</td>
                      <td className="p-2 border border-slate-800 text-emerald-400">Extracted Boundary</td>
                      <td className="p-2 border border-slate-800">{selectedParcel.land_use}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 3: SIH Shared Data Contract JSON */}
            {activeTab === 'raw_contract' && (
              <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-emerald-400 custom-scrollbar">
                <pre>
{JSON.stringify(
  {
    parcel_id: selectedParcel.parcel_id,
    confidence: selectedParcel.confidence,
    priority: selectedParcel.priority,
    area_difference: selectedParcel.area_difference,
    geometry_conflict: selectedParcel.geometry_conflict,
    attribute_conflict: selectedParcel.attribute_conflict,
    recommendation: selectedParcel.recommendation
  },
  null,
  2
)}
                </pre>
              </div>
            )}

          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            Select a parcel from the queue to view reconciliation metrics.
          </div>
        )}
      </div>

    </div>
  );
}
