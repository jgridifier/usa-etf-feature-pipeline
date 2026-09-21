import { useJsonData } from '../hooks/useJsonData'
import { pct, num } from '../lib/utils'

interface CompRow {
  strategy_id: string
  label: string
  AnnReturn: number
  AnnVol: number
  MaxDD: number
  Sharpe_rf0: number
  NW_t_vs_option_a: number
  turnover_per_year: number
  n_months: number
  start_date: string
  end_date: string
  stance?: string
}

interface CompPayload {
  rows: CompRow[]
  source?: string
}

export function ComparisonTable() {
  const { data, status, error } = useJsonData<CompPayload>('viz_comparison.json')

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-muted animate-pulse">
        Loading comparison data…
      </div>
    )
  }
  if (status === 'error' || !data) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4 text-sm text-muted">
        {error ?? 'Failed to load comparison data'}
      </div>
    )
  }

  const rows = data.rows ?? []

  return (
    <div
      className="overflow-x-auto rounded-xl border border-border"
      tabIndex={0}
      role="region"
      aria-label="Strategy comparison"
    >
      <table className="w-full text-xs whitespace-nowrap">
        <thead>
          <tr className="border-b border-border bg-raised text-left">
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs">Strategy</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">Ann. Return</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">Ann. Vol</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">Max DD</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">Sharpe rf0</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">NW t vs A</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">TO/yr</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">Mo.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.strategy_id} className="border-b border-border last:border-0 hover:bg-raised transition-colors">
              <td className="px-4 py-3">
                <span className="font-medium text-ink">{row.label ?? row.strategy_id}</span>
                {row.stance && <span className="ml-2 text-muted/60 text-2xs">({row.stance})</span>}
              </td>
              <td className="px-4 py-3 text-right font-mono text-ink">{pct(row.AnnReturn)}</td>
              <td className="px-4 py-3 text-right font-mono text-body">{pct(row.AnnVol)}</td>
              <td className="px-4 py-3 text-right font-mono text-down">{pct(row.MaxDD)}</td>
              <td className="px-4 py-3 text-right font-mono text-ink">{num(row.Sharpe_rf0)}</td>
              <td className="px-4 py-3 text-right font-mono text-body">{num(row.NW_t_vs_option_a)}</td>
              <td className="px-4 py-3 text-right font-mono text-muted">{pct(row.turnover_per_year)}</td>
              <td className="px-4 py-3 text-right font-mono text-muted">{row.n_months}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.source && (
        <div className="px-4 py-2 text-2xs text-muted bg-raised border-t border-border">
          Source: <code>{data.source}</code>
        </div>
      )}
    </div>
  )
}
