import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function Explorer() {
  useEffect(() => {
    window.location.replace('./explorer/index.html')
  }, [])

  return (
    <div>
      {/* Research sandbox framing — this is not a live shortlist peer */}
      <section className="border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-5xl px-4 md:px-6 py-10">
          <div className="inline-flex items-center gap-2 border border-border/60 rounded-full px-3 py-1 mb-4">
            <span className="text-2xs font-medium uppercase tracking-label text-muted/60">Research sandbox</span>
          </div>
          <h1 className="font-display font-bold text-3xl text-ink/70 mb-3 leading-tight">
            Time Series Explorer
          </h1>
          <div className="border border-down/20 bg-down/5 rounded-xl px-4 py-3 mb-5 max-w-xl">
            <p className="text-sm text-muted">
              <strong className="text-ink">Not a live shortlist peer.</strong>{' '}
              This tool is a layer-3 diagnostics sandbox for research use. It is not part of the
              live shortlist (Books 1–2) and is not an alternative methodology candidate.
              All shortlist decisions are on{' '}
              <Link to="/books" className="text-accent/70 hover:text-accent no-underline">Books →</Link>
            </p>
          </div>
          <p className="text-sm text-body/70 mb-6 max-w-xl">
            Growth-panel metrics and time-series charts for exploratory research. Redirecting…
          </p>
          <a
            href="./explorer/index.html"
            className="inline-flex items-center gap-2 rounded-lg border border-border text-muted text-sm font-medium px-5 py-2.5 hover:border-border-bright hover:text-ink transition-all no-underline"
          >
            Open Explorer sandbox →
          </a>
        </div>
      </section>
    </div>
  )
}
