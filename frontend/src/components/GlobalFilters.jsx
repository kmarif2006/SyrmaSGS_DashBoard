import { useState } from 'react'
import { ChevronDown, SlidersHorizontal, X } from 'lucide-react'
import { cn } from '../lib/utils'

function FilterSelect({ label, options, value, onChange, multi = false }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</label>
      <select
        multiple={multi}
        value={value || (multi ? [] : '')}
        onChange={e => {
          if (multi) {
            const vals = Array.from(e.target.selectedOptions).map(o => o.value)
            onChange(vals.join(','))
          } else {
            onChange(e.target.value)
          }
        }}
        className={cn(
          'bg-slate-800/80 border border-slate-700/60 text-slate-200 text-xs rounded-lg px-2 py-1.5',
          'focus:outline-none focus:border-indigo-500/60 transition-colors',
          multi ? 'h-20' : 'h-8'
        )}
      >
        {!multi && <option value="">All</option>}
        {options?.map(o => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  )
}

function DateInput({ label, value, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</label>
      <input
        type="date"
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="bg-slate-800/80 border border-slate-700/60 text-slate-200 text-xs rounded-lg px-2 py-1.5 h-8 focus:outline-none focus:border-indigo-500/60 transition-colors"
      />
    </div>
  )
}

export default function GlobalFilters({ filterOptions, filters, setFilters, loading }) {
  const [open, setOpen] = useState(false)

  const activeCount = Object.values(filters || {}).filter(v => v && v !== '').length

  const update = (key) => (val) => setFilters(prev => ({ ...prev, [key]: val }))

  const clearAll = () => setFilters({})

  return (
    <div className="bg-slate-900/60 border-b border-slate-800/60 sticky top-16 z-40">
      <div className="max-w-[1600px] mx-auto px-5">
        {/* Toggle bar */}
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2.5 py-2.5 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors"
        >
          <SlidersHorizontal size={14} />
          <span>Filters</span>
          {activeCount > 0 && (
            <span className="px-1.5 py-0.5 bg-indigo-500/30 text-indigo-300 text-[10px] font-bold rounded-full border border-indigo-500/40">
              {activeCount}
            </span>
          )}
          <ChevronDown size={13} className={cn('transition-transform', open && 'rotate-180')} />
          {activeCount > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); clearAll() }}
              className="ml-2 flex items-center gap-1 text-xs text-slate-500 hover:text-red-400 transition-colors"
            >
              <X size={11} /> Clear
            </button>
          )}
        </button>

        {/* Filter panel */}
        {open && (
          <div className="pb-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <FilterSelect label="Company Code" options={filterOptions?.company_codes} value={filters.company_code} onChange={update('company_code')} />
            <FilterSelect label="Plant" options={filterOptions?.plants} value={filters.plant} onChange={update('plant')} />
            <FilterSelect label="Purch. Group" options={filterOptions?.purchasing_groups} value={filters.purchasing_group} onChange={update('purchasing_group')} />
            <FilterSelect label="Currency" options={filterOptions?.currencies} value={filters.currency} onChange={update('currency')} />
            <DateInput label="Date From" value={filters.date_from} onChange={update('date_from')} />
            <DateInput label="Date To" value={filters.date_to} onChange={update('date_to')} />
            <div className="flex items-end">
              <button onClick={clearAll} className="btn-secondary text-xs w-full">Reset All</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
