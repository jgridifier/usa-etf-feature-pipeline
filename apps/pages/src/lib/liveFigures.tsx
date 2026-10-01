/**
 * Live-book figures for prose copy.
 *
 * Every return / Sharpe figure in the Books, Home and Runs prose is read from
 * docs/data/live_figures.json, which scripts/build_pages.py writes from the
 * refreshed live-book outputs in data/processed/live/ (and the live fields of
 * data/processed/cash_null_audit/site_sharpe.json, which are computed from the
 * same files). Formatting happens here, at render time. The rounding rules below
 * are mirrored by tests/test_live_figures.py, which renders the built pages and
 * checks every [data-live-figure] span against the live outputs.
 */
import { useEffect, useState } from 'react'
import { dataUrl } from './utils'

export type LiveBook = {
  ann_return: number
  ann_vol: number
  max_dd: number
  sharpe_exbil: number
  sharpe_rf0: number
}

export type LiveFigures = {
  asof: string
  n_months: number
  window: string
  books: { book1: LiveBook; book2: LiveBook; vt: LiveBook }
}

export type LiveKey =
  | 'book1.return' | 'book2.return' | 'vt.return'
  | 'vt.return.whole'
  | 'book1.exbil' | 'book2.exbil' | 'vt.exbil'
  | 'book1.rf0' | 'book2.rf0' | 'vt.rf0'
  | 'gap.points'

const pct1 = (x: number) => `${(x * 100).toFixed(1)}%`

/** Return gap VT − Book 2, in percentage points (unrounded). */
export function returnGapPoints(f: LiveFigures): number {
  return (f.books.vt.ann_return - f.books.book2.ann_return) * 100
}

export function formatLive(k: LiveKey, f: LiveFigures): string {
  const b = f.books
  switch (k) {
    case 'book1.return': return pct1(b.book1.ann_return)
    case 'book2.return': return pct1(b.book2.ann_return)
    case 'vt.return': return pct1(b.vt.ann_return)
    case 'vt.return.whole': return `${Math.round(b.vt.ann_return * 100)}%`
    case 'book1.exbil': return b.book1.sharpe_exbil.toFixed(2)
    case 'book2.exbil': return b.book2.sharpe_exbil.toFixed(2)
    case 'vt.exbil': return b.vt.sharpe_exbil.toFixed(2)
    case 'book1.rf0': return b.book1.sharpe_rf0.toFixed(2)
    case 'book2.rf0': return b.book2.sharpe_rf0.toFixed(2)
    case 'vt.rf0': return b.vt.sharpe_rf0.toFixed(3)
    case 'gap.points': {
      const n = Math.round(returnGapPoints(f))
      return `${n} point${n === 1 ? '' : 's'}`
    }
  }
}

let cache: Promise<LiveFigures> | null = null
function loadLive(): Promise<LiveFigures> {
  if (!cache) {
    cache = fetch(dataUrl('live_figures.json'), { credentials: 'same-origin' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status} loading live_figures.json`)
      return r.json() as Promise<LiveFigures>
    })
  }
  return cache
}

export function useLiveFigures(): LiveFigures | null {
  const [data, setData] = useState<LiveFigures | null>(null)
  useEffect(() => {
    let cancelled = false
    loadLive().then(d => { if (!cancelled) setData(d) }).catch(() => { /* placeholder stays */ })
    return () => { cancelled = true }
  }, [])
  return data
}

/** Inline live figure. Plain text: no emphasis, no callout. */
export function LiveFig({ k }: { k: LiveKey }) {
  const f = useLiveFigures()
  return <span data-live-figure={k}>{f ? formatLive(k, f) : '…'}</span>
}
