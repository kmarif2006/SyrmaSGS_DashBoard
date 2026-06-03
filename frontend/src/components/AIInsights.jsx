import { motion } from 'framer-motion'
import {
  TrendingUp, PieChart, Factory, Building2, Clock, Trash2, BarChart3, Lightbulb
} from 'lucide-react'
import { cn } from '../lib/utils'

const iconMap = { TrendingUp, PieChart, Factory, Building2, Clock, Trash2, BarChart3 }
const severityMap = {
  info:    { border: 'border-indigo-500/30', bg: 'bg-indigo-500/10', text: 'text-indigo-300', badge: 'badge-indigo' },
  warning: { border: 'border-amber-500/30',  bg: 'bg-amber-500/10',  text: 'text-amber-300',  badge: 'badge-amber'  },
  success: { border: 'border-emerald-500/30',bg: 'bg-emerald-500/10',text: 'text-emerald-300',badge: 'badge-green'  },
  error:   { border: 'border-red-500/30',    bg: 'bg-red-500/10',    text: 'text-red-300',    badge: 'badge-red'    },
}

function InsightCard({ insight, index }) {
  const Icon = iconMap[insight.icon] || Lightbulb
  const s = severityMap[insight.severity] || severityMap.info

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      className={cn('glass-card p-4 border', s.border)}
    >
      <div className="flex items-start gap-3">
        <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0', s.bg)}>
          <Icon size={17} className={s.text} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm font-semibold text-slate-200">{insight.title}</p>
            {insight.metric && (
              <span className={cn('badge ml-auto flex-shrink-0', s.badge)}>{insight.metric}</span>
            )}
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{insight.message}</p>
        </div>
      </div>
    </motion.div>
  )
}

function SkeletonCard() {
  return (
    <div className="glass-card p-4 animate-pulse">
      <div className="flex gap-3">
        <div className="w-9 h-9 bg-slate-700 rounded-xl flex-shrink-0" />
        <div className="flex-1">
          <div className="h-3 bg-slate-700 rounded w-32 mb-2" />
          <div className="h-2 bg-slate-700 rounded w-48" />
          <div className="h-2 bg-slate-700 rounded w-36 mt-1" />
        </div>
      </div>
    </div>
  )
}

export default function AIInsights({ data, isLoading }) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
          <Lightbulb size={14} className="text-white" />
        </div>
        <h2 className="text-base font-bold text-white">AI-Generated Insights</h2>
        <span className="badge-amber ml-1">Automated</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
          : data?.map((insight, i) => <InsightCard key={insight.id} insight={insight} index={i} />)
        }
      </div>
    </section>
  )
}
