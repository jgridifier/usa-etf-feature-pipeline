import { Link } from 'react-router-dom'

export default function Masthead() {
  return (
    <div className="border-b border-border bg-bg">
      {/* Thick editorial rule — 3px broadsheet-weight top bar */}
      <div className="h-[3px] bg-ink/80" />

      <div className="mx-auto max-w-6xl px-4 md:px-6 py-4 md:py-5">
        <div className="flex items-center justify-between gap-4">
          {/* Wordmark — larger, more editorial */}
          <Link
            to="/"
            className="no-underline group flex-shrink-0"
            aria-label="USA ETF Lab home"
          >
            <div className="flex items-center gap-3.5">
              <div className="flex-shrink-0 h-9 w-9 rounded border border-border-bright bg-surface flex items-center justify-center shadow-card">
                <svg width="18" height="18" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <rect x="1.5" y="1.5" width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.9"/>
                  <rect x="8"   y="1.5" width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.4"/>
                  <rect x="1.5" y="8"   width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.4"/>
                  <rect x="8"   y="8"   width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.9"/>
                </svg>
              </div>
              <div>
                <p className="text-3xs font-medium uppercase tracking-masthead text-muted/70 leading-none mb-0.5">
                  Research Lab · USA Equities
                </p>
                <h1 className="font-display font-black text-2xl md:text-4xl text-ink leading-none tracking-tight group-hover:text-accent transition-colors">
                  USA ETF LAB
                </h1>
              </div>
            </div>
          </Link>

          {/* Right meta — edition/date energy */}
          <div className="hidden md:flex flex-col items-end gap-1 text-right flex-shrink-0">
            <p className="text-2xs text-muted/80 uppercase tracking-label font-medium">
              Research edition
            </p>
            <p className="text-2xs text-muted/50">
              Static GitHub Pages · Not investment advice
            </p>
            <p className="text-2xs text-muted/40 font-mono">
              OOS window · 2021-02 → 2026-09
            </p>
          </div>
        </div>

        {/* Thick horizontal rule with centred label — broadsheet divider */}
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1 h-px bg-border-bright/60" />
          <span className="text-2xs text-muted/50 uppercase tracking-label flex-shrink-0 px-1 font-medium">
            Experimental panel · research only
          </span>
          <div className="flex-1 h-px bg-border-bright/60" />
        </div>
      </div>
    </div>
  )
}
