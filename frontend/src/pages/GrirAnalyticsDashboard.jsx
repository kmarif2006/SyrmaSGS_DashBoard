import { useEffect, useState, useCallback } from 'react'
import { AlertCircle, Download, RefreshCw, Upload, CheckCircle2, BarChart3, TrendingUp } from 'lucide-react'
import { toast } from 'react-hot-toast'

function GrirAnalyticsDashboard() {
  const [dashboardData, setDashboardData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('kpis')

  const fetchDashboard = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/grir/dashboard')
      const data = await response.json()
      
      if (data.success) {
        setDashboardData(data)
      } else {
        setError(data.error || 'Failed to load dashboard')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleFileUpload = useCallback(async (e) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    try {
      const formData = new FormData()
      for (let file of files) {
        formData.append('file', file)
      }

      const response = await fetch('/api/grir/upload-files', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (data.success) {
        toast.success(`Analysis complete: ${data.po_lines_analyzed} PO lines processed`)
        await fetchDashboard()
      } else {
        toast.error(data.error || 'Upload failed')
        setError(data.error)
      }
    } catch (err) {
      toast.error(err.message)
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }, [fetchDashboard])

  const handleExport = useCallback(async (format) => {
    try {
      const url = `/api/grir/export/${format}`
      const link = document.createElement('a')
      link.href = url
      link.click()
      toast.success(`Export started (${format.toUpperCase()})`)
    } catch (err) {
      toast.error(`Export failed: ${err.message}`)
    }
  }, [])

  useEffect(() => {
    fetchDashboard()
  }, [fetchDashboard])

  if (loading && !dashboardData) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-indigo-500 mx-auto mb-4 animate-spin" />
          <p className="text-slate-300">Loading GRIR Analysis...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <div className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur border-b border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <BarChart3 className="w-8 h-8 text-indigo-500" />
              GRIR Analytics Dashboard
            </h1>
            {dashboardData?.analysis_timestamp && (
              <p className="text-sm text-slate-400 mt-1">
                Last Updated: {new Date(dashboardData.analysis_timestamp).toLocaleString()}
              </p>
            )}
          </div>
          <div className="flex gap-3">
            <label className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded-lg cursor-pointer flex items-center gap-2 transition">
              <Upload className="w-4 h-4" />
              Upload
              <input
                type="file"
                multiple
                accept=".csv,.xlsx,.xls"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>
            <button
              onClick={() => handleExport('json')}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center gap-2 transition"
            >
              <Download className="w-4 h-4" />
              JSON
            </button>
            <button
              onClick={() => handleExport('excel')}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center gap-2 transition"
            >
              <Download className="w-4 h-4" />
              Excel
            </button>
            <button
              onClick={fetchDashboard}
              disabled={loading}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center gap-2 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg m-6 p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <div>
            <p className="font-semibold text-red-300">Error</p>
            <p className="text-sm text-red-200">{error}</p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!error && !dashboardData?.kpis && !loading && (
        <div className="flex flex-col items-center justify-center h-96 m-6 border-2 border-dashed border-slate-700 rounded-lg">
          <Upload className="w-16 h-16 text-slate-600 mb-4" />
          <h3 className="text-xl font-semibold text-slate-400 mb-2">No Data Loaded</h3>
          <p className="text-slate-500 mb-6">Upload GRIR, ME2N, and EKKO files to begin analysis</p>
          <label className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 rounded-lg cursor-pointer font-medium transition">
            Choose Files
            <input
              type="file"
              multiple
              accept=".csv,.xlsx,.xls"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
      )}

      {/* Dashboard Content */}
      {dashboardData?.kpis && (
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* KPIs Section */}
          <div>
            <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
              <TrendingUp className="w-6 h-6 text-indigo-500" />
              Executive KPIs
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <KPICard
                label="Total PO Lines"
                value={dashboardData.kpis.total_po_lines}
                format="number"
              />
              <KPICard
                label="Reconciliation Rate"
                value={dashboardData.kpis.reconciliation_rate_pct}
                format="percent"
              />
              <KPICard
                label="Open Exposure (INR)"
                value={dashboardData.kpis.total_open_exposure_inr}
                format="currency"
              />
              <KPICard
                label="Reconciled Lines"
                value={dashboardData.kpis.reconciled_po_lines}
                format="number"
              />
              <KPICard
                label="GR Value (INR)"
                value={dashboardData.kpis.total_gr_value_inr}
                format="currency"
              />
              <KPICard
                label="IR Value (INR)"
                value={dashboardData.kpis.total_ir_value_inr}
                format="currency"
              />
              <KPICard
                label="Pending Invoices"
                value={dashboardData.kpis.pending_invoice_count}
                format="number"
              />
              <KPICard
                label="Pending GRs"
                value={dashboardData.kpis.pending_gr_count}
                format="number"
              />
            </div>
          </div>

          {/* Charts Section */}
          {dashboardData?.charts && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <ChartCard title="Reconciliation Status" data={dashboardData.charts.reconciliation_status_donut} />
              <ChartCard title="Aging Distribution" data={dashboardData.charts.aging_bucket_histogram} />
              <ChartCard title="Top Vendors by Exposure" data={dashboardData.charts.vendor_exposure_bar} />
              <ChartCard title="Plant Exposure" data={dashboardData.charts.plant_exposure_bar} />
            </div>
          )}

          {/* Insights Section */}
          {dashboardData?.insights && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
              <InsightCard
                title="Top Vendors by Open Exposure"
                items={dashboardData.insights.top_vendors_by_exposure?.slice(0, 5)}
              />
              <InsightCard
                title="Largest Unreconciled PO Lines"
                items={dashboardData.insights.largest_unreconciled_po_lines?.slice(0, 5)}
              />
              <InsightCard
                title="Vendor Invoice Delay Ranking"
                items={dashboardData.insights.vendor_invoice_delay_ranking?.slice(0, 5)}
              />
              <div className="glass-card p-6 rounded-lg border border-slate-700">
                <h3 className="font-bold text-lg mb-4">Status Summary</h3>
                <div className="space-y-3">
                  {Object.entries(dashboardData.insights.status_summary || {}).map(([status, data]) => (
                    <div key={status} className="flex justify-between items-center">
                      <span className="text-slate-300">{status}</span>
                      <div className="text-right">
                        <p className="font-semibold">{data.count}</p>
                        <p className="text-xs text-slate-400">₹{(data.exposure_inr / 1e5).toFixed(2)}L</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Aging Analysis */}
          {dashboardData?.aging && (
            <div className="glass-card p-6 rounded-lg border border-slate-700 mb-8">
              <h3 className="font-bold text-lg mb-4">Aging Analysis</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-slate-600">
                    <tr>
                      <th className="text-left py-2 px-3">Aging Bucket</th>
                      <th className="text-center py-2 px-3">Total Items</th>
                      <th className="text-center py-2 px-3">Reconciled</th>
                      <th className="text-right py-2 px-3">Exposure (INR)</th>
                      <th className="text-center py-2 px-3">IR Pending</th>
                      <th className="text-center py-2 px-3">GR Pending</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {dashboardData.aging.map((row) => (
                      <tr key={row.aging_bucket} className="hover:bg-slate-800/50">
                        <td className="py-3 px-3">{row.aging_bucket}</td>
                        <td className="text-center">{row.total_items}</td>
                        <td className="text-center text-emerald-400">{row.reconciled_items}</td>
                        <td className="text-right font-semibold">₹{(row.total_exposure_inr / 1e5).toFixed(2)}L</td>
                        <td className="text-center text-yellow-400">{row.ir_pending_count}</td>
                        <td className="text-center text-orange-400">{row.gr_pending_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function KPICard({ label, value, format }) {
  let displayValue = value

  if (format === 'currency') {
    displayValue = `₹${(value / 1e5).toFixed(1)}L`
  } else if (format === 'percent') {
    displayValue = `${value.toFixed(1)}%`
  } else if (format === 'number') {
    displayValue = value.toLocaleString('en-IN')
  }

  return (
    <div className="glass-card p-6 rounded-lg border border-slate-700 hover:border-indigo-500/50 transition">
      <p className="text-slate-400 text-sm font-medium mb-2">{label}</p>
      <p className="text-3xl font-bold text-white">{displayValue}</p>
    </div>
  )
}

function ChartCard({ title, data }) {
  return (
    <div className="glass-card p-6 rounded-lg border border-slate-700">
      <h4 className="font-bold text-lg mb-4">{title}</h4>
      {data && data.length > 0 ? (
        <div className="space-y-2">
          {data.slice(0, 8).map((item, idx) => (
            <div key={idx} className="flex justify-between items-center">
              <span className="text-slate-300 text-sm truncate">{item.name || item.month}</span>
              <div className="flex items-center gap-2">
                <div className="w-32 bg-slate-700 rounded-full h-2">
                  <div
                    className="bg-indigo-500 h-2 rounded-full"
                    style={{
                      width: `${Math.min((item.value / Math.max(...data.map(d => d.value || 0))) * 100, 100)}%`
                    }}
                  />
                </div>
                <span className="text-right text-slate-300 text-sm">{item.value?.toFixed(0)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-slate-500 text-sm">No data available</p>
      )}
    </div>
  )
}

function InsightCard({ title, items }) {
  return (
    <div className="glass-card p-6 rounded-lg border border-slate-700">
      <h4 className="font-bold text-lg mb-4 flex items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-indigo-500" />
        {title}
      </h4>
      <div className="space-y-3">
        {items && items.length > 0 ? (
          items.map((item, idx) => (
            <div key={idx} className="flex justify-between items-start gap-2 p-2 bg-slate-800/40 rounded">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">
                  {item.vendor || item.po_number || item.name || 'N/A'}
                </p>
                {item.material_group && (
                  <p className="text-xs text-slate-400">{item.material_group}</p>
                )}
              </div>
              <div className="text-right whitespace-nowrap">
                <p className="text-sm font-bold text-indigo-400">
                  ₹{(item.exposure_inr / 1e5 || item.value / 1e5).toFixed(1)}L
                </p>
                {item.avg_days_open && (
                  <p className="text-xs text-slate-400">{item.avg_days_open.toFixed(0)}d</p>
                )}
              </div>
            </div>
          ))
        ) : (
          <p className="text-slate-500 text-sm">No data available</p>
        )}
      </div>
    </div>
  )
}

export default GrirAnalyticsDashboard
