import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { formatINR, truncate, CustomTooltip, CHART_COLORS } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-72 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function SupplierChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-72 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  const sorted = [...data].sort((a, b) => a.Total_Spend_INR - b.Total_Spend_INR)

  return (
    <ResponsiveContainer width="100%" height={Math.max(320, sorted.length * 38)}>
      <BarChart data={sorted} layout="vertical" margin={{ left: 8, right: 20, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={v => formatINR(v)}
          tick={{ fill: '#64748b', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="Supplier"
          width={180}
          tick={{ fill: '#94a3b8', fontSize: 11 }}
          tickFormatter={v => truncate(v, 26)}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={<CustomTooltip formatter={(v) => formatINR(v)} />}
          cursor={{ fill: 'rgba(99,102,241,0.08)' }}
        />
        <Bar dataKey="Total_Spend_INR" name="Total Spend (INR)" radius={[0, 6, 6, 0]} maxBarSize={24}>
          {sorted.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
