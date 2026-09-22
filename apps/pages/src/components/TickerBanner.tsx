const TICKER_SEGMENTS = [
  'HOLD · Static core + Book-2 vol-target',
  'Book 1: VOO 70% / QQQM 20% / IJR 10% · buy-and-hold reference',
  'Book 2: vol-target sleeve · scale-down only · BIL cash residual',
  'DO NOT PROMOTE · Spectral RP · Regime-Aware · Vol-cond #13 — FAIL / ARCHIVE',
  'SHIFT MEANING · same ~14.7% return · claim is risk path not return alpha',
  'XSD optional gated sleeve · never a live book · default OFF',
  'OOS window ~68 months · 2021-02 → 2026-09 · real-BIL sample · research only',
]

export default function TickerBanner() {
  // Use slash separators for broadsheet chrome density
  const text = TICKER_SEGMENTS.join('  /  ')
  const doubled = `${text}  /  ${text}`

  return (
    <div
      className="overflow-hidden bg-ink/90 border-b border-border"
      aria-label="Live shortlist summary ticker"
      aria-live="off"
    >
      <div
        className="inline-flex whitespace-nowrap py-2"
        style={{ animation: 'ticker 52s linear infinite' }}
      >
        <span className="text-2xs font-medium text-bg/70 tracking-wide px-4">
          {doubled}
        </span>
      </div>
    </div>
  )
}
