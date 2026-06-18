import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { 
  useGrirSummary, 
  useGrirItems 
} from '../../hooks/useAnalytics'
import { NavBar } from '../../shared'
import { uploadGrirFile, fetchGrirUploadMetadata } from '../../shared'
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, AreaChart, Area
} from 'recharts'
import { 
  DollarSign, 
  CheckCircle2, 
  AlertTriangle, 
  Users, 
  FileText, 
  TrendingUp, 
  Layers, 
  ShieldAlert, 
  Search, 
  ArrowUpDown, 
  ChevronLeft, 
  ChevronRight, 
  Filter, 
  Clock, 
  Info,
  Calendar,
  AlertCircle,
  Activity,
  Package,
  RefreshCw,
  Percent,
  Upload,
  Loader2,
  RotateCcw,
  BarChart3,
  BookOpen,
  FileType
} from 'lucide-react'

// Colors for charts
const STATUS_COLORS = {
  'Reconciled': '#10b981', // Emerald
  'GR Done / IR Pending': '#3b82f6', // Blue
  'IR Done / GR Pending': '#8b5cf6', // Violet
  'Invoice Greater Than GR': '#ef4444', // Red
  'GR Greater Than Invoice': '#f59e0b', // Amber
  'Review Required': '#06b6d4', // Cyan
}

function GrirKPICard({ title, value, sub, icon: Icon, colorClass, isLoading, tooltip, description }) {
  return (
    <div className="glass-card-hover p-6 flex items-start justify-between" title={tooltip}>
      <div className="space-y-2">
        <div className="flex items-center gap-1.5">
          <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">{title}</p>
          {tooltip && <Info size={12} className="text-slate-500 cursor-help" />}
        </div>
        {isLoading ? (
          <div className="h-8 w-24 bg-slate-800 animate-pulse rounded" />
        ) : (
          <p className="text-2xl font-black text-white tracking-tight">{value}</p>
        )}
        <p className="text-xs text-slate-400 font-medium">{sub}</p>
        {description && <p className="text-[10px] text-amber-500/80 font-medium leading-tight max-w-[200px] mt-1">{description}</p>}
      </div>
      <div className={`p-3.5 rounded-2xl border ${colorClass} shrink-0`}>
        <Icon size={24} />
      </div>
    </div>
  )
}

// ── Upload Zone Component ─────────────────────────────────────────────────────
function GrirUploadZone({ onUploadSuccess, onUploadStart }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [metadata, setMetadata] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  // Load existing metadata on mount
  useEffect(() => {
    fetchGrirUploadMetadata()
      .then(d => setMetadata(d))
      .catch(() => {})
  }, [])

  const handleFile = useCallback(async (file) => {
    if (!file) return
    const ext = file.name.split('.').pop().toLowerCase()
    if (!['csv', 'xlsx', 'xls'].includes(ext)) {
      setError('Only CSV, XLS, or XLSX files are accepted.')
      return
    }
    setError(null)
    setUploading(true)
    if (onUploadStart) onUploadStart()
    setProgress(0)
    try {
      const res = await uploadGrirFile(file, p => setProgress(p))
      setMetadata(res.data.metadata)
      onUploadSuccess()
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [onUploadSuccess, onUploadStart])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }, [handleFile])

  const onInputChange = useCallback((e) => {
    handleFile(e.target.files[0])
  }, [handleFile])

  return (
    <div className="glass-card p-5 border border-slate-800/60">
      <div className="flex flex-col lg:flex-row gap-5 items-start lg:items-center">
        {/* Drop Zone */}
        <label
          htmlFor="file-upload"
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex-shrink-0 w-full lg:w-72 flex flex-col items-center justify-center gap-3 p-5 rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
            dragging
              ? 'border-indigo-500 bg-indigo-500/5 scale-[1.01]'
              : uploading
              ? 'border-slate-700 bg-slate-900/40 cursor-wait'
              : 'border-slate-700/50 hover:border-indigo-500/40 hover:bg-indigo-500/3'
          }`}
        >
          <input id="file-upload" ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onInputChange} aria-label="Upload dataset file" />
          <div className={`p-3 rounded-xl border transition-colors ${
            uploading ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400' : 'bg-slate-800 border-slate-700 text-slate-400'
          }`}>
            {uploading ? <Loader2 size={22} className="animate-spin" /> : <Upload size={22} />}
          </div>
          {uploading ? (
            <div className="w-full space-y-1.5">
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 transition-all duration-300" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-[10px] text-center text-indigo-400 font-black uppercase tracking-widest">Processing {progress}% — Running reconciliation engine…</p>
            </div>
          ) : (
            <>
              <p className="text-xs font-bold text-slate-300 text-center">Drop GRIR CSV / XLSX here</p>
              <p className="text-[10px] text-slate-500 text-center">or click to browse · CSV, XLS, XLSX</p>
            </>
          )}
        </label>

        {/* Metadata Panel */}
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <BookOpen size={14} className="text-indigo-400" />
            <p className="text-xs font-black text-slate-400 uppercase tracking-wider">Active Dataset</p>
          </div>
          {metadata ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'File Name', value: metadata.file_name, mono: false },
                { label: 'Records', value: (metadata.record_count || 0).toLocaleString(), mono: true },
                { label: 'PO Count', value: (metadata.po_count || 0).toLocaleString(), mono: true },
                { label: 'Uploaded', value: metadata.upload_date || 'Pre-loaded', mono: false },
              ].map(m => (
                <div key={m.label} className="bg-slate-900/50 border border-slate-800/60 rounded-xl p-3">
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{m.label}</p>
                  <p className={`text-xs font-black text-slate-200 mt-0.5 truncate ${m.mono ? 'font-mono' : ''}`}>{m.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">No dataset loaded. Upload a GRIR file to begin reconciliation analysis.</p>
          )}
          {error && (
            <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded-xl px-3 py-2 mt-2">
              <AlertCircle size={13} />{error}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Skeleton UI Helpers ────────────────────────────────────────────────────────
const SkeletonBlock = ({ className }) => (
  <div className={`animate-pulse bg-slate-800/50 rounded-2xl ${className}`} />
)

// ── Main Dashboard Component ───────────────────────────────────────────────────
export default function GrirDashboard() {
  const queryClient = useQueryClient()
  const { data: summary, isLoading: isSummaryLoading, error: summaryError, refetch: refetchSummary } = useGrirSummary()
  
  const [isUploadingFile, setIsUploadingFile] = useState(false)

  const handleUploadSuccess = useCallback(() => {
    setIsUploadingFile(false)
    // Invalidate GRIR queries so the dashboard auto-refreshes with new data
    queryClient.invalidateQueries({ queryKey: ['grirSummary'] })
    queryClient.invalidateQueries({ queryKey: ['grirItems'] })
  }, [queryClient])

  const showLoading = isSummaryLoading || isUploadingFile;

  // Tab state
  const [activeTab, setActiveTab] = useState('overview')

  // Pagination, search and filters state
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [agingDaysFilter, setAgingDaysFilter] = useState('')
  const [plantFilter, setPlantFilter] = useState('')
  const [sortBy, setSortBy] = useState('open_val')
  const [sortOrder, setSortOrder] = useState('desc')
  const [limit, setLimit] = useState(25)

  // Track expanded rows in main table
  const [expandedRows, setExpandedRows] = useState({})

  const itemsParams = useMemo(() => ({
    page,
    limit,
    search,
    status: statusFilter,
    aging_days: agingDaysFilter,
    plant: plantFilter,
    sortBy,
    sortOrder
  }), [page, limit, search, statusFilter, agingDaysFilter, plantFilter, sortBy, sortOrder])

  const { data: itemsData, isLoading: isItemsLoading } = useGrirItems(itemsParams)

  // Helper for safe toLocaleString
  const safeLocaleString = (val, fallback = '0') => {
    if (val === null || val === undefined) return fallback;
    const num = Number(val);
    if (isNaN(num)) return fallback;
    return num.toLocaleString();
  }

  // Format currency
  const formatINR = (val) => {
    if (val === null || val === undefined) return '₹0';
    const num = Number(val);
    if (isNaN(num)) return '₹0';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(num);
  }

  // Format percentage
  const formatPct = (val) => {
    if (val === null || val === undefined) return '0.0%';
    const num = Number(val);
    if (isNaN(num)) return '0.0%';
    return `${num.toFixed(1)}%`;
  }

  // Handle pagination
  const handlePrevPage = () => {
    if (page > 1) setPage(p => p - 1)
  }

  const handleNextPage = () => {
    if (page < (itemsData?.pages || 1)) setPage(p => p + 1)
  }

  // Handle sorting
  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(order => order === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
    setPage(1)
  }

  // Toggle row expand
  const toggleRow = (rowKey) => {
    setExpandedRows(prev => ({
      ...prev,
      [rowKey]: !prev[rowKey]
    }))
  }

  const resetFilters = () => {
    setSearch('')
    setStatusFilter('')
    setAgingDaysFilter('')
    setPlantFilter('')
    setPage(1)
  }

  // Build chart data
  const statusChartData = useMemo(() => {
    if (!summary?.kpis?.status_distribution) return []
    return Object.entries(summary.kpis.status_distribution).map(([status, count]) => ({
      name: status,
      count: count,
      fill: STATUS_COLORS[status] || '#cbd5e1'
    }))
  }, [summary])

  const topVendorsChartData = useMemo(() => {
    if (!summary?.vendor_insights) return []
    return summary.vendor_insights.slice(0, 10).map(v => ({
      name: v.vendor.length > 15 ? v.vendor.substring(0, 15) + '...' : v.vendor,
      fullName: v.vendor,
      'Open Exposure': v.open_value,
      'Absolute Exposure': Math.abs(v.open_value || 0),
      'Pending Invoice': v.pending_invoice,
      'Over Invoiced': v.over_invoiced,
    }))
  }, [summary])

  const agingChartData = useMemo(() => {
    if (!summary?.aging_analysis) return []
    return summary.aging_analysis.map(item => ({
      name: item.aging_bucket || (item.bucket + ' days'),
      'GR Done / IR Pending': item.gr_done_ir_pending_val || 0,
      'IR Done / GR Pending': item.ir_done_gr_pending_val || 0,
      'Invoice Greater Than GR': item.inv_greater_gr_val || 0,
      'GR Greater Than Invoice': item.gr_greater_inv_val || 0,
      'Review Required': item.review_required_val || 0,
    }))
  }, [summary])

  // Sub-Section Tab Renderers
  const renderOverview = () => {
    return (
      <div className="space-y-10 animate-fadeIn">
        {/* KPIs Section — 8 cards */}
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <GrirKPICard
            title="Reconciliation Rate"
            value={summary?.kpis ? formatPct(summary.kpis.reconciliation_rate) : '--'}
            sub={`${summary?.kpis ? safeLocaleString(summary.kpis.reconciled_count) : '--'} / ${summary?.kpis ? safeLocaleString(summary.kpis.total_po_items) : '--'} PO lines`}
            icon={CheckCircle2}
            colorClass="text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Total Open Exposure"
            value={summary?.kpis ? formatINR(summary.kpis.total_open_value) : '--'}
            sub="Net GR minus IR value"
            icon={DollarSign}
            colorClass="text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Total GR Value"
            value={summary?.kpis ? formatINR(summary.kpis.total_gr_value) : '--'}
            sub="Cumulative goods receipt value"
            icon={BarChart3}
            colorClass="text-blue-400 bg-blue-500/10 border-blue-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Total IR Value"
            value={summary?.kpis ? formatINR(summary.kpis.total_ir_value) : '--'}
            sub="Cumulative invoice receipt value"
            icon={FileText}
            colorClass="text-violet-400 bg-violet-500/10 border-violet-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Actionable Exceptions"
            value={summary?.kpis ? `${safeLocaleString(summary.kpis.actionable_exceptions_count)} Items` : '--'}
            sub={summary?.kpis ? `${formatINR(summary.kpis.actionable_exceptions_val)} Total Exposure` : 'Immediate escalation required'}
            icon={AlertTriangle}
            colorClass="text-amber-400 bg-amber-500/10 border-amber-500/20"
            isLoading={showLoading}
            description="> 90 Days Old OR Over-Invoiced"
          />
          <GrirKPICard
            title="Open PO Count"
            value={summary?.kpis ? safeLocaleString(summary.kpis.unique_pos) : '--'}
            sub="Unique POs with open items"
            icon={BookOpen}
            colorClass="text-cyan-400 bg-cyan-500/10 border-cyan-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Reversal Count (Val)"
            value={summary?.kpis ? formatINR(summary.kpis.total_reversals_val) : '--'}
            sub="Total reversed IR value"
            icon={RotateCcw}
            colorClass="text-rose-400 bg-rose-500/10 border-rose-500/20"
            isLoading={showLoading}
          />
          <GrirKPICard
            title="Active Vendors"
            value={summary?.kpis ? safeLocaleString(summary.kpis.unique_vendors) : '--'}
            sub="With open GR/IR balances"
            icon={Users}
            colorClass="text-amber-400 bg-amber-500/10 border-amber-500/20"
            isLoading={showLoading}
          />
        </div>

        {/* Executive Summary Narrative */}
        {showLoading ? (
          <div className="glass-card p-6 bg-slate-900/40 border-indigo-500/10 mb-6 flex flex-col lg:flex-row gap-6">
            <div className="flex-1 space-y-4">
              <SkeletonBlock className="h-5 w-48" />
              <SkeletonBlock className="h-8 w-3/4" />
              <div className="space-y-2 mt-4">
                <SkeletonBlock className="h-4 w-full" />
                <SkeletonBlock className="h-4 w-5/6" />
                <SkeletonBlock className="h-4 w-4/6" />
              </div>
            </div>
            <div className="w-full lg:w-96 flex-shrink-0 bg-slate-950/60 border border-slate-800/80 rounded-2xl p-4 space-y-3">
              <SkeletonBlock className="h-4 w-40 mb-4" />
              <SkeletonBlock className="h-4 w-full" />
              <SkeletonBlock className="h-4 w-full" />
              <SkeletonBlock className="h-4 w-4/5" />
            </div>
          </div>
        ) : summary?.executive_summary && (
          <div className="glass-card p-6 bg-slate-900/40 relative overflow-hidden border-indigo-500/10 mb-6">
            <div className="absolute top-0 right-0 w-[40%] h-[150%] bg-indigo-500/5 blur-[100px] pointer-events-none rounded-full" />
            <div className="flex flex-col lg:flex-row gap-6 items-start justify-between relative z-10">
              <div className="space-y-3 flex-1">
                <div className="flex items-center gap-2 text-indigo-400 text-sm font-bold uppercase tracking-wider">
                  <Activity size={16} />
                  Executive Audit Synthesis
                </div>
                <h3 className="text-lg font-bold text-white leading-snug">
                  {summary.executive_summary.headline}
                </h3>
                <p className="text-slate-400 text-sm leading-relaxed max-w-5xl">
                  {summary.executive_summary.detail}
                </p>
              </div>

              {summary.executive_summary.risk_flags?.length > 0 && (
                <div className="w-full lg:w-96 flex-shrink-0 bg-slate-950/60 border border-slate-800/80 rounded-2xl p-4 space-y-3">
                  <p className="text-xs text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                    <AlertTriangle size={14} /> Actionable Exception Flags
                  </p>
                  <ul className="space-y-2 text-xs text-slate-300">
                    {summary.executive_summary.risk_flags.map((flag, idx) => (
                      <li key={idx} className="flex gap-2 items-start">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1 flex-shrink-0" />
                        <span className="leading-normal">{flag}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Charts & Analytical Details */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          
          {/* Match Rate Over Time */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 flex flex-col w-full h-[350px]">
            <div className="mb-4">
              <h3 className="text-sm font-bold text-slate-100 mb-1">Reconciliation Accuracy Trend</h3>
              <p className="text-[10px] text-slate-500 font-bold tracking-wide uppercase">Match rate percentage by posting month</p>
            </div>
            <div className="w-full flex-1">
              {showLoading ? (
                <SkeletonBlock className="w-full h-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={summary?.time_series_analytics?.match_rate || []} margin={{ top: 15, right: 10, left: -20, bottom: 5 }}>
                    <XAxis dataKey="month" stroke="#475569" className="text-[10px]" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis stroke="#475569" className="text-[10px]" tick={{ fontSize: 10 }} tickFormatter={(val) => `${val}%`} domain={[0, 100]} axisLine={false} tickLine={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                      labelClassName="text-slate-100 font-bold text-xs mb-2"
                      itemClassName="text-xs font-mono"
                      formatter={(value) => [`${value}%`, 'Match Rate']}
                    />
                    <Line type="monotone" dataKey="match_rate_pct" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: '#10b981', strokeWidth: 0 }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Cumulative GR vs IR Trend */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 flex flex-col w-full h-[350px]">
            <div className="mb-4">
              <h3 className="text-sm font-bold text-slate-100 mb-1">Cumulative Ledger Value Trend</h3>
              <p className="text-[10px] text-slate-500 font-bold tracking-wide uppercase">Total GR vs IR volume over time (INR)</p>
            </div>
            <div className="w-full flex-1">
              {showLoading ? (
                <SkeletonBlock className="w-full h-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={summary?.time_series_analytics?.trend || []} margin={{ top: 15, right: 10, left: 10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="colorGr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorIr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="month" stroke="#475569" className="text-[10px]" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis stroke="#475569" className="text-[10px]" tick={{ fontSize: 10 }} tickFormatter={(val) => `₹${(val/10000000).toFixed(0)}Cr`} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                    labelClassName="text-slate-100 font-bold text-xs mb-2"
                    itemClassName="text-xs font-mono"
                    formatter={(value) => formatINR(value)}
                  />
                  <Area type="monotone" dataKey="cumulative_gr" stroke="#06b6d4" strokeWidth={2} fillOpacity={1} fill="url(#colorGr)" name="Total GR" />
                  <Area type="monotone" dataKey="cumulative_ir" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorIr)" name="Total IR" />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '10px', paddingTop: '10px' }} iconType="circle" />
                </AreaChart>
              </ResponsiveContainer>
              )}
            </div>
          </div>

        </div>
        
        {/* Status Distribution */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6 flex flex-col w-full mb-6">
          <div className="mb-6 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-bold text-slate-100 mb-1">GR/IR Status Profile</h3>
              <p className="text-[10px] text-slate-500 font-bold tracking-wide uppercase">Volume distribution of all PO lines</p>
            </div>
            <span className="bg-slate-800 text-slate-400 font-semibold text-[10px] border border-slate-700 px-2 py-1 rounded-full">6 Categories</span>
          </div>
          <div className="w-full h-[300px]">
            {showLoading ? (
              <SkeletonBlock className="w-full h-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusChartData} layout="vertical" margin={{ left: 50, right: 20 }}>
                  <XAxis type="number" stroke="#475569" className="text-xs" axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" stroke="#475569" className="text-[10px]" width={120} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                    labelClassName="text-slate-100 font-bold text-xs"
                    itemClassName="text-xs text-slate-300"
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {statusChartData.map((entry, idx) => (
                      <Cell key={`cell-${idx}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Financial Impact & Action Recommendations */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Financial Impact Ledger */}
          <div className="glass-card p-6 flex flex-col">
            <div className="mb-6 flex items-center gap-3">
              <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
                <Layers size={18} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100 mb-0.5">Balance Sheet & Control Impact</h3>
                <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Financial severity mapping</p>
              </div>
            </div>
            
            <div className="flex-1 space-y-4">
              {showLoading ? (
                [1, 2, 3].map(i => (
                  <div key={i} className="flex justify-between items-center py-2">
                    <SkeletonBlock className="h-4 w-32" />
                    <SkeletonBlock className="h-4 w-24" />
                  </div>
                ))
              ) : (
                summary?.financial_impact?.map((impact, idx) => (
                  <div key={idx} className="p-4 bg-slate-900/35 border border-slate-850 rounded-2xl flex flex-col sm:flex-row gap-4 justify-between items-start">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-black tracking-widest px-2 py-0.5 rounded-full uppercase ${
                          impact.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                        }`}>
                          {impact.severity}
                        </span>
                        <h4 className="text-sm font-bold text-white">{impact.area}</h4>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">{impact.description}</p>
                      <p className="text-[11px] text-slate-500 font-medium"><strong className="text-slate-400">Resolution Action:</strong> {impact.action}</p>
                    </div>
                    
                    <div className="text-left sm:text-right flex-shrink-0">
                      <p className="text-[10px] text-slate-500 uppercase font-black tracking-wider">Estimated Impact</p>
                      <p className="text-base font-black text-indigo-400 mt-0.5">{formatINR(impact.impact_val)}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5 font-bold">₹{impact.impact_cr.toFixed(2)} Cr</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Action Priorities */}
          <div className="glass-card p-6 flex flex-col">
            <div className="mb-6 flex items-center gap-3">
              <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <CheckCircle2 size={18} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100 mb-0.5">Recommended Actions</h3>
                <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Procurement follow-up & corrections checklist</p>
              </div>
            </div>

            <div className="flex-1 space-y-4 max-h-[480px] overflow-y-auto pr-1">
              {showLoading ? (
                [1, 2, 3].map(i => (
                  <div key={i} className="flex gap-3">
                    <SkeletonBlock className="h-4 w-4 mt-1 rounded-full flex-shrink-0" />
                    <div className="space-y-2 flex-1">
                      <SkeletonBlock className="h-4 w-full" />
                      <SkeletonBlock className="h-3 w-5/6" />
                    </div>
                  </div>
                ))
              ) : (
                summary?.recommended_actions?.map((act, idx) => (
                  <div key={idx} className="p-4 bg-slate-900/35 border border-slate-850 rounded-2xl space-y-3">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-black tracking-widest px-2 py-0.5 rounded-full uppercase ${
                          act.priority === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 
                          act.priority === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                        }`}>
                          {act.priority} PRIORITY
                        </span>
                        <span className="text-xs text-slate-400 font-bold">• {act.category}</span>
                      </div>
                      <span className="text-[10px] text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded font-bold">{act.timeline}</span>
                    </div>

                    <p className="text-xs font-semibold text-slate-200 leading-normal">{act.action}</p>
                    
                    <div className="flex justify-between items-center pt-2 border-t border-slate-800/40 text-[10px] text-slate-500">
                      <p>Owner: <strong className="text-slate-400">{act.owner}</strong></p>
                      <p>Impact: <strong className="text-slate-400">{act.impact}</strong></p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Major Exceptions Drawer List */}
        {(summary?.top_exceptions?.length > 0 || showLoading) && (
          <div className="glass-card p-6">
            <div className="mb-6 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                  <ShieldAlert size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 30 Critical Audit Anomalies</h3>
                  <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Ranked by variance and open value severity</p>
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider">
                    <th className="pb-3 pr-4">PO Document</th>
                    <th className="pb-3 px-4">Vendor</th>
                    <th className="pb-3 px-4">Material Text</th>
                    <th className="pb-3 px-4 text-center">Status</th>
                    <th className="pb-3 px-4 text-right">Open Value</th>
                    <th className="pb-3 pl-4">Audit Exception Narrative</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {showLoading ? (
                    [1, 2, 3, 4, 5].map(i => (
                      <tr key={i}>
                        <td className="py-3.5 pr-4"><SkeletonBlock className="h-4 w-24" /></td>
                        <td className="py-3.5 px-4"><SkeletonBlock className="h-4 w-32" /></td>
                        <td className="py-3.5 px-4"><SkeletonBlock className="h-4 w-40" /></td>
                        <td className="py-3.5 px-4"><SkeletonBlock className="h-5 w-20 mx-auto" /></td>
                        <td className="py-3.5 px-4"><SkeletonBlock className="h-4 w-24 ml-auto" /></td>
                        <td className="py-3.5 pl-4"><SkeletonBlock className="h-4 w-full" /></td>
                      </tr>
                    ))
                  ) : (
                    summary?.top_exceptions?.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                        <td className="py-3.5 pr-4 font-mono font-bold text-slate-200">
                          {item.po_number} / {item.po_item}
                        </td>
                        <td className="py-3.5 px-4 text-slate-300 max-w-[150px] truncate">{item.vendor}</td>
                        <td className="py-3.5 px-4 text-slate-400 max-w-[180px] truncate">{item.material}</td>
                        <td className="py-3.5 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded font-black tracking-widest text-[9px] uppercase border ${
                            item.status === 'GR Done / IR Pending' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                            item.status === 'IR Done / GR Pending' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                            item.status === 'Invoice Greater Than GR' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                            item.status === 'GR Greater Than Invoice' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                          }`}>
                            {item.status}
                          </span>
                        </td>
                        <td className={`py-3.5 px-4 text-right font-bold font-mono ${item.open_val < 0 ? 'text-red-400' : 'text-slate-300'}`}>
                          {formatINR(item.open_val)}
                        </td>
                        <td className="py-3.5 pl-4 text-slate-400 leading-normal italic text-[11px] max-w-[320px]">
                          {item.explanation}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderVendors = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <SkeletonBlock className="h-32 w-full" />
            <SkeletonBlock className="h-32 w-full" />
            <SkeletonBlock className="h-32 w-full" />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <SkeletonBlock className="h-[350px] w-full xl:col-span-1" />
            <SkeletonBlock className="h-[350px] w-full xl:col-span-2" />
          </div>
        </div>
      )
    }
    const vendors = summary?.vendor_insights || []

    return (
      <div className="space-y-6 animate-fadeIn">
        {/* Vendor Header Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="glass-card p-5 space-y-1">
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Top Exposed Vendor</p>
            <p className="text-lg font-black text-white truncate">{vendors[0]?.vendor || 'N/A'}</p>
            <p className="text-xs text-indigo-400 font-bold">Exposure: {formatINR(vendors[0]?.open_value)} ({vendors[0]?.open_pct_total}%)</p>
          </div>
          <div className="glass-card p-5 space-y-1">
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Highest Reversal Vendor</p>
            {(() => {
              const maxRev = [...vendors].sort((a, b) => b.avg_reversal_pct - a.avg_reversal_pct)[0]
              return (
                <>
                  <p className="text-lg font-black text-white truncate">{maxRev?.vendor || 'N/A'}</p>
                  <p className="text-xs text-amber-400 font-bold">Avg Reversal: {formatPct(maxRev?.avg_reversal_pct)}</p>
                </>
              )
            })()}
          </div>
          <div className="glass-card p-5 space-y-1">
            <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Total Active Vendors</p>
            <p className="text-2xl font-black text-white">{safeLocaleString(summary?.kpis?.unique_vendors)}</p>
            <p className="text-xs text-slate-400 font-medium">With open SAP GR/IR balances</p>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Top 10 chart */}
          <div className="glass-card p-6 xl:col-span-1 flex flex-col">
            <div className="mb-4">
              <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 10 Vendors by Open Exposure</h3>
              <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Net unreconciled values</p>
            </div>
            <div className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topVendorsChartData} layout="vertical" margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
                  <XAxis type="number" stroke="#475569" className="text-[10px]" tickFormatter={(val) => `₹${(val/1e5).toFixed(0)}L`} />
                  <YAxis type="category" dataKey="name" stroke="#475569" className="text-[10px]" width={80} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }}
                    labelClassName="text-slate-100 font-bold text-xs"
                    itemClassName="text-xs text-slate-300"
                    formatter={(val, name, props) => [formatINR(props.payload['Open Exposure'] || 0), 'Exposure']}
                  />
                  <Bar dataKey="Absolute Exposure" radius={[0, 4, 4, 0]} fill="#6366f1" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Supplier Grid */}
          <div className="glass-card p-6 xl:col-span-2">
            <div className="mb-4">
              <h3 className="text-base font-bold text-slate-100 mb-0.5">Vendor Performance & Exposure Leaderboard</h3>
              <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Ranked by absolute open balance value</p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider">
                    <th className="pb-3 pr-4">Vendor</th>
                    <th className="pb-3 px-4 text-center">POs / Items</th>
                    <th className="pb-3 px-4 text-right">GR Value</th>
                    <th className="pb-3 px-4 text-right">IR Value</th>
                    <th className="pb-3 px-4 text-right">Open Value</th>
                    <th className="pb-3 px-4 text-center">Status</th>
                    <th className="pb-3 pl-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50 text-slate-300">
                  {vendors.map((v, idx) => {
                    const isExpanded = !!expandedRows[`vendor-${idx}`]
                    return (
                      <>
                        <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                          <td className="py-3 pr-4 font-bold text-slate-200 truncate max-w-[150px]" title={v.vendor}>
                            {v.vendor}
                          </td>
                          <td className="py-3 px-4 text-center font-mono">{v.po_count} / {v.item_count}</td>
                          <td className="py-3 px-4 text-right font-mono text-slate-400">{formatINR(v.gr_value)}</td>
                          <td className="py-3 px-4 text-right font-mono text-slate-400">{formatINR(v.ir_value)}</td>
                          <td className={`py-3 px-4 text-right font-mono font-bold ${v.open_value < -1 ? 'text-red-400' : 'text-emerald-400'}`}>
                            {formatINR(v.open_value)}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                              v.dominant_status === 'Reconciled' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                              v.dominant_status === 'GR Done / IR Pending' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                              v.dominant_status === 'IR Done / GR Pending' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                              v.dominant_status === 'Invoice Greater Than GR' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              v.dominant_status === 'GR Greater Than Invoice' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                            }`}>
                              {v.dominant_status}
                            </span>
                          </td>
                          <td className="py-3 pl-4 text-right">
                            <button 
                              onClick={() => toggleRow(`vendor-${idx}`)}
                              className="text-xs text-indigo-400 hover:text-indigo-300 font-bold transition-colors"
                            >
                              {isExpanded ? 'Hide Details' : 'View Drilldown'}
                            </button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-slate-900/20">
                            <td colSpan={8} className="p-4 border-l-2 border-indigo-500">
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                                <div className="p-3 bg-slate-950/60 border border-slate-900 rounded-lg">
                                  <p className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">Open Exposure %</p>
                                  <p className="text-sm font-black text-white mt-1">{v.open_pct_total}% of Total</p>
                                </div>
                                <div className="p-3 bg-slate-950/60 border border-slate-900 rounded-lg">
                                  <p className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">Pending Invoices</p>
                                  <p className="text-sm font-black text-indigo-400 mt-1">{formatINR(v.pending_invoice)}</p>
                                </div>
                                <div className="p-3 bg-slate-950/60 border border-slate-900 rounded-lg">
                                  <p className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">Over-Invoiced Value</p>
                                  <p className="text-sm font-black text-rose-400 mt-1">{formatINR(v.over_invoiced)}</p>
                                </div>
                                <div className="p-3 bg-slate-950/60 border border-slate-900 rounded-lg">
                                  <p className="text-slate-500 font-bold uppercase tracking-wider text-[10px]">Avg Days Outstanding</p>
                                  <p className="text-sm font-black text-amber-400 mt-1">{v.avg_days_open} Days</p>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderMaterials = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <SkeletonBlock className="h-[500px] w-full" />
        </div>
      )
    }
    const materials = summary?.material_insights || []

    return (
      <div className="space-y-6 animate-fadeIn">
        <div className="glass-card p-6">
          <div className="mb-4">
            <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 25 Materials Pending Invoice / Receipt</h3>
            <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Ranked by absolute open reconciliation exposure</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider">
                  <th className="pb-3 pr-4">Material / Short Text</th>
                  <th className="pb-3 px-4 text-center">PO Items</th>
                  <th className="pb-3 px-4 text-right">Net GR Value</th>
                  <th className="pb-3 px-4 text-right">Net IR Value</th>
                  <th className="pb-3 px-4 text-right">Open Exposure Value</th>
                  <th className="pb-3 pl-4">Status Anomalies Distribution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300">
                {materials.map((m, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                    <td className="py-3.5 pr-4 font-bold text-slate-200 truncate max-w-[250px]" title={m.material}>
                      {m.material}
                    </td>
                    <td className="py-3.5 px-4 text-center font-mono">{m.item_count}</td>
                    <td className="py-3.5 px-4 text-right font-mono text-slate-400">{formatINR(m.gr_value)}</td>
                    <td className="py-3.5 px-4 text-right font-mono text-slate-400">{formatINR(m.ir_value)}</td>
                    <td className={`py-3.5 px-4 text-right font-mono font-bold ${m.open_value < -1 ? 'text-red-400' : 'text-emerald-400'}`}>
                      {formatINR(m.open_value)}
                    </td>
                    <td className="py-3.5 pl-4">
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(m.status_dist || {})
                          .filter(([_, count]) => count > 0)
                          .map(([status, count]) => (
                            <span 
                              key={status} 
                              className={`px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                                status === 'Reconciled' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                                status === 'GR Done / IR Pending' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                                status === 'IR Done / GR Pending' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                                status === 'Invoice Greater Than GR' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                status === 'GR Greater Than Invoice' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                              }`}
                            >
                              {status}: {count}
                            </span>
                          ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  const renderAging = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <SkeletonBlock className="h-[400px] w-full xl:col-span-2" />
            <SkeletonBlock className="h-[400px] w-full xl:col-span-1" />
          </div>
        </div>
      )
    }
    const agingData = summary?.aging_analysis || []

    return (
      <div className="space-y-6 animate-fadeIn">
        {/* Aging KPI Cards Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {agingData.map((item, idx) => (
            <div key={idx} className="glass-card p-4 space-y-1.5 flex flex-col justify-between">
              <div className="space-y-0.5">
                <span className="text-[10px] text-slate-500 font-black tracking-widest uppercase">Bucket</span>
                <p className="text-base font-black text-white">{item.aging_bucket || item.bucket} Days</p>
              </div>
              <div>
                <p className="text-sm font-extrabold text-indigo-400">{formatINR(item.total_exposure_inr || item.open_value)}</p>
                <p className="text-[10px] text-slate-400">{item.unreconciled_items || item.open_count} open items</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Aging Stacked Bar Chart */}
          <div className="glass-card p-6 xl:col-span-2 flex flex-col">
            <div className="mb-4">
              <h3 className="text-base font-bold text-slate-100 mb-0.5">Aging Discrepancy Stacked Composition</h3>
              <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Unreconciled value by posting age and category</p>
            </div>
            <div className="flex-1 min-h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agingChartData} margin={{ left: 10, right: 10, top: 10, bottom: 10 }}>
                  <XAxis dataKey="name" stroke="#475569" className="text-[10px]" />
                  <YAxis stroke="#475569" className="text-[10px]" tickFormatter={(val) => `₹${(val/1e5).toFixed(0)}L`} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }}
                    labelClassName="text-slate-100 font-bold text-xs"
                    itemClassName="text-xs text-slate-300"
                    formatter={(val) => [formatINR(val)]}
                  />
                  <Legend wrapperStyle={{ fontSize: '10px', paddingTop: '10px' }} />
                  <Bar dataKey="GR Done / IR Pending" stackId="a" fill="#3b82f6" />
                  <Bar dataKey="IR Done / GR Pending" stackId="a" fill="#8b5cf6" />
                  <Bar dataKey="Invoice Greater Than GR" stackId="a" fill="#ef4444" />
                  <Bar dataKey="GR Greater Than Invoice" stackId="a" fill="#f59e0b" />
                  <Bar dataKey="Review Required" stackId="a" fill="#64748b" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Aging Table Summary */}
          <div className="glass-card p-6 flex flex-col justify-between">
            <div>
              <div className="mb-4">
                <h3 className="text-base font-bold text-slate-100 mb-0.5">Aging Account Summary</h3>
                <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Reconciliation aging matrices</p>
              </div>

              <div className="space-y-3.5">
                {agingData.map((item, idx) => (
                  <div key={idx} className="p-3 bg-slate-900/40 border border-slate-800/60 rounded-xl space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <strong className="text-slate-200 font-black">{item.aging_bucket || item.bucket} Days</strong>
                      <span className="text-slate-400 font-mono font-bold">{item.unreconciled_items || item.open_count} / {item.total_items || item.total_count} open</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Open Value</span>
                      <span className="font-mono font-black text-indigo-400">{formatINR(item.total_exposure_inr || item.open_value)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderReversals = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <SkeletonBlock className="h-28 w-full" />
          </div>
          <SkeletonBlock className="h-[500px] w-full" />
        </div>
      )
    }
    const reversals = summary?.reversal_analysis || []

    return (
      <div className="space-y-6 animate-fadeIn">
        {/* KPI card info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="glass-card p-5 space-y-1 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Total Reversals Posted Value</p>
              <p className="text-2xl font-black text-white mt-1">
                {summary?.kpis ? formatINR(summary.kpis.total_reversals_val) : '--'}
              </p>
              <p className="text-xs text-slate-400 font-medium">Reversed Invoice Receipt (IR) transactions value</p>
            </div>
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl">
              <RefreshCw size={20} />
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="mb-4">
            <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 25 Post-Posting Reversal Exceptions</h3>
            <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Ranked by reversal percentage and corrected value magnitude</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider">
                  <th className="pb-3 pr-4">PO Doc / Item</th>
                  <th className="pb-3 px-4">Vendor</th>
                  <th className="pb-3 px-4">Material Name</th>
                  <th className="pb-3 px-4 text-center">Net GR Qty</th>
                  <th className="pb-3 px-4 text-center">Net IR Qty</th>
                  <th className="pb-3 px-4 text-center">GR Rev Qty</th>
                  <th className="pb-3 px-4 text-center">IR Rev Qty</th>
                  <th className="pb-3 px-4 text-right">Reversal Value</th>
                  <th className="pb-3 px-4 text-center">Reversal %</th>
                  <th className="pb-3 px-4 text-right">Open Value</th>
                  <th className="pb-3 pl-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300 font-medium">
                {reversals.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-8 text-center text-slate-500 font-bold">No active reversal records detected.</td>
                  </tr>
                ) : (
                  reversals.map((r, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                      <td className="py-3.5 pr-4 font-mono font-bold text-slate-200">
                        {r.po_number} / {r.po_item}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 truncate max-w-[120px]" title={r.vendor}>{r.vendor}</td>
                      <td className="py-3.5 px-4 text-slate-400 truncate max-w-[150px]" title={r.material}>{r.material}</td>
                      <td className="py-3.5 px-4 text-center font-mono">{r.gr_qty}</td>
                      <td className="py-3.5 px-4 text-center font-mono">{r.ir_qty}</td>
                      <td className={`py-3.5 px-4 text-center font-mono font-bold ${r.gr_reversal_qty > 0 ? 'text-amber-400' : 'text-slate-500'}`}>{r.gr_reversal_qty}</td>
                      <td className={`py-3.5 px-4 text-center font-mono font-bold ${r.ir_reversal_qty > 0 ? 'text-amber-400' : 'text-slate-500'}`}>{r.ir_reversal_qty}</td>
                      <td className={`py-3.5 px-4 text-right font-mono font-bold ${r.reversal_val > 0 ? 'text-amber-400' : 'text-slate-400'}`}>{formatINR(r.reversal_val)}</td>
                      <td className="py-3.5 px-4 text-center">
                        <span className="px-2 py-0.5 rounded text-[10px] font-black font-mono bg-red-500/10 text-red-400 border border-red-500/20">
                          {formatPct(r.reversal_pct)}
                        </span>
                      </td>
                      <td className={`py-3.5 px-4 text-right font-mono font-bold ${r.open_val < -1 ? 'text-red-400' : 'text-slate-300'}`}>
                        {formatINR(r.open_val)}
                      </td>
                      <td className="py-3.5 pl-4 text-center">
                        <span className="px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border bg-slate-800 text-slate-400 border-slate-700">
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  const renderPriceVariance = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <SkeletonBlock className="h-28 w-full" />
            <SkeletonBlock className="h-28 w-full" />
          </div>
          <SkeletonBlock className="h-[500px] w-full" />
        </div>
      )
    }
    const variances = summary?.price_variance_analysis || []

    return (
      <div className="space-y-6 animate-fadeIn">
        {/* KPI header details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="glass-card p-5 space-y-1 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Price Variance Exceptions</p>
              <p className="text-2xl font-black text-white mt-1">
                {variances.length} Items
              </p>
              <p className="text-xs text-slate-400 font-medium">Items with variance exceeding ±5% baseline tolerance</p>
            </div>
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-xl">
              <Percent size={20} />
            </div>
          </div>
          <div className="glass-card p-5 space-y-1 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Purchase Price Compliance</p>
              <p className="text-sm font-bold text-slate-300 mt-1">
                Variance occurs when invoice unit prices deviate from authorized SAP Purchase Order prices.
              </p>
            </div>
            <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-xl">
              <TrendingUp size={20} />
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <div className="mb-4">
            <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 25 Unit Price Variance Audit Mismatches</h3>
            <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Reconciled line items with significant unit price inflation or deflation</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider">
                  <th className="pb-3 pr-4">PO Doc / Item</th>
                  <th className="pb-3 px-4">Vendor</th>
                  <th className="pb-3 px-4">Material Text</th>
                  <th className="pb-3 px-4 text-right">PO Unit Price</th>
                  <th className="pb-3 px-4 text-right">Net GR Value</th>
                  <th className="pb-3 px-4 text-right">Net IR Value</th>
                  <th className="pb-3 px-4 text-center">Variance %</th>
                  <th className="pb-3 px-4 text-right">Variance Absolute</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300 font-medium">
                {variances.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-500 font-bold">No compliance price variances detected.</td>
                  </tr>
                ) : (
                  variances.map((v, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                      <td className="py-3.5 pr-4 font-mono font-bold text-slate-200">
                        {v.po_number} / {v.po_item}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 truncate max-w-[120px]" title={v.vendor}>{v.vendor}</td>
                      <td className="py-3.5 px-4 text-slate-400 truncate max-w-[150px]" title={v.material}>{v.material}</td>
                      <td className="py-3.5 px-4 text-right font-mono text-slate-400">{formatINR(v.po_price)}</td>
                      <td className="py-3.5 px-4 text-right font-mono text-slate-400">{formatINR(v.gr_value)}</td>
                      <td className="py-3.5 px-4 text-right font-mono text-slate-400">{formatINR(v.ir_value)}</td>
                      <td className="py-3.5 px-4 text-center font-mono">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black ${
                          v.variance_pct > 0 ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}>
                          {v.variance_pct > 0 ? '+' : ''}{v.variance_pct}%
                        </span>
                      </td>
                      <td className={`py-3.5 px-4 text-right font-mono font-bold ${v.variance_abs > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                        {formatINR(v.variance_abs)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  const renderLedgerExplorer = () => {
    return (
      <section className="glass-card p-6 space-y-6 animate-fadeIn">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers size={18} className="text-indigo-400" />
              Ledger Investigation Center
            </h3>
            <p className="text-xs text-slate-500 font-bold uppercase mt-0.5">Filter, search, and drill down on all {summary?.kpis ? safeLocaleString(summary.kpis.total_po_items) : '0'} PO lines</p>
          </div>
          
          <button 
            onClick={resetFilters}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors underline flex items-center gap-1"
          >
            Reset All Filters
          </button>
        </div>

        {/* Interactive Filters Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 bg-slate-900/30 border border-slate-900 p-4 rounded-2xl">
          {/* Text Search */}
          <div className="flex items-center gap-2.5 bg-slate-950/80 border border-slate-850 px-3 py-2 rounded-xl focus-within:border-indigo-500/50 transition-colors">
            <Search size={14} className="text-slate-500" />
            <input 
              type="text" 
              name="search"
              autoComplete="off"
              aria-label="Search PO, Vendor, or Material"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              placeholder="Search PO / Vendor / Material..."
              className="bg-transparent text-xs text-slate-200 placeholder-slate-500 outline-none w-full"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-850 px-3 py-2 rounded-xl">
            <Filter size={14} className="text-slate-500" />
            <select 
              value={statusFilter} 
              onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="bg-transparent text-xs text-slate-300 outline-none w-full border-none cursor-pointer"
            >
              <option value="" className="bg-slate-900">All Statuses</option>
              <option value="Reconciled" className="bg-slate-900">Reconciled</option>
              <option value="GR Done / IR Pending" className="bg-slate-900">GR Done / IR Pending</option>
              <option value="IR Done / GR Pending" className="bg-slate-900">IR Done / GR Pending</option>
              <option value="Invoice Greater Than GR" className="bg-slate-900">Invoice Greater Than GR</option>
              <option value="GR Greater Than Invoice" className="bg-slate-900">GR Greater Than Invoice</option>
              <option value="Review Required" className="bg-slate-900">Review Required</option>
            </select>
          </div>

          {/* Aging Days Filter */}
          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-850 px-3 py-2 rounded-xl">
            <Clock size={14} className="text-slate-500" />
            <select 
              value={agingDaysFilter} 
              onChange={e => { setAgingDaysFilter(e.target.value); setPage(1) }}
              className="bg-transparent text-xs text-slate-300 outline-none w-full border-none cursor-pointer"
            >
              <option value="" className="bg-slate-900">All Aging Days</option>
              <option value="<30" className="bg-slate-900">{'< 30 Days'}</option>
              <option value="30-60" className="bg-slate-900">30 - 60 Days</option>
              <option value="60-90" className="bg-slate-900">60 - 90 Days</option>
              <option value=">90" className="bg-slate-900">{'> 90 Days'}</option>
            </select>
          </div>

          {/* Plant Filter */}
          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-850 px-3 py-2 rounded-xl">
            <Layers size={14} className="text-slate-500" />
            <select 
              value={plantFilter} 
              onChange={e => { setPlantFilter(e.target.value); setPage(1) }}
              className="bg-transparent text-xs text-slate-300 outline-none w-full border-none cursor-pointer"
            >
              <option value="" className="bg-slate-900">All Plants</option>
              {summary?.plant_insights?.map((p) => (
                <option key={p.plant} value={p.plant} className="bg-slate-900">Plant {p.plant}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Interactive Paginated Items Grid */}
        <div className="relative border border-slate-900 rounded-2xl overflow-hidden bg-slate-900/10">
          {isItemsLoading && (
            <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px] flex items-center justify-center z-10">
              <div className="h-10 w-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
            </div>
          )}

          <div className="overflow-x-auto min-h-[400px]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-bold uppercase tracking-wider bg-slate-900/50">
                  <th className="py-4 pl-6 pr-4 cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('PO Number')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('PO Number'); } }}>
                    <div className="flex items-center gap-1.5">
                      PO Doc / Item <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('Vendor')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('Vendor'); } }}>
                    <div className="flex items-center gap-1.5">
                      Vendor <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('Short Text')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('Short Text'); } }}>
                    <div className="flex items-center gap-1.5">
                      Short Text <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('Plant')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('Plant'); } }}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Plant <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('net_gr_val')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('net_gr_val'); } }}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Net GR <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('net_ir_val')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('net_ir_val'); } }}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Net IR <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('open_val')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('open_val'); } }}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Open Value <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('status')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('status'); } }}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Status <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200 focus-visible:outline-indigo-500" tabIndex={0} onClick={() => handleSort('open_aging_days')} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort('open_aging_days'); } }}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Open Aging Days <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 pr-6 pl-4 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900 font-medium text-slate-300">
                {itemsData?.items?.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-12 text-center text-slate-500 font-bold">
                      No records match the active search and filters.
                    </td>
                  </tr>
                ) : (
                  itemsData?.items?.map((item, index) => {
                    const rowKey = `${item['PO Number']}-${item['PO Item']}`
                    const isExpanded = !!expandedRows[rowKey]
                    
                    return (
                      <>
                        <tr 
                          key={rowKey}
                          tabIndex={0}
                          className={`hover:bg-slate-900/40 transition-colors cursor-pointer border-l-2 ${
                            isExpanded ? 'bg-slate-900/50 border-l-indigo-500' : 'border-l-transparent'
                          }`}
                          onClick={() => toggleRow(rowKey)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRow(rowKey); } }}
                        >
                          <td className="py-4 pl-6 pr-4 font-mono font-bold text-slate-100">
                            {item['PO Number']} / {item['PO Item']}
                          </td>
                          <td className="py-4 px-4 truncate max-w-[150px]">{item.Vendor || 'N/A'}</td>
                          <td className="py-4 px-4 truncate max-w-[160px] text-slate-400">{item['Short Text'] || 'N/A'}</td>
                          <td className="py-4 px-4 text-center font-mono">{item.Plant}</td>
                          <td className="py-4 px-4 text-right font-mono font-bold text-slate-400">
                            {formatINR(item.net_gr_val)}
                          </td>
                          <td className="py-4 px-4 text-right font-mono font-bold text-slate-400">
                            {formatINR(item.net_ir_val)}
                          </td>
                          <td className={`py-4 px-4 text-right font-mono font-black ${
                            item.open_val < -0.01 ? 'text-rose-400' : item.open_val > 0.01 ? 'text-amber-400' : 'text-emerald-400'
                          }`}>
                            {formatINR(item.open_val)}
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                              item.status === 'Reconciled' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                              item.status === 'GR Done / IR Pending' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                              item.status === 'IR Done / GR Pending' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                              item.status === 'Invoice Greater Than GR' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              item.status === 'GR Greater Than Invoice' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                            }`}>
                              {item.status}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center font-mono font-bold text-slate-300">
                            {item.open_aging_days !== undefined && item.open_aging_days !== null && item.open_aging_days !== "" ? `${item.open_aging_days} days` : '--'}
                          </td>
                          <td className="py-4 pr-6 pl-4 text-center">
                            <button className="text-xs text-indigo-400 hover:text-indigo-300 font-bold transition-colors">
                              {isExpanded ? 'Collapse' : 'Investigate'}
                            </button>
                          </td>
                        </tr>

                        {/* Row Expansion Anomaly Drilldown */}
                        {isExpanded && (
                          <tr className="bg-slate-900/35">
                            <td colSpan={10} className="p-6 border-l-2 border-l-indigo-500 border-t border-slate-900">
                              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                {/* Explanation block */}
                                <div className="lg:col-span-2 space-y-3">
                                  <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
                                    <Info size={14} className="text-indigo-400" />
                                    Audit Discrepancy Analysis
                                  </h4>
                                  
                                  {/* Detailed Narrative */}
                                  <div className="bg-slate-950/80 border border-slate-850 p-4 rounded-xl relative">
                                    <p className="text-xs leading-relaxed text-slate-200">
                                      {item.explanation || 'Goods quantity and invoice values match baseline tolerances. No abnormal ledger patterns detected.'}
                                    </p>
                                    {item.status === 'IR ONLY' && (
                                      <div className="flex items-center gap-2 mt-3 p-2.5 rounded-lg border border-red-500/20 bg-red-500/5 text-[10px] text-red-400">
                                        <AlertCircle size={14} /> Critical: release control payment block is active for this invoice.
                                      </div>
                                    )}
                                    {item.status === 'OVER INVOICED' && (
                                      <div className="flex items-center gap-2 mt-3 p-2.5 rounded-lg border border-red-500/20 bg-red-500/5 text-[10px] text-red-400">
                                        <AlertCircle size={14} /> Immediate audit notification: quantity mismatch exceeds baseline.
                                      </div>
                                    )}
                                  </div>
                                </div>

                                {/* Detailed stats grid */}
                                <div className="bg-slate-950/40 border border-slate-850 rounded-xl p-4 space-y-3">
                                  <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest">Ancillary Indicators</h4>
                                  <div className="grid grid-cols-2 gap-3 text-[10px]">
                                    <div className="p-2.5 bg-slate-950/60 border border-slate-900 rounded-lg">
                                      <p className="text-slate-500 font-bold uppercase tracking-wider">Days Outstanding</p>
                                      <p className="text-sm font-black text-white mt-1 flex items-center gap-1">
                                        <Clock size={12} className="text-slate-500" /> {item.days_open ? `${item.days_open} days` : 'N/A'}
                                      </p>
                                    </div>
                                    
                                    <div className="p-2.5 bg-slate-950/60 border border-slate-900 rounded-lg">
                                      <p className="text-slate-500 font-bold uppercase tracking-wider">Posting Date</p>
                                      <p className="text-sm font-black text-white mt-1">
                                        {item.posting_date || 'N/A'}
                                      </p>
                                    </div>

                                    <div className="p-2.5 bg-slate-950/60 border border-slate-900 rounded-lg">
                                      <p className="text-slate-500 font-bold uppercase tracking-wider">Invoice Comp %</p>
                                      <p className="text-sm font-black text-indigo-400 mt-1">
                                        {formatPct(item.inv_completion_pct)}
                                      </p>
                                    </div>

                                    <div className="p-2.5 bg-slate-950/60 border border-slate-900 rounded-lg">
                                      <p className="text-slate-500 font-bold uppercase tracking-wider">Reversals Flag</p>
                                      <p className={`text-sm font-black mt-1 ${item.reversal_pct > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                                        {formatPct(item.reversal_pct)}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls Footer */}
          {itemsData?.pages > 1 && (
            <div className="py-4 px-6 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/50">
              <p className="text-xs text-slate-500 font-bold uppercase">
                Showing page <span className="text-slate-300 font-black">{page}</span> of <span className="text-slate-300 font-black">{itemsData.pages}</span>
                <span className="text-slate-500 ml-1.5">({safeLocaleString(itemsData.total)} filtered PO lines)</span>
              </p>

              <div className="flex items-center gap-2">
                {/* Previous page */}
                <button 
                  onClick={handlePrevPage}
                  disabled={page === 1}
                  className="p-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-950/80 text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronLeft size={16} />
                </button>

                <div className="flex items-center gap-1">
                  {/* Select Page Limit */}
                  <span className="text-[10px] text-slate-500 font-black uppercase mr-1">Limit:</span>
                  <select 
                    value={limit} 
                    onChange={e => { setLimit(Number(e.target.value)); setPage(1) }}
                    className="bg-slate-950/80 border border-slate-800 rounded-lg p-1.5 text-xs text-slate-300 outline-none cursor-pointer"
                  >
                    <option value="10">10</option>
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </select>
                </div>

                {/* Next page */}
                <button 
                  onClick={handleNextPage}
                  disabled={page === itemsData.pages}
                  className="p-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-950/80 text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    )
  }

  const renderIsolated7P = () => {
    if (showLoading) {
      return (
        <div className="space-y-6 animate-fadeIn">
          <div className="flex items-center justify-between mb-4">
            <SkeletonBlock className="h-10 w-1/3" />
            <div className="flex gap-4">
              <SkeletonBlock className="h-16 w-24" />
              <SkeletonBlock className="h-16 w-24" />
            </div>
          </div>
          <SkeletonBlock className="h-[400px] w-full" />
        </div>
      )
    }
    const data = summary?.isolated_type_7p
    if (!data || !data.items || data.items.length === 0) {
      return (
        <div className="p-10 text-center bg-slate-900/50 border border-slate-800 rounded-xl">
          <p className="text-slate-400">No Type 7 or Type P transactions found in this dataset.</p>
        </div>
      )
    }

    return (
      <section className="space-y-6 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <FileType className="text-indigo-400" /> Isolated Type 7 & Type P Log
            </h2>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
              These transaction types do not impact core GR/IR balance and are listed here for isolated auditing. 
              Their values are mathematically zeroed out from the main dashboard exposure logic.
            </p>
          </div>
          <div className="flex gap-4">
            <div className="bg-slate-900 px-4 py-2 rounded-lg border border-slate-800 text-center">
              <p className="text-[10px] text-slate-500 uppercase font-bold">Total Type 7 Qty</p>
              <p className="text-sm font-black text-white">{safeLocaleString(data.total_7_qty)}</p>
            </div>
            <div className="bg-slate-900 px-4 py-2 rounded-lg border border-slate-800 text-center">
              <p className="text-[10px] text-slate-500 uppercase font-bold">Total Type P Qty</p>
              <p className="text-sm font-black text-white">{safeLocaleString(data.total_p_qty)}</p>
            </div>
          </div>
        </div>

        <div className="glass-card border-slate-800 rounded-xl overflow-hidden bg-slate-900/50">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950">
              <tr>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">PO Number</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Item</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Vendor</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Material</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Type 7 Qty</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Type 7 Val</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Type P Qty</th>
                <th className="py-3 px-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Type P Val</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {data.items.slice(0, 100).map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 px-4 text-slate-300 font-mono text-xs">{item.po_number}</td>
                  <td className="py-3 px-4 text-slate-400 font-mono text-xs">{item.po_item}</td>
                  <td className="py-3 px-4 text-slate-300">{item.vendor}</td>
                  <td className="py-3 px-4 text-slate-300">{item.material}</td>
                  <td className="py-3 px-4 text-indigo-300 text-right font-mono font-bold">{safeLocaleString(item.type_7_qty)}</td>
                  <td className="py-3 px-4 text-indigo-400 text-right font-mono font-bold">{formatINR(item.type_7_val)}</td>
                  <td className="py-3 px-4 text-amber-300 text-right font-mono font-bold">{safeLocaleString(item.type_p_qty)}</td>
                  <td className="py-3 px-4 text-amber-400 text-right font-mono font-bold">{formatINR(item.type_p_val)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    )
  }

  if (summaryError && !isUploadingFile) {
    return (
      <div className="min-h-screen bg-slate-950 pb-16">
        <NavBar />
        <main id="dashboard-container" className="max-w-[1600px] mx-auto px-5 pt-8 space-y-8">
          <GrirUploadZone onUploadSuccess={handleUploadSuccess} onUploadStart={() => setIsUploadingFile(true)} />
          
          <div className="bg-slate-900/50 border border-red-500/20 rounded-2xl p-10 flex flex-col items-center justify-center text-center">
            <AlertTriangle size={64} className="text-red-500 mb-4 animate-bounce" />
            <h1 className="text-2xl font-black text-white mb-2">Analysis Pending</h1>
            <p className="text-slate-400 max-w-md mb-6">
              {summaryError?.response?.data?.error || summaryError?.message || 'Unable to load the GR/IR Reconciliation Analysis results. Please upload your GR/IR file above to begin.'}
            </p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 pb-16">
      <NavBar />

      <main id="dashboard-container" className="max-w-[1600px] mx-auto px-5 pt-8 space-y-8">

        {/* ── GRIR Upload Zone ────────────────────────────────────────────── */}
        <GrirUploadZone onUploadSuccess={handleUploadSuccess} onUploadStart={() => setIsUploadingFile(true)} />

        {/* Title Block */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-900">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="badge-indigo">SAP Audit Ledger</span>
              {summary?.metadata && (
                <span className="text-xs text-slate-500 font-bold flex items-center gap-1">
                  <Calendar size={12} /> Generated: {summary.metadata.generated_at}
                </span>
              )}
            </div>
            <h1 className="text-4xl font-extrabold text-white tracking-tight">
              GR/IR <span className="gradient-text">Reconciliation</span> Dashboard
            </h1>
            <p className="text-slate-400 text-sm mt-1 max-w-2xl leading-relaxed">
              Real-time 3-way match audit anomalies between Goods Receipt (GR) and Invoice Receipt (IR) lines. Matches EKKO, ME2N and GRIR ledgers.
            </p>
          </div>

          <div className="flex items-center gap-4 bg-slate-900/60 border border-slate-800/80 px-4 py-3 rounded-2xl">
            <div className="text-right">
              <p className="text-[10px] text-slate-500 uppercase font-black tracking-widest">GRIR Rows</p>
              <p className="text-sm font-bold text-slate-200 mt-0.5">
                {summary?.metadata ? `${safeLocaleString(summary.metadata.grir_row_count)}` : '--'}
              </p>
            </div>
            <div className="w-px h-8 bg-slate-800" />
            <div className="text-right">
              <p className="text-[10px] text-slate-500 uppercase font-black tracking-widest font-mono">PO Lines</p>
              <p className="text-sm font-bold text-indigo-400 mt-0.5">
                {summary?.metadata ? `${safeLocaleString(summary.metadata.me2n_row_count)}` : '--'}
              </p>
            </div>
            <div className="w-px h-8 bg-slate-800" />
            <button
              onClick={() => refetchSummary()}
              title="Refresh dashboard data"
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 hover:text-slate-200 transition-all"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>

        {/* Tab Navigation Menu */}
        <div className="flex flex-wrap items-center gap-1 bg-[#111827] p-1 border border-slate-800 rounded-lg">
          {[
            { id: 'overview', name: 'Executive Overview', icon: Activity },
            { id: 'vendors', name: 'Vendor Analytics', icon: Users },
            { id: 'materials', name: 'Material Analytics', icon: Package },
            { id: 'aging', name: 'Aging Engine', icon: Clock },
            { id: 'reversals', name: 'Reversal Log', icon: RefreshCw },
            { id: 'variance', name: 'Price Variance', icon: Percent },
            { id: 'isolated_7p', name: 'Isolated 7/P', icon: FileType },
            { id: 'explorer', name: 'Ledger Explorer', icon: Search }
          ].map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-bold transition-colors border ${
                  isActive 
                    ? 'bg-slate-800 border-slate-600 text-indigo-400' 
                    : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Icon size={14} className={isActive ? 'text-indigo-400' : 'text-slate-500'} />
                {tab.name}
              </button>
            )
          })}
        </div>

        {/* Tab Content Panels */}
        <div className="w-full">
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'vendors' && renderVendors()}
          {activeTab === 'materials' && renderMaterials()}
          {activeTab === 'aging' && renderAging()}
          {activeTab === 'reversals' && renderReversals()}
          {activeTab === 'variance' && renderPriceVariance()}
          {activeTab === 'isolated_7p' && renderIsolated7P()}
          {activeTab === 'explorer' && renderLedgerExplorer()}
        </div>

      </main>
    </div>
  )
}
