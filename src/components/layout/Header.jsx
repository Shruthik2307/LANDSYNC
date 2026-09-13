import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useFleet } from '../../context/FleetContext';
import {
  Truck,
  Bell,
  Sun,
  Moon,
  Wifi,
  WifiOff,
  UserCheck,
  CheckCircle2,
  ChevronDown,
  HelpCircle
} from 'lucide-react';

export const Header = ({ onOpenNotifications, onOpenMore, onOpenWalkthrough, activeTab }) => {
  const { currentUser, company, switchRole, theme, toggleTheme, isOffline } = useAuth();
  const { notifications } = useFleet();
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const roles = [
    { name: 'Admin', desc: 'Full system control & financial reports' },
    { name: 'Fleet Manager', desc: 'Operations, trips, drivers & maintenance' },
    { name: 'Driver', desc: 'Assigned vehicle, trips & issue logging' }
  ];

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-700/50 px-4 py-3 shadow-lg">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-2">
        {/* Brand & Company Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-bold">
            <Truck className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                FleetPulse
              </h1>
              <span className="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                PRO INDIA
              </span>
            </div>
            <p className="text-xs text-slate-400 truncate max-w-[140px] sm:max-w-xs">
              {company.name}
            </p>
          </div>
        </div>

        {/* Action Controls & Role Switcher */}
        <div className="flex items-center gap-2">
          {/* Acceptance Criteria Walkthrough Button */}
          <button
            onClick={onOpenWalkthrough}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition"
            title="View 22-Step Workflow Guide"
          >
            <HelpCircle className="w-4 h-4 text-indigo-400" />
            <span>Workflow Guide</span>
          </button>

          {/* Role Switcher Pill */}
          <div className="relative">
            <button
              onClick={() => setShowRoleDropdown(!showRoleDropdown)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs text-slate-200 transition"
            >
              <UserCheck className="w-4 h-4 text-blue-400" />
              <span className="font-semibold hidden xs:inline">{currentUser.role}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {showRoleDropdown && (
              <div className="absolute right-0 mt-2 w-64 glass-panel rounded-xl border border-slate-700 p-2 shadow-2xl z-50 animate-fade-in">
                <div className="text-[11px] uppercase tracking-wider text-slate-400 px-3 py-1 font-semibold">
                  Switch Active Role (RBAC Demo)
                </div>
                <div className="space-y-1 mt-1">
                  {roles.map((r) => (
                    <button
                      key={r.name}
                      onClick={() => {
                        switchRole(r.name);
                        setShowRoleDropdown(false);
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between transition ${
                        currentUser.role === r.name
                          ? 'bg-blue-600/30 text-blue-300 font-bold border border-blue-500/30'
                          : 'hover:bg-slate-800 text-slate-300'
                      }`}
                    >
                      <div>
                        <div>{r.name}</div>
                        <div className="text-[10px] text-slate-400 font-normal">{r.desc}</div>
                      </div>
                      {currentUser.role === r.name && (
                        <CheckCircle2 className="w-4 h-4 text-blue-400" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Offline indicator */}
          <div
            className={`flex items-center justify-center w-8 h-8 rounded-lg ${
              isOffline ? 'bg-rose-500/20 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'
            }`}
            title={isOffline ? 'Offline mode active (cached sync)' : 'Online & Connected'}
          >
            {isOffline ? <WifiOff className="w-4 h-4" /> : <Wifi className="w-4 h-4" />}
          </div>

          {/* Notification Center Trigger */}
          <button
            onClick={onOpenNotifications}
            className="relative p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition"
            title="Notification Center"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-rose-500 text-white font-bold text-[10px] flex items-center justify-center animate-bounce">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
