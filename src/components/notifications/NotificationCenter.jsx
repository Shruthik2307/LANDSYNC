import React, { useState } from 'react';
import { useFleet } from '../../context/FleetContext';
import { Bell, X, CheckCheck, AlertTriangle, ShieldAlert, Info } from 'lucide-react';

export const NotificationCenter = ({ isOpen, onClose }) => {
  const { notifications, markNotificationAsRead, markAllNotificationsAsRead } = useFleet();
  const [filter, setFilter] = useState('All');

  if (!isOpen) return null;

  const filtered = notifications.filter((n) => filter === 'All' || n.category === filter);
  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-end sm:justify-center bg-black/75 backdrop-blur-sm p-0 sm:p-4">
      <div className="w-full sm:max-w-md h-full sm:h-auto max-h-[85vh] glass-panel sm:rounded-2xl border border-slate-700/80 p-5 shadow-2xl animate-fade-in flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-700/60">
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-base font-bold text-white">Notifications ({unreadCount} unread)</h2>
              <p className="text-xs text-slate-400">System alerts, document expiries & issue reports</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
                onClick={markAllNotificationsAsRead}
                className="text-[11px] font-bold text-blue-400 hover:underline flex items-center gap-1"
              >
                <CheckCheck className="w-3.5 h-3.5" /> Mark All Read
              </button>
            )}
            <button onClick={onClose} className="p-1 rounded-lg bg-slate-800 text-slate-400 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto pt-3 space-y-2 pr-1">
          {filtered.map((ntf) => (
            <div
              key={ntf.id}
              onClick={() => markNotificationAsRead(ntf.id)}
              className={`p-3 rounded-xl border transition cursor-pointer text-xs space-y-1 ${
                !ntf.read
                  ? 'bg-blue-600/10 border-blue-500/30 text-white font-semibold'
                  : 'bg-slate-800/40 border-slate-700/40 text-slate-300 opacity-75'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-100 flex items-center gap-1.5">
                  {ntf.type === 'Critical' ? (
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                  )}
                  {ntf.title}
                </span>
                <span className="text-[10px] text-slate-400">{ntf.timestamp}</span>
              </div>
              <p className="text-[11px] text-slate-300 font-normal">{ntf.message}</p>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="text-center text-slate-400 text-xs py-8">No notifications found.</div>
          )}
        </div>
      </div>
    </div>
  );
};
