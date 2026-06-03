import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'
import { formatINR, CustomTooltip } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-64 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function MonthlyTrendChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-64 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ left: 0, right: 10, top: 10, bottom: 4 }}>
        <defs>
          <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="Month" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => formatINR(v)} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={75} />
        <Tooltip content={<CustomTooltip formatter={v => formatINR(v)} />} cursor={{ stroke: '#6366f1', strokeWidth: 1, strokeDasharray: '4 4' }} />
        <Area
          type="monotone"
          dataKey="Total_Spend_INR"
          name="Spend INR"
          stroke="#6366f1"
          strokeWidth={2.5}
          fill="url(#spendGrad)"
          dot={{ fill: '#6366f1', r: 3, strokeWidth: 0 }}
          activeDot={{ r: 5, fill: '#6366f1', stroke: '#312e81', strokeWidth: 2 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
