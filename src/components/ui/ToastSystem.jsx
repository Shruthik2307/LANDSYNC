import React from 'react'
import { X } from 'lucide-react'

export default function ToastSystem({ toasts, removeToast }) {
  return (
    <div className="fixed bottom-4 right-4 z-[1000] flex flex-col gap-2 w-72">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`p-3 rounded-lg border backdrop-blur-md animate-fadeIn flex items-start gap-3 shadow-2xl ${
            toast.type === 'success'
              ? 'bg-emerald-950/80 border-emerald-500/30 text-emerald-200'
              : 'bg-red-950/80 border-red-500/30 text-red-200'
          }`}
        >
          <div className="flex-1 text-xs font-mono">
            {toast.message}
          </div>
          <button onClick={() => removeToast(toast.id)} className="text-slate-400 hover:text-white">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
