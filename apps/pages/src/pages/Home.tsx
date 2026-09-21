import { Link } from 'react-router-dom'
import { useJsonData } from '../hooks/useJsonData'
import { pct, num } from '../lib/utils'

interface MetricsPayload {
  AnnReturn_vt: number
  AnnVol_vt: number
  MaxDD_vt: number
  Sharpe_vt: number
  AnnReturn_a: number
  AnnVol_a: number
  MaxDD_a: number
  Sharpe_a: number
  NW_t: number
  n_months: number
  start_date: string
  end_date: string
  mean_f: number
  pct_months_f_lt_1: number
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="section-eyebrow">{children}</p>
  )
}

function SectionRule({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-0">
      <div className="flex-1 h-px bg-border" />
      {label && (
        <span className="text-2xs text-muted/50 uppercase tracking-label flex-shrink-0 px-1">
          {label}
        </span>
      )}
      <div className="flex-1 h-px bg-border" />
    </div>
  )
}

function QuoteBlock({
  quote,
  attribution,
}: {
  quote: string
  attribution: string
}) {
  return (
    <div className="quote-block">
      <p className="font-serif text-base md:text-lg italic text-ink leading-snug">{quote}</p>
      <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase">{attribution}</cite>
    </div>
  )
}

function BookCard({
  badge,
  live,
  title,
  descriptor,
  body,
  link,
  muted,
}: {
  badge: string
  live: boolean
  title: string
  descriptor: string
  body: string
  link?: { label: string; to: string }
  muted?: boolean
}) {
  const inner = (
    <article
      className={`article-card h-full p-5 flex flex-col gap-3 ${muted ? 'opacity-50' : 'cursor-pointer'}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span
          className={`text-2xs font-medium uppercase tracking-label px-2 py-0.5 rounded-full border ${
            live
              ? 'border-up/30 text-up bg-up/5'
              : 'border-border text-muted bg-raised'
          }`}
        >
          {badge}
        </span>
      </div>
      <div>
        <h3 className="font-display font-bold text-xl text-ink leading-tight mb-0.5">{title}</h3>
        <p className="text-xs uppercase tracking-label text-muted">{descriptor}</p>
      </div>
      <p className="text-sm text-body leading-relaxed flex-1">{body}</p>
      {link && (
        <p className="text-2xs text-muted/60 uppercase tracking-label mt-auto">
          {link.label} →
        </p>
      )}
    </article>
  )

  if (link && !muted) {
    return (
      <Link to={link.to} className="no-underline block h-full">
        {inner}
      </Link>
    )
  }
  return inner
}

export default function Home() {
  const { data: m } = useJsonData<MetricsPayload>('viz_metrics.json')

  return (
    <div>
      {/* ── Lead / Hero ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-10 pb-12 md:pt-14 md:pb-16">

          {/* CIO copy slot — headline */}
          <div className="max-w-3xl">
            <Eyebrow>Live shortlist · front door</Eyebrow>
            {/* [CIO: rewrite headline below if needed] */}
            <h2 className="font-display font-black text-4xl md:text-6xl text-ink leading-tight mt-2 mb-5 text-balance">
              Static core +<br className="hidden sm:block" /> Book&#8209;2 vol&#8209;target
            </h2>
            {/* [CIO: rewrite body paragraph below if needed] */}
            <p className="text-base md:text-lg text-body leading-relaxed max-w-2xl mb-8">
              The live research shortlist is <strong>Book 1 static Option A</strong> and{' '}
              <strong>Book 2 unconditional vol-target</strong>. Three archived methods failed
              binding nulls — they remain research record, not promoted books.
              Static GitHub Pages — no live trading.
            </p>

            <div className="flex flex-wrap gap-3">
              <Link
                to="/books"
                className="inline-flex items-center gap-2 bg-accent text-white text-sm font-medium rounded-lg px-5 py-2.5 no-underline hover:bg-accent/90 transition-colors"
              >
                Open live shortlist
              </Link>
              <Link
                to="/runs"
                className="inline-flex items-center gap-2 border border-border text-body text-sm font-medium rounded-lg px-5 py-2.5 no-underline hover:border-border-bright hover:text-ink transition-all"
              >
                OOS runs
              </Link>
              <Link
                to="/explorer"
                className="inline-flex items-center gap-2 border border-border text-body text-sm font-medium rounded-lg px-5 py-2.5 no-underline hover:border-border-bright hover:text-ink transition-all"
              >
                Explorer
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Live books grid ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="What is live right now" />
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <BookCard
              badge="Book 1 · live"
              live
              title="Static core"
              descriptor="Buy-and-hold reference"
              body="Fixed weights VOO 70% / QQQM 20% / IJR 10%. No timing, no vol scale. Clean null for any overlay or timing claim."
              link={{ label: 'View shortlist', to: '/books' }}
            />
            <BookCard
              badge="Book 2 · live"
              live
              title="Vol-target"
              descriptor="Default research path"
              body="Same Option A core, scaled by estimated volatility (scale-down only). Cash residual in BIL when risk is elevated."
              link={{ label: 'View shortlist', to: '/books' }}
            />
            <BookCard
              badge="Archive · not live"
              live={false}
              title="Archived methods"
              descriptor="FAIL / research record"
              body="Spectral RP, Regime-Aware, and vol-cond factor corr (#13) failed binding nulls — not promoted to books."
              muted
              link={{ label: 'View archive', to: '/archive' }}
            />
          </div>
        </div>
      </section>

      {/* ── Most Sharable — key findings ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <div className="flex items-center gap-3 mb-8">
            <span className="text-accent text-base leading-none">◆</span>
            <Eyebrow>Most sharable · key findings</Eyebrow>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
            <QuoteBlock
              quote="Static core + unconditional Book-2 VT. Everything else failed binding nulls — research record only."
              attribution="Live shortlist rationale"
            />
            <QuoteBlock
              quote="Path/risk improvement, not return alpha. NW t vs static A ≈ 0 on this panel — milder drawdown is the claim."
              attribution="Book 2 vol-target evidence"
            />
            <QuoteBlock
              quote="XSD is an optional gated sleeve. It is never a promoted live book. Default is OFF."
              attribution="Rotation sleeve framing"
            />
            <QuoteBlock
              quote="Justina round-1 and #13 did not clear binding nulls on Sharpe. No book cut. Shortlist unchanged."
              attribution="CIO frame on archive"
            />
          </div>
        </div>
      </section>

      {/* ── OOS metrics strip ── */}
      {m && (
        <section className="py-12 border-b border-border">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <SectionRule label="Supporting OOS" />

            <div className="mt-8 mb-2">
              <Eyebrow>Book 2 vol-target path vs static Option A</Eyebrow>
              <p className="text-sm text-body mt-1">
                {m.n_months}-month OOS · {m.start_date} → {m.end_date} · real-BIL sample.
                Evidence for the live Book-2 sleeve — not a separate promoted book.
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 mb-4">
              <div className="stat-card">
                <div className="stat-label">Sharpe (vt)</div>
                <div className="stat-value text-accent">{num(m.Sharpe_vt, 2)}</div>
                <div className="stat-sub">Static A: {num(m.Sharpe_a, 2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Max drawdown (vt)</div>
                <div className="stat-value text-down">{pct(m.MaxDD_vt)}</div>
                <div className="stat-sub">Static A: {pct(m.MaxDD_a)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Ann. vol (vt)</div>
                <div className="stat-value">{pct(m.AnnVol_vt)}</div>
                <div className="stat-sub">Static A: {pct(m.AnnVol_a)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">NW t vs A</div>
                <div className="stat-value">{num(m.NW_t, 2)}</div>
                <div className="stat-sub">Path / risk, not return alpha</div>
              </div>
            </div>

            <p className="text-xs text-muted mb-6">
              Moreira &amp; Muir (2017) · mean f = {m.mean_f.toFixed(2)} · months with f&lt;1:{' '}
              {(100 * m.pct_months_f_lt_1).toFixed(0)}%
            </p>

            <div className="flex flex-wrap gap-3">
              <Link
                to="/runs"
                className="inline-flex items-center gap-2 bg-accent text-white text-sm font-medium rounded-lg px-4 py-2 no-underline hover:bg-accent/90 transition-colors"
              >
                Open OOS charts
              </Link>
              <Link
                to="/books"
                className="inline-flex items-center gap-2 border border-border text-body text-sm font-medium rounded-lg px-4 py-2 no-underline hover:border-border-bright hover:text-ink transition-all"
              >
                Live shortlist weights
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* ── Lab sections (soft footer nav, not a second hero grid) ── */}
      <section className="py-10">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Lab sections" />
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              {
                to: '/books',
                eyebrow: 'Shortlist',
                title: 'Books',
                desc: 'Live Books 1–2 with standing-book cards, current weights, and comparison table.',
              },
              {
                to: '/runs',
                eyebrow: 'Out-of-sample',
                title: 'Runs',
                desc: 'Equity, drawdown, scale factor f_t, and downloadable CSVs for the live path.',
              },
              {
                to: '/explorer',
                eyebrow: 'Diagnostics',
                title: 'Explorer',
                desc: 'Growth-panel metrics and time-series charts for research diagnostics.',
              },
            ].map(item => (
              <Link key={item.to} to={item.to} className="no-underline block group">
                <div className="border border-border/60 bg-transparent rounded-lg px-4 py-3.5 h-full transition-colors group-hover:border-border">
                  <p className="section-eyebrow mb-1 text-muted/70">{item.eyebrow}</p>
                  <h3 className="font-display font-semibold text-lg text-ink/90 mb-1 leading-tight group-hover:text-ink">{item.title}</h3>
                  <p className="text-xs text-muted leading-relaxed">{item.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
