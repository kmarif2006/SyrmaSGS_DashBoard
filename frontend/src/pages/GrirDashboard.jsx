import { useState, useMemo } from 'react'
import { 
  useGrirSummary, 
  useGrirItems 
} from '../hooks/useAnalytics'
import NavBar from '../components/NavBar'
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell
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
  Percent
} from 'lucide-react'

// Colors for charts
const STATUS_COLORS = {
  'FULLY RECONCILED': '#10b981', // Emerald
  'FULLY REVERSED': '#64748b',   // Slate
  'PRICE VARIANCE': '#f59e0b',   // Amber
  'GR ONLY': '#3b82f6',          // Blue
  'IR ONLY': '#8b5cf6',          // Violet
  'PARTIALLY INVOICED': '#06b6d4', // Cyan
  'OVER INVOICED': '#ef4444',    // Red
}

const RISK_COLORS = {
  'CRITICAL': '#ef4444', // Red
  'HIGH': '#f97316',     // Orange
  'MEDIUM': '#eab308',   // Yellow
  'LOW': '#10b981',      // Emerald
}

function GrirKPICard({ title, value, sub, icon: Icon, colorClass, isLoading }) {
  return (
    <div className="glass-card-hover p-6 flex items-center justify-between">
      <div className="space-y-2">
        <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">{title}</p>
        {isLoading ? (
          <div className="h-8 w-24 bg-slate-800 animate-pulse rounded" />
        ) : (
          <p className="text-2xl font-black text-white tracking-tight">{value}</p>
        )}
        <p className="text-xs text-slate-400 font-medium">{sub}</p>
      </div>
      <div className={`p-3.5 rounded-2xl border ${colorClass}`}>
        <Icon size={24} />
      </div>
    </div>
  )
}

export default function GrirDashboard() {
  const { data: summary, isLoading: isSummaryLoading, error: summaryError } = useGrirSummary()

  // Tab state
  const [activeTab, setActiveTab] = useState('overview')

  // Pagination, search and filters state
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [plantFilter, setPlantFilter] = useState('')
  const [sortBy, setSortBy] = useState('risk_score')
  const [sortOrder, setSortOrder] = useState('desc')
  const [limit, setLimit] = useState(25)

  // Track expanded rows in main table
  const [expandedRows, setExpandedRows] = useState({})

  const itemsParams = useMemo(() => ({
    page,
    limit,
    search,
    status: statusFilter,
    risk_level: riskFilter,
    plant: plantFilter,
    sortBy,
    sortOrder
  }), [page, limit, search, statusFilter, riskFilter, plantFilter, sortBy, sortOrder])

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

  // Reset filters
  const resetFilters = () => {
    setSearch('')
    setStatusFilter('')
    setRiskFilter('')
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

  const riskChartData = useMemo(() => {
    if (!summary?.kpis?.risk_distribution) return []
    return Object.entries(summary.kpis.risk_distribution).map(([risk, count]) => ({
      name: risk,
      value: count
    }))
  }, [summary])

  const topVendorsChartData = useMemo(() => {
    if (!summary?.vendor_insights) return []
    return summary.vendor_insights.slice(0, 10).map(v => ({
      name: v.vendor.length > 15 ? v.vendor.substring(0, 15) + '...' : v.vendor,
      fullName: v.vendor,
      'Open Exposure': v.open_value,
      'Pending Invoice': v.pending_invoice,
      'Over Invoiced': v.over_invoiced,
    }))
  }, [summary])

  const agingChartData = useMemo(() => {
    if (!summary?.aging_analysis) return []
    return summary.aging_analysis.map(item => ({
      name: item.bucket + ' days',
      'GR ONLY': item.gr_only_val,
      'PARTIALLY INVOICED': item.partial_inv_val,
      'OVER INVOICED': item.over_inv_val,
      'IR ONLY': item.ir_only_val,
    }))
  }, [summary])

  // Sub-Section Tab Renderers
  const renderOverview = () => {
    return (
      <div className="space-y-10 animate-fadeIn">
        {/* KPIs Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <GrirKPICard 
            title="Reconciliation Rate"
            value={summary?.kpis ? formatPct(summary.kpis.reconciliation_rate) : '--'}
            sub={`${summary?.kpis ? safeLocaleString(summary.kpis.reconciled_count) : '--'} / ${summary?.kpis ? safeLocaleString(summary.kpis.total_po_items) : '--'} PO lines reconciled`}
            icon={CheckCircle2}
            colorClass="text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
            isLoading={isSummaryLoading}
          />
          <GrirKPICard 
            title="Total Open Exposure"
            value={summary?.kpis ? formatINR(summary.kpis.total_open_value) : '--'}
            sub="Net accrual & variance value"
            icon={DollarSign}
            colorClass="text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
            isLoading={isSummaryLoading}
          />
          <GrirKPICard 
            title="Critical Risk Items"
            value={summary?.kpis ? safeLocaleString(summary.kpis.critical_items) : '--'}
            sub="Immediate escalation required"
            icon={ShieldAlert}
            colorClass="text-red-400 bg-red-500/10 border-red-500/20"
            isLoading={isSummaryLoading}
          />
          <GrirKPICard 
            title="Active Vendor pool"
            value={summary?.kpis ? safeLocaleString(summary.kpis.unique_vendors) : '--'}
            sub="With open GR/IR balances"
            icon={Users}
            colorClass="text-amber-400 bg-amber-500/10 border-amber-500/20"
            isLoading={isSummaryLoading}
          />
        </div>

        {/* Executive Summary Narrative */}
        {summary?.executive_summary && (
          <div className="glass-card p-6 bg-slate-900/40 relative overflow-hidden border-indigo-500/10">
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
                  <p className="text-xs text-red-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                    <AlertTriangle size={14} /> Critical Risk Flags
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
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          
          {/* Status Distribution */}
          <div className="glass-card p-6 flex flex-col xl:col-span-2">
            <div className="mb-6 flex justify-between items-center">
              <div>
                <h3 className="text-base font-bold text-slate-100 mb-1">Reconciliation Status Profile</h3>
                <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Volume distribution of all PO lines</p>
              </div>
              <span className="badge bg-slate-800 text-slate-400 font-semibold text-[10px] border border-slate-700">7 Categories</span>
            </div>
            <div className="flex-1 min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusChartData} layout="vertical" margin={{ left: 50, right: 20 }}>
                  <XAxis type="number" stroke="#475569" className="text-xs" />
                  <YAxis type="category" dataKey="name" stroke="#475569" className="text-xs" width={120} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }}
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
            </div>
          </div>

          {/* Risk Level Distribution */}
          <div className="glass-card p-6 flex flex-col">
            <div className="mb-6">
              <h3 className="text-base font-bold text-slate-100 mb-1">Audit Risk Composition</h3>
              <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Items by severity band</p>
            </div>
            <div className="flex-1 flex flex-col md:flex-row xl:flex-col items-center justify-center gap-6">
              <div className="w-44 h-44 flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={riskChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={75}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {riskChartData.map((entry, idx) => (
                        <Cell key={`cell-${idx}`} fill={RISK_COLORS[entry.name] || '#cbd5e1'} />
                      ))}
                    </Pie>
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }}
                      itemStyle={{ color: '#f1f5f9', fontSize: '12px' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="flex-1 w-full space-y-2.5">
                {riskChartData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs p-2 bg-slate-900/40 rounded-xl border border-slate-800/50">
                    <div className="flex items-center gap-2">
                      <span className="w-3.5 h-3.5 rounded-md" style={{ backgroundColor: RISK_COLORS[item.name] }} />
                      <span className="font-bold text-slate-300 uppercase tracking-wider">{item.name}</span>
                    </div>
                    <span className="font-black text-white">{safeLocaleString(item.value)} items</span>
                  </div>
                ))}
              </div>
            </div>
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
              {summary?.financial_impact?.map((impact, idx) => (
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
              ))}
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
              {summary?.recommended_actions?.map((act, idx) => (
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
              ))}
            </div>
          </div>
        </div>

        {/* Major Exceptions Drawer List */}
        {summary?.top_exceptions?.length > 0 && (
          <div className="glass-card p-6">
            <div className="mb-6 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                  <ShieldAlert size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100 mb-0.5">Top 30 Critical Audit Anomalies</h3>
                  <p className="text-xs text-slate-500 font-bold tracking-wide uppercase">Ranked by risk score and value severity</p>
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
                    <th className="pb-3 px-4 text-center">Risk</th>
                    <th className="pb-3 pl-4">Audit Exception Narrative</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {summary.top_exceptions.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                      <td className="py-3.5 pr-4 font-mono font-bold text-slate-200">
                        {item.po_number} / {item.po_item}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 max-w-[150px] truncate">{item.vendor}</td>
                      <td className="py-3.5 px-4 text-slate-400 max-w-[180px] truncate">{item.material}</td>
                      <td className="py-3.5 px-4 text-center">
                        <span className={`px-2 py-0.5 rounded font-black tracking-widest text-[9px] uppercase border ${
                          item.status === 'GR ONLY' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                          item.status === 'IR ONLY' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                          item.status === 'OVER INVOICED' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                          item.status === 'PRICE VARIANCE' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                        }`}>
                          {item.status}
                        </span>
                      </td>
                      <td className={`py-3.5 px-4 text-right font-bold font-mono ${item.open_val < 0 ? 'text-red-400' : 'text-slate-300'}`}>
                        {formatINR(item.open_val)}
                      </td>
                      <td className="py-3.5 px-4 text-center font-bold">
                        <span className={`px-2 py-0.5 rounded text-[9px] border uppercase ${
                          item.risk_level === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-orange-500/10 text-orange-400 border-orange-500/20'
                        }`}>
                          {item.risk_score} {item.risk_level}
                        </span>
                      </td>
                      <td className="py-3.5 pl-4 text-slate-400 leading-normal italic text-[11px] max-w-[320px]">
                        {item.explanation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderVendors = () => {
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
                    formatter={(val) => [formatINR(val), 'Exposure']}
                  />
                  <Bar dataKey="Open Exposure" radius={[0, 4, 4, 0]} fill="#6366f1" />
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
                    <th className="pb-3 px-4 text-center">Risk</th>
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
                            <span className="badge bg-slate-800 text-[9px] text-slate-300 border border-slate-700 font-bold uppercase tracking-wider">{v.dominant_status}</span>
                          </td>
                          <td className="py-3 px-4 text-center font-bold">
                            <span className={`px-2 py-0.5 rounded text-[9px] border uppercase ${
                              v.risk_level === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
                              v.risk_level === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' : 
                              v.risk_level === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            }`}>
                              {v.risk_level}
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
                              className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${
                                status === 'FULLY RECONCILED' ? 'bg-emerald-500/5 text-emerald-400 border-emerald-500/10' :
                                status === 'GR ONLY' ? 'bg-blue-500/5 text-blue-400 border-blue-500/10' :
                                status === 'IR ONLY' ? 'bg-purple-500/5 text-purple-400 border-purple-500/10' :
                                status === 'OVER INVOICED' ? 'bg-red-500/5 text-red-400 border-red-500/10' : 'bg-cyan-500/5 text-cyan-400 border-cyan-500/10'
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
    const agingData = summary?.aging_analysis || []

    return (
      <div className="space-y-6 animate-fadeIn">
        {/* Aging KPI Cards Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {agingData.map((item, idx) => (
            <div key={idx} className="glass-card p-4 space-y-1.5 flex flex-col justify-between">
              <div className="space-y-0.5">
                <span className="text-[10px] text-slate-500 font-black tracking-widest uppercase">Bucket</span>
                <p className="text-base font-black text-white">{item.bucket} Days</p>
              </div>
              <div>
                <p className="text-sm font-extrabold text-indigo-400">{formatINR(item.open_value)}</p>
                <p className="text-[10px] text-slate-400">{item.open_count} open items</p>
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
                  <Bar dataKey="GR ONLY" stackId="a" fill="#3b82f6" />
                  <Bar dataKey="PARTIALLY INVOICED" stackId="a" fill="#06b6d4" />
                  <Bar dataKey="OVER INVOICED" stackId="a" fill="#ef4444" />
                  <Bar dataKey="IR ONLY" stackId="a" fill="#8b5cf6" />
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
                      <strong className="text-slate-200 font-black">{item.bucket} Days</strong>
                      <span className="text-slate-400 font-mono font-bold">{item.open_count} / {item.total_count} open</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-slate-500">Open Value</span>
                      <span className="font-mono font-black text-indigo-400">{formatINR(item.open_value)}</span>
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
          <div className="glass-card p-5 space-y-1 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Operational Risks</p>
              <p className="text-sm font-bold text-slate-300 mt-1">
                High reversal rates signal posting errors, inventory corrections, or vendor invoice disputes.
              </p>
            </div>
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-xl">
              <AlertTriangle size={20} />
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
                  <th className="pb-3 px-4 text-center">Net IR Qty</th>
                  <th className="pb-3 px-4 text-center">Reversal Qty</th>
                  <th className="pb-3 px-4 text-right">Reversal Value</th>
                  <th className="pb-3 px-4 text-center">Reversal %</th>
                  <th className="pb-3 px-4 text-right">Open Value</th>
                  <th className="pb-3 pl-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300 font-medium">
                {reversals.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500 font-bold">No active reversal records detected.</td>
                  </tr>
                ) : (
                  reversals.map((r, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/30 transition-colors">
                      <td className="py-3.5 pr-4 font-mono font-bold text-slate-200">
                        {r.po_number} / {r.po_item}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 truncate max-w-[120px]" title={r.vendor}>{r.vendor}</td>
                      <td className="py-3.5 px-4 text-slate-400 truncate max-w-[150px]" title={r.material}>{r.material}</td>
                      <td className="py-3.5 px-4 text-center font-mono">{r.ir_qty}</td>
                      <td className="py-3.5 px-4 text-center font-mono text-amber-400 font-bold">{r.reversal_qty}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-400">{formatINR(r.reversal_val)}</td>
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
                  <th className="pb-3 pl-4 text-center">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-slate-300 font-medium">
                {variances.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500 font-bold">No compliance price variances detected.</td>
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
                      <td className="py-3.5 pl-4 text-center">
                        <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                          v.risk_level === 'HIGH' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                        }`}>
                          {v.risk_level}
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

  const renderLedgerExplorer = () => {
    return (
      <section className="glass-card p-6 space-y-6 animate-fadeIn">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers size={18} className="text-indigo-400" />
              Ledger Investigation Center
            </h3>
            <p className="text-xs text-slate-500 font-bold uppercase mt-0.5">Filter, search, and drill down on all {summary?.kpis ? safeLocaleString(summary.kpis.total_po_items, '47,803') : '47,803'} PO lines</p>
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
              <option value="FULLY RECONCILED" className="bg-slate-900">FULLY RECONCILED</option>
              <option value="FULLY REVERSED" className="bg-slate-900">FULLY REVERSED</option>
              <option value="PRICE VARIANCE" className="bg-slate-900">PRICE VARIANCE</option>
              <option value="GR ONLY" className="bg-slate-900">GR ONLY</option>
              <option value="IR ONLY" className="bg-slate-900">IR ONLY</option>
              <option value="PARTIALLY INVOICED" className="bg-slate-900">PARTIALLY INVOICED</option>
              <option value="OVER INVOICED" className="bg-slate-900">OVER INVOICED</option>
            </select>
          </div>

          {/* Risk Filter */}
          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-850 px-3 py-2 rounded-xl">
            <ShieldAlert size={14} className="text-slate-500" />
            <select 
              value={riskFilter} 
              onChange={e => { setRiskFilter(e.target.value); setPage(1) }}
              className="bg-transparent text-xs text-slate-300 outline-none w-full border-none cursor-pointer"
            >
              <option value="" className="bg-slate-900">All Risks</option>
              <option value="CRITICAL" className="bg-slate-900 font-bold text-red-400">CRITICAL</option>
              <option value="HIGH" className="bg-slate-900 text-orange-400">HIGH</option>
              <option value="MEDIUM" className="bg-slate-900 text-yellow-400">MEDIUM</option>
              <option value="LOW" className="bg-slate-900 text-emerald-400">LOW</option>
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
                  <th className="py-4 pl-6 pr-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('PO Number')}>
                    <div className="flex items-center gap-1.5">
                      PO Doc / Item <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('Vendor')}>
                    <div className="flex items-center gap-1.5">
                      Vendor <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 cursor-pointer hover:text-slate-200" onClick={() => handleSort('Short Text')}>
                    <div className="flex items-center gap-1.5">
                      Short Text <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200" onClick={() => handleSort('Plant')}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Plant <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200" onClick={() => handleSort('net_gr_val')}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Net GR <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200" onClick={() => handleSort('net_ir_val')}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Net IR <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-right cursor-pointer hover:text-slate-200" onClick={() => handleSort('open_val')}>
                    <div className="flex items-center gap-1.5 justify-end">
                      Open Val <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200" onClick={() => handleSort('status')}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Status <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-4 px-4 text-center cursor-pointer hover:text-slate-200" onClick={() => handleSort('risk_score')}>
                    <div className="flex items-center gap-1.5 justify-center">
                      Risk Score <ArrowUpDown size={12} />
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
                          className={`hover:bg-slate-900/40 transition-colors cursor-pointer border-l-2 ${
                            isExpanded ? 'bg-slate-900/50 border-l-indigo-500' : 'border-l-transparent'
                          }`}
                          onClick={() => toggleRow(rowKey)}
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
                            item.open_val < -1 ? 'text-rose-400' : item.open_val > 1 ? 'text-amber-400' : 'text-emerald-400'
                          }`}>
                            {formatINR(item.open_val)}
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-black tracking-widest uppercase border ${
                              item.status === 'FULLY RECONCILED' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                              item.status === 'FULLY REVERSED' ? 'bg-slate-500/10 text-slate-400 border-slate-500/20' :
                              item.status === 'GR ONLY' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                              item.status === 'IR ONLY' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                              item.status === 'OVER INVOICED' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              item.status === 'PRICE VARIANCE' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                            }`}>
                              {item.status}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${
                              item.risk_level === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              item.risk_level === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                              item.risk_level === 'MEDIUM' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            }`}>
                              {item.risk_score} {item.risk_level}
                            </span>
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

  if (summaryError) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-center">
        <AlertTriangle size={64} className="text-red-500 mb-4 animate-bounce" />
        <h1 className="text-2xl font-black text-white mb-2">GR/IR Data Error</h1>
        <p className="text-slate-400 max-w-md mb-6">
          Unable to load the GR/IR Reconciliation Analysis results. Please make sure that the Python script has run successfully.
        </p>
        <button 
          onClick={() => window.location.reload()} 
          className="btn-primary"
        >
          Retry Loading
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 pb-16">
      <NavBar />

      <main id="dashboard-container" className="max-w-[1600px] mx-auto px-5 pt-8 space-y-8">
        
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
              <p className="text-[10px] text-slate-500 uppercase font-black tracking-widest">Scope Coverage</p>
              <p className="text-sm font-bold text-slate-200 mt-0.5">
                {summary?.metadata ? `${safeLocaleString(summary.metadata.grir_row_count)} GR/IR rows` : '--'}
              </p>
            </div>
            <div className="w-px h-8 bg-slate-800" />
            <div className="text-right">
              <p className="text-[10px] text-slate-500 uppercase font-black tracking-widest font-mono">PO Line Items</p>
              <p className="text-sm font-bold text-indigo-400 mt-0.5">
                {summary?.metadata ? `${safeLocaleString(summary.metadata.me2n_row_count)} items` : '--'}
              </p>
            </div>
          </div>
        </div>

        {/* Tab Navigation Menu */}
        <div className="flex flex-wrap items-center gap-2 bg-slate-900/10 p-1.5 border border-slate-900 rounded-2xl backdrop-blur-md">
          {[
            { id: 'overview', name: 'Executive Overview', icon: Activity },
            { id: 'vendors', name: 'Vendor Analytics', icon: Users },
            { id: 'materials', name: 'Material Analytics', icon: Package },
            { id: 'aging', name: 'Aging Engine', icon: Clock },
            { id: 'reversals', name: 'Reversal Log', icon: RefreshCw },
            { id: 'variance', name: 'Price Variance', icon: Percent },
            { id: 'explorer', name: 'Ledger Explorer', icon: Search }
          ].map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all border ${
                  isActive 
                    ? 'bg-indigo-600/15 border-indigo-500/30 text-indigo-400 font-extrabold shadow-lg shadow-indigo-500/5' 
                    : 'bg-slate-900/40 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 hover:border-slate-700/80'
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
          {activeTab === 'explorer' && renderLedgerExplorer()}
        </div>

      </main>
    </div>
  )
}
