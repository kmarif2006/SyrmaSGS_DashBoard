import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { CustomTooltip } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-48 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

const BUCKET_COLORS = { '0-30 days': '#10b981', '31-60 days': '#f59e0b', '61-90 days': '#f97316', '90+ days': '#ef4444' }

export default function AgingChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-48 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ left: 0, right: 10, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="Bucket" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            return (
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                <p className="text-slate-300 font-medium mb-1">{label}</p>
                <p className="text-white"><span className="text-slate-400">POs: </span><span className="font-bold">{payload[0]?.value?.toLocaleString()}</span></p>
              </div>
            )
          }}
          cursor={{ fill: 'rgba(99,102,241,0.08)' }}
        />
        <Bar dataKey="PO_Count" name="PO Count" radius={[6, 6, 0, 0]} maxBarSize={64}>
          {data.map((d, i) => <Cell key={i} fill={BUCKET_COLORS[d.Bucket] || '#6366f1'} fillOpacity={0.85} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
