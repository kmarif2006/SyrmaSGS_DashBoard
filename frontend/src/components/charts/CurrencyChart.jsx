import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { formatINR, CustomTooltip } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-56 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function CurrencyChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-56 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: 0, right: 10, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="Currency" tick={{ fill: '#94a3b8', fontSize: 13, fontWeight: 600 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => formatINR(v)} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={70} />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            return (
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                <p className="text-slate-300 font-bold mb-2">{label}</p>
                {payload.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full" style={{ background: p.fill }} />
                    <span className="text-slate-400">{p.name}:</span>
                    <span className="text-white font-semibold">{formatINR(p.value)}</span>
                  </div>
                ))}
              </div>
            )
          }}
          cursor={{ fill: 'rgba(99,102,241,0.08)' }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
        <Bar dataKey="Original_Spend" name="Original Spend" fill="#6366f1" fillOpacity={0.7} radius={[4, 4, 0, 0]} maxBarSize={56} />
        <Bar dataKey="Converted_INR" name="Converted INR" fill="#10b981" fillOpacity={0.8} radius={[4, 4, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ResponsiveContainer>
  )
}
