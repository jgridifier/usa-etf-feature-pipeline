import EChart, { baseOption, COLORS } from '../EChart'
import { useJsonData } from '../../hooks/useJsonData'

interface FtPayload {
  dates: string[]
  f_t: number[]
  w_bil: number[]
  mean_f?: number
  pct_months_f_lt_1?: number
}

function ChartSkeleton({ height = 220 }: { height?: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface animate-pulse flex items-center justify-center text-muted text-xs" style={{ height }}>
      Loading…
    </div>
  )
}
function ChartError({ msg, height = 220 }: { msg: string; height?: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface flex items-center justify-center text-muted text-xs" style={{ height }}>
      {msg}
    </div>
  )
}

const AXIS_STYLE = {
  axisLabel: { color: COLORS.muted, fontSize: 11 },
  axisLine: { lineStyle: { color: COLORS.border } },
  splitLine: { lineStyle: { color: COLORS.border } },
}

export function FtChart() {
  const { data, status, error } = useJsonData<FtPayload>('viz_ft_history.json')

  if (status === 'loading' || status === 'idle') return <ChartSkeleton />
  if (status === 'error' || !data) return <ChartError msg={error ?? 'Failed to load'} />

  const meanF = data.mean_f != null ? ` · mean f = ${data.mean_f.toFixed(2)}` : ''
  const pctLt1 = data.pct_months_f_lt_1 != null ? ` · months f<1: ${(100 * data.pct_months_f_lt_1).toFixed(0)}%` : ''

  const opt = {
    ...baseOption(),
    grid: { left: 48, right: 16, top: 40, bottom: 40 },
    title: {
      text: `Scale factor f_t${meanF}${pctLt1}`,
      left: 0, top: 0,
      textStyle: { fontSize: 12, fontWeight: 600, color: COLORS.body },
    },
    xAxis: {
      type: 'category', data: data.dates,
      axisLabel: { hideOverlap: true, color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', min: 0, max: 1.05,
      axisLabel: { formatter: (v: number) => v.toFixed(2), color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
      splitLine: { lineStyle: { color: COLORS.border } },
    },
    series: [
      {
        name: 'f_t (scale)',
        type: 'bar',
        data: data.f_t,
        itemStyle: { color: COLORS.accent, opacity: 0.85, borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 16,
      },
    ],
  }

  return <EChart option={opt} style={{ height: 220 }} />
}

export function WBilChart() {
  const { data, status, error } = useJsonData<FtPayload>('viz_ft_history.json')

  if (status === 'loading' || status === 'idle') return <ChartSkeleton />
  if (status === 'error' || !data) return <ChartError msg={error ?? 'Failed to load'} />

  const opt = {
    ...baseOption(),
    grid: { left: 48, right: 16, top: 40, bottom: 40 },
    title: {
      text: 'BIL weight w_BIL = 1 − f_t',
      left: 0, top: 0,
      textStyle: { fontSize: 12, fontWeight: 600, color: COLORS.body },
    },
    xAxis: {
      type: 'category', data: data.dates,
      axisLabel: { hideOverlap: true, color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value', min: 0, max: 1.05,
      axisLabel: { formatter: (v: number) => (100 * v).toFixed(0) + '%', color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
      splitLine: { lineStyle: { color: COLORS.border } },
    },
    series: [
      {
        name: 'BIL weight',
        type: 'bar',
        data: data.w_bil,
        itemStyle: { color: COLORS.muted, opacity: 0.7, borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 16,
      },
    ],
  }

  return <EChart option={opt} style={{ height: 220 }} />
}
