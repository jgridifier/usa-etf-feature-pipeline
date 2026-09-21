import { Link } from 'react-router-dom'

export default function Masthead() {
  return (
    <div className="border-b border-border bg-bg">
      {/* Top rule */}
      <div className="h-px bg-border-bright" />

      <div className="mx-auto max-w-6xl px-4 md:px-6 py-5 md:py-6">
        <div className="flex items-end justify-between gap-4">
          {/* Wordmark */}
          <Link
            to="/"
            className="no-underline group flex-shrink-0"
            aria-label="USA ETF Lab home"
          >
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 h-7 w-7 rounded border border-border-bright bg-surface flex items-center justify-center shadow-card">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <rect x="1.5" y="1.5" width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.9"/>
                  <rect x="8"   y="1.5" width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.4"/>
                  <rect x="1.5" y="8"   width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.4"/>
                  <rect x="8"   y="8"   width="4.5" height="4.5" rx="0.75" fill="#4f7ef8" opacity="0.9"/>
                </svg>
              </div>
              <div>
                <p className="text-3xs font-medium uppercase tracking-masthead text-muted leading-none mb-0.5">
                  Research Lab
                </p>
                <h1 className="font-display font-black text-2xl md:text-3xl text-ink leading-none tracking-tight group-hover:text-accent transition-colors">
                  USA ETF LAB
                </h1>
              </div>
            </div>
          </Link>

          {/* Right meta */}
          <div className="hidden md:flex flex-col items-end gap-1 text-right flex-shrink-0">
            <p className="text-2xs text-muted uppercase tracking-label">
              Experimental panel
            </p>
            <p className="text-2xs text-muted/60">
              Static GitHub Pages · Not investment advice
            </p>
          </div>
        </div>

        {/* Date rule */}
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1 h-px bg-border" />
          <span className="text-2xs text-muted/60 uppercase tracking-label flex-shrink-0">
            Research only
          </span>
          <div className="flex-1 h-px bg-border" />
        </div>
      </div>
    </div>
  )
}
