import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts'
import { formatINR, truncate, CHART_COLORS, CustomTooltip } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-64 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function ParetoChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-64 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ left: 0, right: 10, top: 4, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="Supplier"
          tick={{ fill: '#94a3b8', fontSize: 10 }}
          tickFormatter={v => truncate(v, 14)}
          angle={-35}
          textAnchor="end"
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          yAxisId="left"
          tickFormatter={v => formatINR(v)}
          tick={{ fill: '#64748b', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={70}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          domain={[0, 100]}
          tickFormatter={v => `${v}%`}
          tick={{ fill: '#64748b', fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            return (
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                <p className="text-slate-400 mb-2 font-medium">{truncate(label, 30)}</p>
                {payload.map((p, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
                    <span className="text-slate-300">{p.name}:</span>
                    <span className="text-white font-semibold">
                      {p.name === 'Cumulative %' ? `${p.value}%` : formatINR(p.value)}
                    </span>
                  </div>
                ))}
              </div>
            )
          }}
          cursor={{ fill: 'rgba(99,102,241,0.08)' }}
        />
        <Bar yAxisId="left" dataKey="Spend_INR" name="Spend INR" radius={[4, 4, 0, 0]} maxBarSize={48}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.85} />)}
        </Bar>
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="Cumulative_Pct"
          name="Cumulative %"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={{ fill: '#f59e0b', r: 3 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
