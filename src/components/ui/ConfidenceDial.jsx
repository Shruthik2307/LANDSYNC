import React from 'react'
import { clampConfidence } from '../../validation'

export default function ConfidenceDial({ value, compact = false }) {
  const safeValue = clampConfidence(value)
  const radius = compact ? 14 : 38
  const strokeWidth = compact ? 3 : 4.5
  const circumference = 2 * Math.PI * radius
  const dash = (safeValue / 100) * circumference
  
  // Dynamic color based on confidence thresholds
  const isHigh = safeValue >= 80
  const isMed = safeValue >= 50 && safeValue < 80
  const color = isHigh ? '#00F0FF' : isMed ? '#FFB800' : '#FF4C4C'
  const glowColor = isHigh ? 'rgba(0, 240, 255, 0.4)' : isMed ? 'rgba(255, 184, 0, 0.4)' : 'rgba(255, 76, 76, 0.4)'
  const statusText = isHigh ? 'HIGH CONFIDENCE' : isMed ? 'MODERATE CONSENSUS' : 'CRITICAL SHIFT'

  if (compact) {
    return (
      <div 
        className="relative inline-flex items-center justify-center shrink-0 w-8 h-8 font-mono"
        style={{ '--dash': dash, '--circumference': circumference }}
        title={`Confidence: ${safeValue}%`}
      >
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle 
            cx="18" 
            cy="18" 
            r={radius} 
            fill="none" 
            stroke="rgba(255, 255, 255, 0.1)" 
            strokeWidth={strokeWidth} 
          />
          <circle
            cx="18"
            cy="18"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            style={{ 
              transition: 'stroke-dasharray 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
              filter: `drop-shadow(0 0 3px ${glowColor})`
            }}
          />
        </svg>
        <span 
          className="absolute text-[11px] font-bold"
          style={{ color }}
        >
          {safeValue}
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center select-none">
      <div 
        className="relative w-24 h-24 flex items-center justify-center font-mono group"
        style={{ '--dash': dash, '--circumference': circumference }}
      >
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          {/* Outer Decorative Track */}
          <circle
            cx="50"
            cy="50"
            r="46"
            fill="none"
            stroke="rgba(0, 240, 255, 0.08)"
            strokeWidth="1"
            strokeDasharray="2 6"
          />
          
          {/* Base Track */}
          <circle 
            cx="50" 
            cy="50" 
            r={radius} 
            fill="none" 
            stroke="rgba(255, 255, 255, 0.08)" 
            strokeWidth={strokeWidth} 
          />
          
          {/* Animated Value Arc */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            style={{ 
              transition: 'stroke-dasharray 1s cubic-bezier(0.16, 1, 0.3, 1)',
              filter: `drop-shadow(0 0 6px ${glowColor})`
            }}
          />

          {/* Compass Axis Ticks */}
          <path d="M50 4v4M96 50h-4M50 96v-4M4 50h4" stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1" />
        </svg>

        {/* Center Percentage Display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span 
            className="text-2xl font-bold tracking-tight leading-none"
            style={{ color, textShadow: `0 0 12px ${glowColor}` }}
          >
            {safeValue}
            <span className="text-xs font-normal opacity-70 ml-0.5">%</span>
          </span>
          <span className="text-[11px] text-slate-400 font-sans uppercase tracking-widest mt-0.5">
            MATCH
          </span>
        </div>
      </div>

      {/* Signal Status Label */}
      <div 
        className="mt-2 text-[11px] font-mono uppercase tracking-widest font-semibold px-2 py-0.5 rounded border"
        style={{ 
          color, 
          borderColor: `${color}40`, 
          backgroundColor: `${color}15` 
        }}
      >
        {statusText}
      </div>
    </div>
  )
}
