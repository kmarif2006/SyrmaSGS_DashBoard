import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'
import { formatINR, CHART_COLORS } from '../../lib/utils'

function ChartSkeleton() {
  return <div className="h-64 bg-slate-800/50 rounded-xl animate-pulse flex items-center justify-center"><p className="text-slate-600 text-sm">Loading...</p></div>
}

function CustomContent({ x, y, width, height, name, value, index }) {
  const fontSize = Math.min(13, Math.max(9, width / 8))
  if (width < 30 || height < 20) return null
  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        rx={6}
        fill={CHART_COLORS[index % CHART_COLORS.length]}
        fillOpacity={0.75}
        stroke={CHART_COLORS[index % CHART_COLORS.length]}
        strokeOpacity={0.4}
        strokeWidth={1}
      />
      {width > 50 && height > 30 && (
        <>
          <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#fff" fontSize={fontSize} fontWeight={600}>
            {name?.length > 12 ? name.slice(0, 12) + '…' : name}
          </text>
          <text x={x + width / 2} y={y + height / 2 + 10} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={Math.max(8, fontSize - 2)}>
            {formatINR(value)}
          </text>
        </>
      )}
    </g>
  )
}

export default function TreemapChart({ data, isLoading }) {
  if (isLoading) return <ChartSkeleton />
  if (!data?.length) return <div className="h-64 flex items-center justify-center text-slate-600 text-sm">No data available</div>

  return (
    <ResponsiveContainer width="100%" height={300}>
      <Treemap
        data={data}
        dataKey="value"
        nameKey="name"
        content={<CustomContent />}
        isAnimationActive
      >
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0]?.payload
            return (
              <div className="bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs shadow-2xl">
                <p className="text-slate-200 font-semibold mb-1">{d?.name}</p>
                <p className="text-white">Spend: <span className="font-bold text-indigo-300">{formatINR(d?.value)}</span></p>
                <p className="text-slate-400">Items: {d?.count?.toLocaleString()}</p>
              </div>
            )
          }}
        />
      </Treemap>
    </ResponsiveContainer>
  )
}
