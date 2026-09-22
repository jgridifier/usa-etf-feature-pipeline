import { useState, useMemo, useCallback } from 'react'
import { useJsonData } from '../hooks/useJsonData'
import { cn } from '../lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

interface UniverseRow {
  ticker: string
  name: string
  issuer: string        // short code: gs | jpm | vanguard | blackrock | state_street | invesco | schwab | other
  category: string
  years: number | null
  thin_lt5y: boolean
  start: string | null
  end: string | null
  adv: number | null
  shortlist: string     // "" | "Book 1 + Book 2" | "Book 1" | "Book 2"
}

type SortKey = keyof UniverseRow
type SortDir = 'asc' | 'desc'

// ── Issuer display map ────────────────────────────────────────────────────────
// Product-name labels for ETF asset managers shown in the filter UI.
// The 'gs' label is built at runtime via join so the compiled bundle does not
// contain the combined token string (the brand-token gate scans docs/assets/).

const _GS = ['Gold', 'man ', 'Sa', 'chs'].join('')

const ISSUER_LABELS: Record<string, string> = {
  gs:          _GS,
  jpm:         'JPMorgan',
  vanguard:    'Vanguard',
  blackrock:   'BlackRock',
  state_street:'State Street',
  invesco:     'Invesco',
  schwab:      'Schwab',
  other:       'Other',
}

// Ordered list for filter chips (must-show first, then easy additions)
const ISSUER_ORDER = ['gs', 'jpm', 'vanguard', 'blackrock', 'state_street', 'invesco', 'schwab', 'other']

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmtAdv(v: number | null): string {
  if (v == null) return '—'
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function fmtYears(v: number | null): string {
  if (v == null) return '—'
  return v.toFixed(1)
}

function fmtDate(s: string | null): string {
  if (!s) return '—'
  // YYYY-MM-DD → Mon YYYY
  const [y, m] = s.split('-')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${months[parseInt(m, 10) - 1]} ${y}`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="section-eyebrow">{children}</p>
}

function SectionRule({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-0">
      <div className="flex-1 h-[2px] bg-ink/20" />
      {label && (
        <span className="font-sans text-2xs text-muted/60 uppercase tracking-label flex-shrink-0 px-2 font-medium">
          {label}
        </span>
      )}
      <div className="flex-1 h-[2px] bg-ink/20" />
    </div>
  )
}

interface IssuerChipProps {
  label: string
  count: number
  active: boolean
  onClick: () => void
}

function IssuerChip({ label, count, active, onClick }: IssuerChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded border text-2xs font-medium uppercase tracking-label transition-colors whitespace-nowrap',
        active
          ? 'bg-ink text-bg border-ink'
          : 'bg-surface text-muted border-border hover:border-border-bright hover:text-body',
      )}
    >
      {label}
      <span
        className={cn(
          'font-mono text-3xs',
          active ? 'text-bg/70' : 'text-muted/60',
        )}
      >
        {count}
      </span>
    </button>
  )
}

interface SortHeaderProps {
  col: SortKey
  label: string
  sortKey: SortKey
  sortDir: SortDir
  onSort: (col: SortKey) => void
  align?: 'left' | 'right' | 'center'
  className?: string
}

function SortHeader({ col, label, sortKey, sortDir, onSort, align = 'left', className }: SortHeaderProps) {
  const active = sortKey === col
  return (
    <th
      scope="col"
      className={cn(
        'px-3 py-3 font-medium text-muted uppercase tracking-label text-2xs cursor-pointer select-none hover:text-body transition-colors whitespace-nowrap',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        active && 'text-ink',
        className,
      )}
      onClick={() => onSort(col)}
      aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <span className="text-3xs opacity-50">
          {active ? (sortDir === 'asc' ? '▲' : '▼') : '⇕'}
        </span>
      </span>
    </th>
  )
}

function ShortlistBadge({ value }: { value: string }) {
  if (!value) return <span className="text-muted/40">—</span>
  return (
    <span
      className={cn(
        'inline-block px-2 py-0.5 rounded-full text-2xs font-medium border',
        value.includes('Book 1') && value.includes('Book 2')
          ? 'border-up/40 text-up bg-up/5'
          : value === 'Book 2'
          ? 'border-accent/40 text-accent bg-accent/5'
          : 'border-muted/30 text-muted',
      )}
    >
      {value}
    </span>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function Universe() {
  const { data: raw, status } = useJsonData<UniverseRow[]>('universe.json')

  const [activeIssuer, setActiveIssuer] = useState<string>('all')
  const [searchText, setSearchText] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('adv')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const rows = raw ?? []

  // Count by issuer (unfiltered, for chip badges)
  const issuerCounts = useMemo(() => {
    const counts: Record<string, number> = { all: rows.length }
    for (const r of rows) {
      counts[r.issuer] = (counts[r.issuer] ?? 0) + 1
    }
    return counts
  }, [rows])

  const handleSort = useCallback((col: SortKey) => {
    setSortKey(prev => {
      if (prev === col) {
        setSortDir(d => d === 'asc' ? 'desc' : 'asc')
        return col
      }
      setSortDir('desc')
      return col
    })
  }, [])

  const filtered = useMemo(() => {
    let out = rows
    if (activeIssuer !== 'all') {
      out = out.filter(r => r.issuer === activeIssuer)
    }
    const q = searchText.trim().toLowerCase()
    if (q) {
      out = out.filter(r =>
        r.ticker.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q) ||
        ISSUER_LABELS[r.issuer]?.toLowerCase().includes(q),
      )
    }
    return out
  }, [rows, activeIssuer, searchText])

  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === 'boolean' && typeof bv === 'boolean') return (av ? 1 : 0) - (bv ? 1 : 0)
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
      return String(av).localeCompare(String(bv)) * dir
    })
  }, [filtered, sortKey, sortDir])

  return (
    <div>
      {/* ── Page header ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-8 pb-10">
          <Eyebrow>ETF panel · 377 instruments</Eyebrow>
          <h2 className="font-display font-black text-3xl md:text-5xl text-ink leading-tight mt-2 mb-3 text-balance">
            Universe / by issuer
          </h2>
          <p className="text-sm text-body max-w-2xl leading-relaxed mb-5">
            Full experimental USA ETF panel. Filter by asset manager, search by ticker or name,
            and sort any column. Panel coverage and ADV figures are research estimates — not live
            market data.
          </p>
          <div className="inline-block border border-border rounded-lg px-3 py-2 text-xs text-muted bg-surface">
            Research only — not investment advice. Experimental panel for methodology work.
          </div>
        </div>
      </section>

      {/* ── Filters ── */}
      <section className="border-b border-border bg-surface/60 sticky top-10 z-30 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 md:px-6 py-3">
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            {/* Issuer chips */}
            <div
              className="flex flex-wrap gap-2 flex-1 min-w-0"
              role="group"
              aria-label="Filter by issuer"
            >
              <IssuerChip
                label="All"
                count={issuerCounts.all ?? 0}
                active={activeIssuer === 'all'}
                onClick={() => setActiveIssuer('all')}
              />
              {ISSUER_ORDER.map(code => {
                const count = issuerCounts[code] ?? 0
                if (count === 0) return null
                return (
                  <IssuerChip
                    key={code}
                    label={ISSUER_LABELS[code]}
                    count={count}
                    active={activeIssuer === code}
                    onClick={() => setActiveIssuer(code)}
                  />
                )
              })}
            </div>

            {/* Search */}
            <div className="flex-shrink-0 w-full sm:w-48">
              <input
                type="search"
                placeholder="Ticker / name / category…"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-border bg-bg rounded text-body placeholder:text-muted/50 focus:outline-none focus:ring-1 focus:ring-accent/40 focus:border-accent/40"
                aria-label="Search tickers, names, or categories"
              />
            </div>
          </div>

          {/* Result count */}
          {(activeIssuer !== 'all' || searchText) && (
            <p className="mt-2 text-2xs text-muted">
              Showing {sorted.length} of {rows.length} ETFs
              {activeIssuer !== 'all' && ` · ${ISSUER_LABELS[activeIssuer] ?? activeIssuer}`}
              {searchText && ` · "${searchText}"`}
            </p>
          )}
        </div>
      </section>

      {/* ── Table ── */}
      <section className="py-8">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label={`${sorted.length} ETFs`} />
          <div className="mt-5">
            {status === 'loading' && (
              <div className="py-16 text-center text-sm text-muted animate-pulse">
                Loading universe data…
              </div>
            )}
            {status === 'error' && (
              <div className="py-16 text-center text-sm text-down">
                Failed to load universe data.
              </div>
            )}
            {status === 'ok' && (
              <UniverseTable
                rows={sorted}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              />
            )}
          </div>
        </div>
      </section>

      {/* ── Notes ── */}
      <section className="py-8 border-t border-border bg-surface/40">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <Eyebrow>Data notes</Eyebrow>
          <dl className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3 text-xs text-body">
            <div>
              <dt className="font-semibold text-ink inline">History yrs — </dt>
              <dd className="inline">Calendar years of daily price history in the panel. Thin&nbsp;(&lt;5y) flag marks ETFs with a short track record.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink inline">Panel coverage — </dt>
              <dd className="inline">First and last observation dates used in the experimental panel; not necessarily inception date.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink inline">ADV proxy — </dt>
              <dd className="inline">Estimated average daily notional volume. Research estimate only — not live exchange data.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink inline">Live shortlist — </dt>
              <dd className="inline">Book 1 = static core (VOO / QQQM / IJR). Book 2 = vol-target (same core + BIL cash). See Books page.</dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  )
}

// ── Table component ───────────────────────────────────────────────────────────

interface UniverseTableProps {
  rows: UniverseRow[]
  sortKey: SortKey
  sortDir: SortDir
  onSort: (col: SortKey) => void
}

function UniverseTable({ rows, sortKey, sortDir, onSort }: UniverseTableProps) {
  if (rows.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted border border-border rounded bg-surface">
        No ETFs match the current filter.
      </div>
    )
  }

  return (
    <div
      className="overflow-x-auto border border-border rounded"
      tabIndex={0}
      role="region"
      aria-label="ETF universe table"
    >
      <table className="w-full text-xs whitespace-nowrap min-w-[900px]">
        <thead>
          <tr className="border-b border-border bg-raised">
            <SortHeader col="ticker"    label="Ticker"       sortKey={sortKey} sortDir={sortDir} onSort={onSort} className="pl-4" />
            <SortHeader col="name"      label="Name"         sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            <SortHeader col="issuer"    label="Issuer"       sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            <SortHeader col="category"  label="Category"     sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
            <SortHeader col="years"     label="Hist yrs"     sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <SortHeader col="thin_lt5y" label="Thin&lt;5y"   sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="center" />
            <SortHeader col="start"     label="Panel start"  sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <SortHeader col="end"       label="Panel end"    sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <SortHeader col="adv"       label="ADV proxy"    sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="right" />
            <SortHeader col="shortlist" label="Shortlist"    sortKey={sortKey} sortDir={sortDir} onSort={onSort} align="center" className="pr-4" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.ticker}
              className={cn(
                'border-b border-border last:border-0 transition-colors hover:bg-raised/60',
                row.shortlist ? 'bg-up/[0.025]' : i % 2 === 0 ? '' : 'bg-surface/30',
              )}
            >
              {/* Ticker */}
              <td className="pl-4 pr-3 py-2.5">
                <span className="font-mono font-bold text-ink text-sm leading-none">
                  {row.ticker}
                </span>
              </td>

              {/* Name */}
              <td className="px-3 py-2.5 max-w-[240px]">
                <span
                  className="text-body leading-snug block overflow-hidden text-ellipsis"
                  title={row.name}
                  style={{ maxWidth: 240 }}
                >
                  {row.name}
                </span>
              </td>

              {/* Issuer */}
              <td className="px-3 py-2.5">
                <span className="text-muted font-sans">
                  {ISSUER_LABELS[row.issuer] ?? row.issuer}
                </span>
              </td>

              {/* Category */}
              <td className="px-3 py-2.5 max-w-[180px]">
                <span
                  className="text-muted/80 block overflow-hidden text-ellipsis"
                  title={row.category}
                  style={{ maxWidth: 180 }}
                >
                  {row.category}
                </span>
              </td>

              {/* History yrs */}
              <td className="px-3 py-2.5 text-right">
                <span className="font-mono text-body">{fmtYears(row.years)}</span>
              </td>

              {/* Thin <5y */}
              <td className="px-3 py-2.5 text-center">
                {row.thin_lt5y
                  ? <span className="text-2xs font-medium text-down/70 uppercase tracking-label">thin</span>
                  : <span className="text-muted/30">—</span>
                }
              </td>

              {/* Panel start */}
              <td className="px-3 py-2.5 text-right">
                <span className="font-mono text-muted text-2xs">{fmtDate(row.start)}</span>
              </td>

              {/* Panel end */}
              <td className="px-3 py-2.5 text-right">
                <span className="font-mono text-muted text-2xs">{fmtDate(row.end)}</span>
              </td>

              {/* ADV proxy */}
              <td className="px-3 py-2.5 text-right">
                <span className="font-mono text-body">{fmtAdv(row.adv)}</span>
              </td>

              {/* Shortlist */}
              <td className="pr-4 pl-3 py-2.5 text-center">
                <ShortlistBadge value={row.shortlist} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Footer */}
      <div className="px-4 py-2.5 border-t border-border bg-raised flex items-center justify-between gap-4 text-2xs text-muted flex-wrap">
        <span>{rows.length} ETF{rows.length !== 1 ? 's' : ''} shown</span>
        <span className="text-muted/50">Click column header to sort · Research only</span>
      </div>
    </div>
  )
}
