import React from 'react';
import {
  Users,
  Fuel,
  Wrench,
  FileText,
  AlertTriangle,
  BarChart3,
  History,
  Settings,
  X,
  ShieldAlert,
  HelpCircle
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const MoreMenuModal = ({ isOpen, onClose, activeTab, setActiveTab, onOpenWalkthrough }) => {
  const { currentUser } = useAuth();
  if (!isOpen) return null;

  const menuItems = [
    { id: 'drivers', label: 'Drivers', desc: 'Driver profiles, licenses & performance', icon: Users, roles: ['Admin', 'Fleet Manager'] },
    { id: 'fuel', label: 'Fuel Ledger', desc: 'Fuel transactions, litres & station receipts', icon: Fuel, roles: ['Admin', 'Fleet Manager', 'Driver'] },
    { id: 'maintenance', label: 'Maintenance Hub', desc: 'Service logs, scheduling & repair invoices', icon: Wrench, roles: ['Admin', 'Fleet Manager', 'Driver'] },
    { id: 'documents', label: 'Document Vault', desc: 'RC, Insurance, PUC & Permit expiry alerts', icon: FileText, roles: ['Admin', 'Fleet Manager', 'Driver'] },
    { id: 'issues', label: 'Vehicle Issues', desc: 'Driver defect reporting & manager resolution', icon: AlertTriangle, roles: ['Admin', 'Fleet Manager', 'Driver'] },
    { id: 'reports', label: 'Reports & Analytics', desc: 'Fleet spend, fuel, trip profit & CSV exports', icon: BarChart3, roles: ['Admin', 'Fleet Manager'] },
    { id: 'audit', label: 'Audit Trail', desc: 'System mutation logs & user activity history', icon: History, roles: ['Admin'] },
    { id: 'settings', label: 'Settings', desc: 'Company profile, RBAC matrix & theme', icon: Settings, roles: ['Admin', 'Fleet Manager'] }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-0 sm:p-4">
      <div className="w-full max-w-lg glass-panel sm:rounded-2xl rounded-t-2xl border border-slate-700/80 p-5 shadow-2xl animate-slide-up max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-slate-700/60">
          <div>
            <h2 className="text-lg font-bold text-white">More Modules</h2>
            <p className="text-xs text-slate-400">Access full fleet management modules</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Workflow Simulator Banner */}
        <div
          onClick={() => {
            onClose();
            onOpenWalkthrough();
          }}
          className="mt-4 p-3 rounded-xl bg-gradient-to-r from-blue-600/30 via-indigo-600/30 to-purple-600/30 border border-blue-500/40 flex items-center justify-between cursor-pointer hover:border-blue-400 transition"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
              <HelpCircle className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-bold text-white">Acceptance Workflow Guide</div>
              <div className="text-[11px] text-slate-300">Step-by-step checklist of all 22 features</div>
            </div>
          </div>
          <span className="text-xs text-blue-400 font-bold px-2 py-1 bg-blue-500/20 rounded-lg">View</span>
        </div>

        {/* Module Items */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-4">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isAllowed = item.roles.includes(currentUser.role);
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                disabled={!isAllowed}
                onClick={() => {
                  if (isAllowed) {
                    setActiveTab(item.id);
                    onClose();
                  }
                }}
                className={`text-left p-3 rounded-xl border transition flex items-start gap-3 ${
                  !isAllowed
                    ? 'opacity-40 cursor-not-allowed bg-slate-900/50 border-slate-800'
                    : isActive
                    ? 'bg-blue-600/20 border-blue-500/50 text-white'
                    : 'bg-slate-800/60 border-slate-700/60 hover:bg-slate-700/60 text-slate-200'
                }`}
              >
                <div className={`p-2 rounded-lg ${isActive ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-700/50 text-slate-300'}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold truncate">{item.label}</span>
                    {!isAllowed && <ShieldAlert className="w-3.5 h-3.5 text-amber-500" title="Role Restricted" />}
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-2 mt-0.5">{item.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
