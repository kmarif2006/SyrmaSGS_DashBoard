import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { formatINR, CHART_COLORS } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-64 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function CompanyTrendChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.data?.length) return <div className="h-64 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  const { data: rows, companies } = data

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={rows} margin={{ left: 0, right: 10, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="Month" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => formatINR(v)} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={70} />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            return (
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                <p className="text-slate-400 mb-2 font-medium">{label}</p>
                {payload.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                    <span className="text-slate-300">CC {p.dataKey}:</span>
                    <span className="text-white font-semibold">{formatINR(p.value)}</span>
                  </div>
                ))}
              </div>
            )
          }}
          cursor={{ stroke: '#475569', strokeDasharray: '4 4' }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
        {companies?.map((cc, i) => (
          <Line
            key={cc}
            type="monotone"
            dataKey={String(cc)}
            name={`CC ${cc}`}
            stroke={CHART_COLORS[i % CHART_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 2, fill: CHART_COLORS[i % CHART_COLORS.length] }}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
