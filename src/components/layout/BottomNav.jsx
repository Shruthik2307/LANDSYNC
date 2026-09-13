import React from 'react';
import {
  LayoutDashboard,
  Truck,
  MapPin,
  CreditCard,
  Menu
} from 'lucide-react';

export const BottomNav = ({ activeTab, setActiveTab, onOpenMore }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'vehicles', label: 'Vehicles', icon: Truck },
    { id: 'trips', label: 'Trips', icon: MapPin },
    { id: 'expenses', label: 'Expenses', icon: CreditCard }
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 glass-panel border-t border-slate-700/60 pb-safe pt-1 px-2 shadow-2xl">
      <div className="max-w-md mx-auto flex items-center justify-around">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex flex-col items-center justify-center py-2 px-3 rounded-xl transition ${
                isActive
                  ? 'text-blue-400 font-bold bg-blue-500/10'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'scale-110' : ''}`} />
              <span className="text-[11px] mt-1 tracking-tight">{t.label}</span>
            </button>
          );
        })}

        {/* More Menu Trigger */}
        <button
          onClick={onOpenMore}
          className={`flex flex-col items-center justify-center py-2 px-3 rounded-xl transition ${
            ['drivers', 'fuel', 'maintenance', 'documents', 'issues', 'reports', 'audit', 'settings'].includes(activeTab)
              ? 'text-purple-400 font-bold bg-purple-500/10'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Menu className="w-5 h-5" />
          <span className="text-[11px] mt-1 tracking-tight">More</span>
        </button>
      </div>
    </nav>
  );
};
