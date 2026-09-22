import React from 'react';
import { SYSTEM_METRICS_OVERVIEW } from '../../data/landsyncData';
import { 
  BarChart3, 
  AlertTriangle, 
  Building2, 
  Map, 
  ShieldCheck, 
  ArrowUpRight,
  GitPullRequest
} from 'lucide-react';

export default function ExecutiveDashboard({ parcels = [] }) {
  const totalCount = parcels.length;
  const highPriorityCount = parcels.filter(p => p.priority === 'HIGH').length;
  const lowPriorityCount = parcels.filter(p => p.priority === 'LOW').length;

  const avgConfidence = Math.round(
    parcels.reduce((acc, p) => acc + (Number(p.confidence) || 0), 0) / (totalCount || 1)
  );

  const flaggedCount = parcels.filter(p => p.geometry_conflict || p.attribute_conflict || Math.abs(Number(p.area_difference) || 0) > 5).length || 1;
  const geomCount = parcels.filter(p => p.geometry_conflict).length;
  const geomPct = Math.round((geomCount / flaggedCount) * 100);
  const areaCount = parcels.filter(p => Math.abs(Number(p.area_difference) || 0) > 5).length;
  const areaPct = Math.round((areaCount / flaggedCount) * 100);
  const attrCount = parcels.filter(p => p.attribute_conflict).length;
  const attrPct = Math.round((attrCount / flaggedCount) * 100);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      
      {/* Top Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Total Parcels Analyzed</span>
            <Map className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-extrabold text-white">{totalCount}</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center">
              GHMC Live <ArrowUpRight className="w-3 h-3 ml-0.5" />
            </span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Hyderabad Reconciled Cadastral Zone</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Average Consensus Score</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-extrabold text-emerald-400">{avgConfidence}%</span>
            <span className="text-xs font-semibold text-slate-300">{lowPriorityCount} Clear</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-2 overflow-hidden">
            <div className="bg-emerald-400 h-full rounded-full" style={{ width: `${avgConfidence}%` }}></div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Field Verification Queue</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-extrabold text-rose-400">{highPriorityCount} Parcels</span>
            <span className="text-xs font-semibold text-rose-300 bg-rose-950 px-2 py-0.5 rounded border border-rose-800">
              HIGH Priority
            </span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Actionable field surveyor dispatch required</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Inter-Dept Sync Layer</span>
            <GitPullRequest className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-sm font-bold text-slate-100">{SYSTEM_METRICS_OVERVIEW.interdept_sync_status}</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Revenue, Cadastral, Municipal & Utility live</div>
        </div>

      </div>

      {/* Analytics Breakdown Charts & Department Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Conflict Type Distribution (7 Cols) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-emerald-400" />
              Geospatial Discrepancy Breakdown by Category
            </h3>
            <span className="text-xs text-slate-400">NAKSHA Zone 4 Analysis</span>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>Boundary Shift (Municipal Survey vs Cadastral Geometry)</span>
                <span className="font-bold text-slate-200">{geomPct}% ({geomCount} parcels)</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div className="bg-rose-500 h-full rounded-full transition-all duration-500" style={{ width: `${geomPct}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>Area Discrepancy (&gt; 5 m² Variance)</span>
                <span className="font-bold text-slate-200">{areaPct}% ({areaCount} parcels)</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div className="bg-amber-500 h-full rounded-full transition-all duration-500" style={{ width: `${areaPct}%` }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>Non-Spatial Attribute Mismatch (Revenue Record Attributes)</span>
                <span className="font-bold text-slate-200">{attrPct}% ({attrCount} parcels)</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div className="bg-cyan-500 h-full rounded-full transition-all duration-500" style={{ width: `${attrPct}%` }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Inter-Departmental Synchronization Matrix (5 Cols) */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-purple-400" />
              Inter-Department Data Alignment Matrix
            </h3>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60 flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Survey & Land Records Dept</div>
                <div className="text-[10px] text-slate-400">Cadastral Vector Polygons</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 font-medium">
                100% Synced
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60 flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Revenue Administration</div>
                <div className="text-[10px] text-slate-400">Owner Katha & Tax Attributes</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 font-medium">
                96% Synced
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60 flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Municipal Urban Planning</div>
                <div className="text-[10px] text-slate-400">Zoning & Building Footprints</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-amber-950 text-amber-300 border border-amber-800 font-medium">
                88% Synced
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-800/50 border border-slate-700/60 flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200">Water & Electricity Utilities</div>
                <div className="text-[10px] text-slate-400">Underground Pipelines & Lines</div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800 font-medium">
                91% Synced
              </span>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}
