import EChart, { baseOption, COLORS } from '../EChart'
import type { ChartOption } from '../EChart'
import { useJsonData } from '../../hooks/useJsonData'
import { pct } from '../../lib/utils'

interface EquityPayload {
  dates: string[]
  equity: {
    vol_target_option_a: number[]
    static_option_a: number[]
  }
  drawdown: {
    vol_target_option_a: number[]
    static_option_a: number[]
  }
  max_dd: {
    vol_target_option_a: number
    static_option_a: number
  }
}

function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div
      className="border border-border bg-surface animate-pulse flex items-center justify-center text-muted text-xs"
      style={{ height }}
    >
      Loading chart…
    </div>
  )
}

function ChartError({ msg, height = 300 }: { msg: string; height?: number }) {
  return (
    <div
      className="border border-border bg-surface flex items-center justify-center text-muted text-xs"
      style={{ height }}
    >
      {msg}
    </div>
  )
}

export function EquityChart() {
  const { data, status, error } = useJsonData<EquityPayload>('viz_equity_drawdown.json')

  if (status === 'loading' || status === 'idle') return <ChartSkeleton height={300} />
  if (status === 'error' || !data) return <ChartError msg={error ?? 'Failed to load data'} height={300} />

  const opt: ChartOption = {
    ...baseOption(),
    title: {
      text: 'Cumulative wealth (OOS)',
      left: 0, top: 0,
      textStyle: { fontSize: 12, fontWeight: 600, color: COLORS.body },
    },
    xAxis: { type: 'category', data: data.dates, axisLabel: { hideOverlap: true, color: COLORS.muted, fontSize: 11 }, axisLine: { lineStyle: { color: COLORS.border } } },
    yAxis: { type: 'value', scale: true, name: 'Wealth', nameTextStyle: { color: COLORS.muted }, axisLabel: { color: COLORS.muted, fontSize: 11 }, splitLine: { lineStyle: { color: COLORS.border } } },
    series: [
      { name: 'Vol-target (Book 2)', type: 'line', showSymbol: false, data: data.equity.vol_target_option_a, lineStyle: { width: 2, color: COLORS.series1 }, itemStyle: { color: COLORS.series1 } },
      { name: 'Static Option A', type: 'line', showSymbol: false, data: data.equity.static_option_a, lineStyle: { width: 2, color: COLORS.series2 }, itemStyle: { color: COLORS.series2 } },
    ],
  }

  return <EChart option={opt} style={{ height: 300 }} />
}

export function DrawdownChart() {
  const { data, status, error } = useJsonData<EquityPayload>('viz_equity_drawdown.json')

  if (status === 'loading' || status === 'idle') return <ChartSkeleton height={260} />
  if (status === 'error' || !data) return <ChartError msg={error ?? 'Failed to load data'} height={260} />

  const opt: ChartOption = {
    ...baseOption(),
    title: {
      text: `Drawdown · MaxDD vt ${pct(data.max_dd?.vol_target_option_a)} vs A ${pct(data.max_dd?.static_option_a)}`,
      left: 0, top: 0,
      textStyle: { fontSize: 12, fontWeight: 600, color: COLORS.body },
    },
    xAxis: { type: 'category', data: data.dates, axisLabel: { hideOverlap: true, color: COLORS.muted, fontSize: 11 }, axisLine: { lineStyle: { color: COLORS.border } } },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => (100 * v).toFixed(0) + '%', color: COLORS.muted, fontSize: 11 }, splitLine: { lineStyle: { color: COLORS.border } } },
    series: [
      {
        name: 'Vol-target (Book 2)',
        type: 'line', showSymbol: false,
        data: data.drawdown.vol_target_option_a,
        lineStyle: { width: 2, color: COLORS.down },
        areaStyle: { color: COLORS.down, opacity: 0.1 },
        itemStyle: { color: COLORS.down },
      },
      {
        name: 'Static Option A',
        type: 'line', showSymbol: false,
        data: data.drawdown.static_option_a,
        lineStyle: { width: 2, color: COLORS.muted },
        itemStyle: { color: COLORS.muted },
      },
    ],
  }

  return <EChart option={opt} style={{ height: 260 }} />
}
