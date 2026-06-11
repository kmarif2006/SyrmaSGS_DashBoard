import { useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSearch, getExportUrl, exportToPDF, truncate } from '../lib'
import { BarChart3, Search, Download, RefreshCw, Moon, ChevronLeft, X, FileText } from 'lucide-react'

export default function NavBar({ filters, onSearchResult }) {
  const [query, setQuery] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [exporting, setExporting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const inputRef = useRef()
  
  const isGrirActive = location.pathname === '/grir'
  const isDashboardActive = location.pathname === '/dashboard'

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => fetchSearch(query),
    enabled: query.length >= 2,
    staleTime: 10000,
  })

  const handleExportPDF = async () => {
    setExporting(true)
    await exportToPDF('dashboard-container')
    setExporting(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') { setQuery(''); setShowResults(false) }
  }

  const exportUrl = getExportUrl(filters || {})

  return (
    <nav className="sticky top-0 z-50 bg-slate-950/90 backdrop-blur-xl border-b border-slate-800/60">
      <div className="max-w-[1600px] mx-auto px-5 h-16 flex items-center gap-4">

        {/* Logo */}
        <button onClick={() => navigate('/')} className="flex items-center gap-2.5 flex-shrink-0 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 group-hover:shadow-indigo-500/50 transition-shadow">
            <BarChart3 size={18} className="text-white" />
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-bold text-white leading-none">Syrma SGS</p>
            <p className="text-[10px] text-slate-500 leading-none mt-0.5">Procurement Analytics</p>
          </div>
        </button>

        {/* Navigation Tabs */}
        {location.pathname !== '/' && (
          <div className="hidden md:flex items-center gap-1.5 ml-4 bg-slate-900/40 p-1 border border-slate-800/40 rounded-xl">
            <button
              onClick={() => navigate('/dashboard')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                isDashboardActive 
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Spend Analytics
            </button>
            <button
              onClick={() => navigate('/grir')}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                isGrirActive 
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              GR/IR Reconciliation
            </button>
          </div>
        )}

        {/* Search box */}
        <div className="flex-1 max-w-xl relative">
          <div className="flex items-center gap-2 bg-slate-800/60 border border-slate-700/50 rounded-xl px-3 py-2 focus-within:border-indigo-500/60 transition-colors">
            <Search size={15} className="text-slate-500 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => { setQuery(e.target.value); setShowResults(true) }}
              onFocus={() => setShowResults(true)}
              onBlur={() => setTimeout(() => setShowResults(false), 200)}
              onKeyDown={handleKeyDown}
              placeholder="Search PO, supplier, material, company..."
              className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
            />
            {query && (
              <button onClick={() => { setQuery(''); setShowResults(false) }}>
                <X size={13} className="text-slate-500 hover:text-slate-300" />
              </button>
            )}
          </div>

          {/* Search results dropdown */}
          {showResults && query.length >= 2 && (
            <div className="absolute top-full mt-2 left-0 right-0 glass-card py-2 shadow-2xl max-h-80 overflow-y-auto z-50">
              {isLoading && <p className="px-4 py-3 text-sm text-slate-500">Searching...</p>}
              {!isLoading && results.length === 0 && <p className="px-4 py-3 text-sm text-slate-500">No results found</p>}
              {results.map((r, i) => (
                <div key={i} className="px-4 py-2.5 hover:bg-slate-700/50 cursor-pointer transition-colors">
                  <div className="flex items-center gap-2">
                    <FileText size={13} className="text-indigo-400 flex-shrink-0" />
                    <span className="text-sm font-medium text-slate-200">{r['Purchasing Document']}</span>
                    <span className="text-xs text-slate-500">•</span>
                    <span className="text-xs text-slate-400 truncate">{truncate(r['Name of Supplier'] || '', 30)}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 ml-5 truncate">{truncate(r['Short Text'] || '', 50)}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={handleExportPDF}
            disabled={exporting}
            className="hidden lg:flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-medium transition-all disabled:opacity-50"
          >
            <RefreshCw size={11} className={exporting ? "animate-spin" : ""} />
            {exporting ? "Generating..." : "Executive PDF"}
          </button>
          
          {!isGrirActive && (
            <a
              href={exportUrl}
              download
              className="hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 text-xs font-medium transition-all"
            >
              <Download size={13} />
              CSV Data
            </a>
          )}
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-400 hover:text-slate-200 text-xs font-medium transition-all"
          >
            <ChevronLeft size={13} />
            Upload
          </button>
        </div>
      </div>
    </nav>
  )
}
