import { motion } from 'framer-motion'
import { formatINR, formatNumber, cn } from '../lib/utils'

const gradients = [
  'from-indigo-500 to-violet-600',
  'from-cyan-500 to-blue-600',
  'from-emerald-500 to-teal-600',
  'from-amber-500 to-orange-600',
  'from-pink-500 to-rose-600',
  'from-violet-500 to-purple-600',
  'from-red-500 to-pink-600',
  'from-teal-500 to-cyan-600',
]

function Skeleton() {
  return (
    <div className="glass-card p-5 animate-pulse">
      <div className="h-3 w-24 bg-slate-700 rounded mb-4" />
      <div className="h-8 w-32 bg-slate-700 rounded mb-2" />
      <div className="h-2 w-16 bg-slate-700 rounded" />
    </div>
  )
}

export default function KPICard({ icon: Icon, label, value, sub, format = 'inr', index = 0, isLoading }) {
  if (isLoading) return <Skeleton />

  const gradient = gradients[index % gradients.length]
  const displayValue = format === 'inr'
    ? formatINR(value)
    : format === 'number'
    ? formatNumber(value)
    : format === 'pct'
    ? `${value?.toFixed?.(1)}%`
    : value?.toLocaleString?.('en-IN') ?? value

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
      className="glass-card-hover p-5 group cursor-default"
    >
      <div className="flex items-start justify-between mb-3">
        <div className={cn(
          'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0',
          `bg-gradient-to-br ${gradient} shadow-lg`
        )}>
          {Icon && <Icon size={18} className="text-white" />}
        </div>
        <div className={cn(
          'w-1.5 h-1.5 rounded-full mt-1',
          `bg-gradient-to-br ${gradient}`
        )} />
      </div>

      <p className="text-xs text-slate-500 font-medium mb-1 uppercase tracking-wider">{label}</p>

      <motion.p
        key={displayValue}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-2xl font-bold text-white leading-none mb-1.5 font-mono tracking-tight"
      >
        {displayValue}
      </motion.p>

      {sub && <p className="text-xs text-slate-500">{sub}</p>}

      {/* Bottom gradient bar */}
      <div className={cn('h-0.5 mt-4 rounded-full bg-gradient-to-r opacity-30 group-hover:opacity-60 transition-opacity', gradient)} />
    </motion.div>
  )
}
