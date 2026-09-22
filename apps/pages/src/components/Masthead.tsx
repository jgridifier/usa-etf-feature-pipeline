import { Link } from 'react-router-dom'

export default function Masthead() {
  const today = new Date()
  const dateStr = today.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <header className="bg-bg border-b border-border">
      {/* ── Broadsheet thick top rule — ink black ── */}
      <div className="h-[4px] bg-ink" />

      {/* ── Date / edition strip ── */}
      <div className="border-b border-border/60">
        <div className="mx-auto max-w-6xl px-4 md:px-6 py-1.5 flex items-center justify-between gap-4">
          <p className="text-2xs font-sans font-medium uppercase tracking-label text-muted">
            {dateStr}
          </p>
          <p className="text-2xs font-sans text-muted/60 uppercase tracking-label">
            OOS window · 2021-02 → 2026-09
          </p>
          <p className="hidden md:block text-2xs font-sans text-muted/50 uppercase tracking-label">
            Static GitHub Pages · Research only
          </p>
        </div>
      </div>

      {/* ── Centered wordmark — broadsheet scale ── */}
      <div className="mx-auto max-w-6xl px-4 md:px-6 py-6 md:py-8 text-center">
        <Link
          to="/"
          className="no-underline inline-block group"
          aria-label="USA ETF Lab — research home"
        >
          <p className="font-sans text-2xs uppercase tracking-[0.35em] text-muted mb-2 font-medium">
            Experimental Research Panel · USA Equities
          </p>
          <h1
            className="font-display font-black text-ink leading-none tracking-tight group-hover:opacity-80 transition-opacity"
            style={{ fontSize: 'clamp(2.8rem, 7vw, 4.5rem)', letterSpacing: '-0.02em' }}
          >
            USA ETF LAB
          </h1>
          <p className="font-sans text-2xs uppercase tracking-[0.3em] text-muted mt-2 font-medium">
            Research Edition · Not Investment Advice
          </p>
        </Link>
      </div>

      {/* ── Thick horizontal masthead rule ── */}
      <div className="mx-auto max-w-6xl px-4 md:px-6 pb-4">
        <div className="h-[2px] bg-ink" />
        <div className="mt-[3px] h-px bg-border" />
      </div>
    </header>
  )
}
