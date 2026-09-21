import ReactECharts from 'echarts-for-react'

export const COLORS = {
  accent:  '#4f7ef8',
  ink:     '#f0f1f5',
  body:    '#7e8699',
  muted:   '#4a5166',
  border:  '#252836',
  surface: '#121419',
  raised:  '#1a1d26',
  up:      '#22d68e',
  down:    '#f06060',
  // series palette
  series1: '#4f7ef8',
  series2: '#a0aec0',
  series3: '#22d68e',
  series4: '#f06060',
}

// Use a permissive type to avoid ECharts' complex discriminated union constraints
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChartOption = Record<string, any>

export function baseOption(): ChartOption {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: COLORS.body },
    grid: { left: 56, right: 24, top: 48, bottom: 40, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: COLORS.raised,
      borderColor: COLORS.border,
      textStyle: { color: COLORS.ink, fontSize: 12 },
      axisPointer: { lineStyle: { color: COLORS.muted } },
    },
    legend: {
      top: 8,
      textStyle: { color: COLORS.body, fontSize: 12 },
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 4,
    },
    color: [COLORS.series1, COLORS.series2, COLORS.series3, COLORS.series4],
  }
}

interface EChartProps {
  option: ChartOption
  style?: React.CSSProperties
  className?: string
}

export default function EChart({ option, style, className }: EChartProps) {
  return (
    <ReactECharts
      option={option}
      style={{ height: 300, width: '100%', ...style }}
      className={className}
      opts={{ renderer: 'canvas' }}
      notMerge
    />
  )
}
