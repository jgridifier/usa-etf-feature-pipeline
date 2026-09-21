const TICKER_SEGMENTS = [
  '● Static core + Book-2 vol-target · live research shortlist',
  '◆ Book 1: VOO 70% / QQQM 20% / IJR 10% · buy-and-hold reference',
  '◆ Book 2: vol-target sleeve · scale-down only · BIL cash residual',
  '● Spectral RP · Regime-Aware · Vol-cond #13 — FAIL / ARCHIVE',
  '◆ Not investment advice · experimental USA ETF panel · no performance guarantees',
  '● XSD optional gated sleeve · never a live book',
  '◆ OOS window ~68 months · 2021-02 → 2026-09 · real-BIL sample',
]

export default function TickerBanner() {
  const text = TICKER_SEGMENTS.join('   ')
  // Duplicate for seamless loop
  const doubled = `${text}   ${text}`

  return (
    <div className="ticker-wrap py-1.5" aria-label="Live shortlist summary ticker" aria-live="off">
      <div className="ticker-inner text-2xs font-medium text-muted tracking-wide">
        <span>{doubled}&nbsp;&nbsp;&nbsp;</span>
      </div>
    </div>
  )
}
