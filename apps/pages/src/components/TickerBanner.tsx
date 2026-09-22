const TICKER_SEGMENTS = [
  'HOLD · Static core + Book-2 vol-target',
  'Book 1: VOO 70% / QQQM 20% / IJR 10% · buy-and-hold reference',
  'Book 2: vol-target sleeve · scale-down only · BIL cash residual',
  'DO NOT PROMOTE · Spectral RP · Regime-Aware · Vol-cond #13 — FAIL / ARCHIVE',
  'SHIFT MEANING · same ~14.7% return · claim is risk path not return alpha',
  'MaxDD: −20.1% vol-target vs −25.6% static · +5.4pp milder',
  'XSD optional gated sleeve · never a live book · default OFF',
  'OOS window ~68 months · 2021-02 → 2026-09 · real-BIL sample · research only',
]

function Slash() {
  return (
    <span className="mx-3 font-sans font-black text-bg/40 text-sm leading-none select-none" aria-hidden="true">
      /
    </span>
  )
}

export default function TickerBanner() {
  const doubled = [...TICKER_SEGMENTS, ...TICKER_SEGMENTS]

  return (
    <div
      className="overflow-hidden bg-ink border-b-2 border-ink"
      aria-label="Live shortlist summary ticker"
      aria-live="off"
      style={{ minHeight: '2.25rem' }}
    >
      <div
        className="inline-flex items-center whitespace-nowrap py-2"
        style={{ animation: 'ticker 60s linear infinite' }}
      >
        {doubled.map((seg, i) => (
          <span key={i} className="inline-flex items-center">
            <span className="font-sans text-xs font-semibold text-bg/80 tracking-wide px-2">
              {seg}
            </span>
            <Slash />
          </span>
        ))}
      </div>
    </div>
  )
}
