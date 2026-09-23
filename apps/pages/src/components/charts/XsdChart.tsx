import EChart, { baseOption, COLORS } from '../EChart'
import { useJsonData } from '../../hooks/useJsonData'

interface XsdPayload {
  available: boolean
  note?: string
  dates: string[]
  xsd_on: (0 | 1)[]
  snapshot?: {
    strategy_id: string
    date: string
    on: boolean
    ticker: string
  }
}

export function XsdChart() {
  const { data, status } = useJsonData<XsdPayload>('viz_xsd_timeline.json')

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="border border-border bg-surface animate-pulse flex items-center justify-center text-muted text-xs" style={{ height: 120 }}>
        Loading…
      </div>
    )
  }

  if (!data || !data.available || data.dates.length === 0) {
    const snap = data?.snapshot
    const state = snap ? (snap.on ? 'ON' : 'OFF') : 'unknown'
    return (
      <div className="border border-border bg-surface px-4 py-4 text-sm text-muted space-y-1">
        <p>No historical XSD ON/OFF timeline published yet.</p>
        {snap && (
          <p>
            Latest snapshot (<code className="text-muted/80">{snap.ticker}</code> · {snap.date?.split(' ')[0]}):{' '}
            <strong className={snap.on ? 'text-up' : 'text-muted'}>{state}</strong>
          </p>
        )}
        {data?.note && <p className="text-xs text-muted/60">{data.note}</p>}
      </div>
    )
  }

  const opt = {
    ...baseOption(),
    grid: { left: 40, right: 16, top: 32, bottom: 32 },
    title: {
      text: 'XSD sleeve ON/OFF',
      left: 0, top: 0,
      textStyle: { fontSize: 12, fontWeight: 600, color: COLORS.body },
    },
    xAxis: {
      type: 'category', data: data.dates,
      axisLabel: { hideOverlap: true, color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.border } },
    },
    yAxis: {
      type: 'value', min: 0, max: 1,
      axisLabel: { formatter: (v: number) => v === 1 ? 'ON' : 'OFF', color: COLORS.muted, fontSize: 11 },
      splitLine: { lineStyle: { color: COLORS.border } },
    },
    series: [
      {
        name: 'XSD ON',
        type: 'bar',
        data: data.xsd_on,
        itemStyle: { color: COLORS.accent, opacity: 0.7, borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 12,
      },
    ],
  }

  return <EChart option={opt} style={{ height: 180 }} />
}
