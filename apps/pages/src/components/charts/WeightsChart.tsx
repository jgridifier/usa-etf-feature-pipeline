import EChart, { baseOption, COLORS } from '../EChart'
import { useJsonData } from '../../hooks/useJsonData'

interface WeightsPayload {
  books: {
    [bookId: string]: {
      label: string
      asof?: string
      eval_date?: string
      f?: number
      weights: { [ticker: string]: number }
    }
  }
}

function ChartSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-surface animate-pulse flex items-center justify-center text-muted text-xs" style={{ height: 200 }}>
      Loading…
    </div>
  )
}
function ChartError({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface flex items-center justify-center text-muted text-xs" style={{ height: 200 }}>
      {msg}
    </div>
  )
}

const BAR_COLORS = [COLORS.accent, COLORS.series2, COLORS.muted, COLORS.up, COLORS.down]

export function WeightsChart({ bookId }: { bookId: string }) {
  const { data, status, error } = useJsonData<WeightsPayload>('viz_weights.json')

  if (status === 'loading' || status === 'idle') return <ChartSkeleton />
  if (status === 'error' || !data) return <ChartError msg={error ?? 'Failed to load'} />

  const book = data.books?.[bookId]
  if (!book) return <ChartError msg={`No data for ${bookId}`} />

  const tickers = Object.keys(book.weights)
  const values = Object.values(book.weights).map(v => +(v * 100).toFixed(1))

  const opt = {
    ...baseOption(),
    grid: { left: 40, right: 16, top: 24, bottom: 24 },
    xAxis: {
      type: 'category', data: tickers,
      axisLabel: { color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
    },
    yAxis: {
      type: 'value', max: 100,
      axisLabel: { formatter: (v: number) => v + '%', color: COLORS.muted, fontSize: 11 },
      splitLine: { lineStyle: { color: COLORS.border } },
    },
    series: [
      {
        name: 'Weight',
        type: 'bar',
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: BAR_COLORS[i % BAR_COLORS.length], borderRadius: [3, 3, 0, 0] },
        })),
        label: {
          show: true, position: 'top',
          formatter: (p: { value: number }) => p.value + '%',
          color: COLORS.body, fontSize: 11,
        },
        barMaxWidth: 40,
      },
    ],
    tooltip: {
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0]
        return `<span style="color:${COLORS.ink}">${p.name}: ${p.value}%</span>`
      },
    },
  }

  return <EChart option={opt} style={{ height: 200 }} />
}
