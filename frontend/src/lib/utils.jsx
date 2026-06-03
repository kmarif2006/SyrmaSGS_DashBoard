import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Format a number as INR currency (Cr / L / raw)
 */
export function formatINR(value, compact = true) {
  if (value == null || isNaN(value)) return '₹0'
  const abs = Math.abs(value)
  if (compact) {
    if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`
    if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`
    if (abs >= 1e3) return `₹${(value / 1e3).toFixed(1)}K`
  }
  return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

/**
 * Format large number (compact: K, M, B)
 */
export function formatNumber(value) {
  if (value == null || isNaN(value)) return '0'
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`
  return Number(value).toLocaleString('en-IN', { maximumFractionDigits: 1 })
}

/**
 * Shorten a long supplier/material name for chart labels
 */
export function truncate(str, maxLen = 28) {
  if (!str) return ''
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str
}

/**
 * Chart color palette
 */
export const CHART_COLORS = [
  '#6366f1', '#8b5cf6', '#06b6d4', '#10b981',
  '#f59e0b', '#ec4899', '#f97316', '#14b8a6',
  '#84cc16', '#64748b', '#a78bfa', '#34d399',
]

/**
 * Custom dark-theme recharts tooltip
 */
export function CustomTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 shadow-2xl text-xs">
      <p className="text-slate-400 mb-2 font-medium">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span className="text-slate-300">{p.name}:</span>
          <span className="text-white font-semibold">
            {formatter ? formatter(p.value, p.name) : p.value?.toLocaleString?.()}
          </span>
        </div>
      ))}
    </div>
  )
}

export function inrTooltipFormatter(value) {
  return formatINR(value)
}
