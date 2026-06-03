import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { formatINR, CHART_COLORS, CustomTooltip } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-56 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

export default function PlantChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-56 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: 0, right: 10, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="Plant" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={v => formatINR(v)} tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} width={70} />
        <Tooltip content={<CustomTooltip formatter={v => formatINR(v)} />} cursor={{ fill: 'rgba(6,182,212,0.08)' }} />
        <Bar dataKey="Total_Spend_INR" name="Spend INR" radius={[6, 6, 0, 0]} maxBarSize={56}>
          {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[(i + 2) % CHART_COLORS.length]} fillOpacity={0.85} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
