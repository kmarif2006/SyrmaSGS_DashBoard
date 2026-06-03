import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function ChartSkeleton() {
  return <div className="h-56 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

const COLORS = ['#10b981', '#ef4444']

export default function DeliveryChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.chart?.length) return <div className="h-56 flex items-center justify-center text-slate-600 text-sm">No delivery data available</div>

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data.chart}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={3}
            dataKey="value"
          >
            {data.chart.map((entry, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} strokeWidth={0} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              return (
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: payload[0].payload.fill }} />
                    <span className="text-slate-200 font-semibold">{payload[0].name}: {payload[0].value.toLocaleString()}</span>
                  </div>
                </div>
              )
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: '#94a3b8' }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex gap-6 mt-1">
        <div className="text-center">
          <p className="text-2xl font-bold text-emerald-400">{data.on_time_pct}%</p>
          <p className="text-xs text-slate-500">On Time</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-red-400">{data.delay_pct}%</p>
          <p className="text-xs text-slate-500">Delayed</p>
        </div>
      </div>
    </div>
  )
}
