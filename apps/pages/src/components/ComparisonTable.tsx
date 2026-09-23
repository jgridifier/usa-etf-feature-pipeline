import { useJsonData } from '../hooks/useJsonData'
import { pct, num } from '../lib/utils'

interface CompRow {
  strategy_id: string
  label: string
  AnnReturn: number
  AnnVol: number
  MaxDD: number
  Sharpe_rf0: number
  NW_t_vs_option_a: number | null
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

/** Order: live books first (static_option_a, vol_target_option_a), then optional sleeve last */
function sortRows(rows: CompRow[]): { live: CompRow[]; sleeve: CompRow[] } {
  const BOOK_ORDER = ['static_option_a', 'vol_target_option_a']
  const live: CompRow[] = []
  const sleeve: CompRow[] = []

  for (const id of BOOK_ORDER) {
    const row = rows.find(r => r.strategy_id === id)
    if (row) live.push(row)
  }
  for (const row of rows) {
    if (!BOOK_ORDER.includes(row.strategy_id)) sleeve.push(row)
  }
  return { live, sleeve }
}

function TableRow({ row, dim = false }: { row: CompRow; dim?: boolean }) {
  return (
    <tr className={`border-b border-border last:border-0 transition-colors ${dim ? 'opacity-50 hover:opacity-70' : 'hover:bg-raised'}`}>
      <td className="px-4 py-3">
        <span className={`font-medium ${dim ? 'text-muted' : 'text-ink'}`}>{row.label ?? row.strategy_id}</span>
        {row.stance && (
          <span className={`ml-2 text-2xs ${dim ? 'text-muted/40' : 'text-muted/60'}`}>({row.stance})</span>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono text-ink">{pct(row.AnnReturn)}</td>
      <td className="px-4 py-3 text-right font-mono text-body">{pct(row.AnnVol)}</td>
      <td className="px-4 py-3 text-right font-mono text-down">{pct(row.MaxDD)}</td>
      <td className="px-4 py-3 text-right font-mono text-ink">{num(row.Sharpe_rf0)}</td>
      <td className="px-4 py-3 text-right font-mono text-body">{num(row.NW_t_vs_option_a)}</td>
      <td className="px-4 py-3 text-right font-mono text-muted">{pct(row.turnover_per_year)}</td>
      <td className="px-4 py-3 text-right font-mono text-muted">{row.n_months}</td>
    </tr>
  )
}

export function ComparisonTable() {
  const { data, status, error } = useJsonData<CompPayload>('viz_comparison.json')

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="border border-border bg-surface p-4 text-sm text-muted animate-pulse">
        Loading comparison data…
      </div>
    )
  }
  if (status === 'error' || !data) {
    return (
      <div className="border border-border bg-surface p-4 text-sm text-muted">
        {error ?? 'Failed to load comparison data'}
      </div>
    )
  }

  const { live, sleeve } = sortRows(data.rows ?? [])

  const headers = [
    { key: 'Strategy', align: 'left' },
    { key: 'Ann. Return', align: 'right' },
    { key: 'Ann. Vol', align: 'right' },
    { key: 'Max DD', align: 'right' },
    { key: 'Sharpe rf0', align: 'right' },
    { key: 'NW t vs A', align: 'right' },
    { key: 'TO/yr', align: 'right' },
    { key: 'Mo.', align: 'right' },
  ]

  return (
    <div>
      {/* Live books table */}
      <div
        className="overflow-x-auto border border-border mb-3"
        tabIndex={0}
        role="region"
        aria-label="Strategy comparison — live books"
      >
        <table className="w-full text-xs whitespace-nowrap">
          <thead>
            <tr className="border-b border-border bg-raised text-left">
              {headers.map(h => (
                <th
                  key={h.key}
                  className={`px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs ${h.align === 'right' ? 'text-right' : ''}`}
                >
                  {h.key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {live.map(row => (
              <TableRow key={row.strategy_id} row={row} />
            ))}
          </tbody>
        </table>
        {data.source && (
          <div className="px-4 py-2 text-2xs text-muted bg-raised border-t border-border">
            Source: <code>{data.source}</code> · Live books only
          </div>
        )}
      </div>

      {/* XSD sleeve — separate, clearly subordinate */}
      {sleeve.length > 0 && (
        <div
          className="overflow-x-auto border border-dashed border-border/60 opacity-60"
          tabIndex={0}
          role="region"
          aria-label="Optional gated sleeve — not a live book"
        >
          <div className="px-4 py-2.5 bg-raised border-b border-border/60 space-y-0.5">
            <span className="text-2xs text-muted/70 uppercase tracking-label block">Optional gated sleeve (default OFF) — not a peer to Books 1–2</span>
            <span className="text-2xs text-down/70 block">
              ⚠ Higher AnnReturn or NW t here is <strong>not a promote signal</strong> — sleeve default is OFF and XSD is never a Book-3 candidate.
            </span>
          </div>
          <table className="w-full text-xs whitespace-nowrap">
            <thead>
              <tr className="border-b border-border/60 bg-raised/50 text-left">
                {headers.map(h => (
                  <th
                    key={h.key}
                    className={`px-4 py-3 font-medium text-muted/60 uppercase tracking-wider text-2xs ${h.align === 'right' ? 'text-right' : ''}`}
                  >
                    {h.key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sleeve.map(row => (
                <TableRow key={row.strategy_id} row={row} dim />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
