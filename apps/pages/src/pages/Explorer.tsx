import { Link } from 'react-router-dom'

export default function Explorer() {
  // No auto-redirect — user must explicitly click through to the sandbox.
  // The destination (explorer/index.html) is a separate white Inter tooling shell;
  // this interstitial is the edition-chrome gate so the style break is deliberate.

  return (
    <div>
      {/* ── Edition chrome wrapper — same paper substrate ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6 pt-10 pb-12">

          {/* Thick broadsheet rule — mirrors masthead */}
          <div className="h-[3px] bg-ink mb-6" />

          {/* Sandbox identity block */}
          <div className="mb-6">
            <p className="font-sans text-2xs font-bold uppercase tracking-[0.3em] text-muted mb-2">
              Research Sandbox · Layer 3 Diagnostics
            </p>
            <h1 className="font-display font-black text-3xl md:text-5xl text-ink leading-tight mb-3">
              Time Series Explorer
            </h1>
            <div className="h-[2px] bg-ink/20 mt-4" />
          </div>

          {/* Unmistakable sandbox banner */}
          <div className="border-2 border-ink bg-ink text-bg px-5 py-4 mb-6">
            <div className="flex items-start gap-3">
              <span className="font-sans text-base font-black text-bg/60 mt-0.5 select-none" aria-hidden="true">⚠</span>
              <div>
                <p className="font-sans text-sm font-bold text-bg uppercase tracking-label mb-1">
                  Sandbox — Not a live shortlist peer
                </p>
                <p className="font-sans text-xs text-bg/75 leading-relaxed">
                  This is a layer-3 diagnostics tool for exploratory research. It is{' '}
                  <strong className="text-bg font-semibold">not</strong> part of the live shortlist
                  (Books 1–2) and is{' '}
                  <strong className="text-bg font-semibold">not</strong> an alternative methodology
                  candidate. All shortlist decisions are on{' '}
                  <Link to="/books" className="text-bg underline underline-offset-2 decoration-bg/40 hover:decoration-bg transition-colors">
                    Books →
                  </Link>
                </p>
              </div>
            </div>
          </div>

          {/* Context body */}
          <div className="mb-8 max-w-2xl">
            <p className="font-serif text-base text-body leading-relaxed mb-4">
              The Explorer shell is a separate application with its own styling (white background,
              Inter font) — the style break from the edition is intentional and expected.
              It provides growth-panel metrics and time-series charts for exploratory research
              use only.
            </p>
            <p className="font-serif text-sm text-muted leading-relaxed">
              Scope: layer-3 diagnostics sandbox. Outputs are research artifacts — not promoted
              shortlist additions and not investment advice.
            </p>
          </div>

          {/* Explicit CTA — user must click; no auto-redirect */}
          <div className="flex flex-wrap items-center gap-4">
            <a
              href="./explorer/index.html"
              className="font-sans inline-flex items-center gap-2 border-2 border-ink text-ink text-sm font-semibold px-6 py-3 no-underline hover:bg-ink hover:text-bg transition-all"
            >
              Open Explorer sandbox →
            </a>
            <Link
              to="/books"
              className="font-sans inline-flex items-center gap-2 border border-border text-muted text-sm font-medium px-5 py-2.5 no-underline hover:border-border-bright hover:text-body transition-all"
            >
              Live shortlist (Books) →
            </Link>
          </div>

          {/* Bottom rule */}
          <div className="mt-10 h-px bg-border" />
          <div className="mt-[3px] h-[2px] bg-ink/15" />
        </div>
      </section>
    </div>
  )
}
