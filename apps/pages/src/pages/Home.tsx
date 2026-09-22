import { useState } from 'react'
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
  return <p className="section-eyebrow">{children}</p>
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

/** CIO verdict band — 3-beat plain-language summary, above the fold */
function CioVerdictBand() {
  return (
    <div className="border border-border/80 rounded-xl bg-surface overflow-hidden mb-8">
      <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
        <span className="text-accent text-xs leading-none">◆</span>
        <span className="text-2xs font-medium uppercase tracking-label text-muted">CIO verdict · plain language</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border">
        {/* Beat 1: HOLD */}
        <div className="px-5 py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-up mb-1.5">HOLD</p>
          <p className="text-sm text-ink leading-snug font-medium mb-1">Static core + Book-2 vol-target</p>
          <p className="text-2xs text-body leading-relaxed">
            Book 1 (fixed VOO/QQQM/IJR) and Book 2 (same core, volatility-scaled) are the live
            shortlist. Hold both.
          </p>
        </div>
        {/* Beat 2: DO NOT PROMOTE */}
        <div className="px-5 py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-down mb-1.5">DO NOT PROMOTE</p>
          <p className="text-sm text-ink leading-snug font-medium mb-1">Archive failures + XSD sleeve</p>
          <p className="text-2xs text-body leading-relaxed">
            Spectral RP, Regime-Aware, and #13 failed binding-null gates — archived only.
            XSD is a gated sleeve, default <strong>OFF</strong>, never a live book.
          </p>
        </div>
        {/* Beat 3: SHIFT meaning */}
        <div className="px-5 py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-accent mb-1.5">SHIFT MEANING</p>
          <p className="text-sm text-ink leading-snug font-medium mb-1">Book-2 = risk path, not return alpha</p>
          <p className="text-2xs text-body leading-relaxed">
            Book-2 and Book-1 earn roughly the same annual return (~14.7%). The shift is
            milder drawdown (−20% vs −26%) and higher Sharpe — not outperformance.
          </p>
        </div>
      </div>
    </div>
  )
}

/** HTML/CSS delta strip: Book-2 vs Book-1 key metrics */
function DeltaStrip({ m }: { m: MetricsPayload }) {
  const sharpeDelta = m.Sharpe_vt - m.Sharpe_a
  const ddDelta = m.MaxDD_a - m.MaxDD_vt       // positive = vt is milder
  const volDelta = m.AnnVol_a - m.AnnVol_vt    // positive = vt is lower vol

  const metrics = [
    {
      label: 'Sharpe (rf=0)',
      vt: num(m.Sharpe_vt, 2),
      base: num(m.Sharpe_a, 2),
      delta: sharpeDelta > 0 ? `+${num(sharpeDelta, 2)}` : num(sharpeDelta, 2),
      deltaGood: sharpeDelta > 0,
      barPct: Math.min(100, (m.Sharpe_vt / 1.5) * 100),
      basePct: Math.min(100, (m.Sharpe_a / 1.5) * 100),
    },
    {
      label: 'Max drawdown',
      vt: pct(m.MaxDD_vt),
      base: pct(m.MaxDD_a),
      delta: `+${pct(ddDelta)} milder`,
      deltaGood: true,
      barPct: Math.min(100, (Math.abs(m.MaxDD_vt) / 0.4) * 100),
      basePct: Math.min(100, (Math.abs(m.MaxDD_a) / 0.4) * 100),
    },
    {
      label: 'Ann. vol',
      vt: pct(m.AnnVol_vt),
      base: pct(m.AnnVol_a),
      delta: `−${pct(volDelta)} lower`,
      deltaGood: true,
      barPct: Math.min(100, (m.AnnVol_vt / 0.25) * 100),
      basePct: Math.min(100, (m.AnnVol_a / 0.25) * 100),
    },
    {
      label: 'NW t vs Book-1',
      vt: num(m.NW_t, 2),
      base: '—',
      delta: '≈ 0 expected',
      deltaGood: null,
      barPct: null,
      basePct: null,
      note: 'Near zero = return parity; claim is risk path only',
    },
  ]

  return (
    <div className="border border-border rounded-xl bg-surface overflow-hidden mb-8">
      <div className="px-4 py-2.5 border-b border-border flex items-center gap-2">
        <span className="text-2xs font-medium uppercase tracking-label text-muted">
          Book-2 vs Book-1 delta · {m.n_months}mo OOS · {m.start_date} → {m.end_date}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-border">
        {metrics.map(metric => (
          <div key={metric.label} className="px-4 py-4">
            <p className="text-2xs text-muted uppercase tracking-label mb-2">{metric.label}</p>

            {/* HTML/CSS proportion bar */}
            {metric.barPct != null && (
              <div className="mb-2 space-y-1">
                <div className="flex items-center gap-1.5">
                  <div className="text-3xs text-muted/70 w-10 shrink-0">Book-2</div>
                  <div className="flex-1 h-2 bg-raised rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent rounded-full transition-all"
                      style={{ width: `${metric.barPct}%` }}
                    />
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="text-3xs text-muted/70 w-10 shrink-0">Book-1</div>
                  <div className="flex-1 h-2 bg-raised rounded-full overflow-hidden">
                    <div
                      className="h-full bg-border-bright rounded-full transition-all"
                      style={{ width: `${metric.basePct}%` }}
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="font-mono text-base text-ink font-semibold">{metric.vt}</span>
              <span className="text-2xs text-muted">vs {metric.base}</span>
            </div>

            <p className={`text-2xs mt-1 font-medium ${
              metric.deltaGood === true ? 'text-up' :
              metric.deltaGood === false ? 'text-down' : 'text-muted'
            }`}>
              {metric.delta}
            </p>
            {metric.note && (
              <p className="text-3xs text-muted/60 mt-0.5 leading-relaxed">{metric.note}</p>
            )}
          </div>
        ))}
      </div>
      <div className="px-4 py-2 border-t border-border bg-raised">
        <p className="text-2xs text-muted/70">
          <strong className="text-muted">Bottom line:</strong> Book-2 earns the same ~14.7% as Book-1 — the shift is risk path, not return alpha.{' '}
          <Link to="/runs" className="text-accent/80 hover:text-accent no-underline">See full OOS charts →</Link>
        </p>
      </div>
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

/** Two-layer progressive disclosure: overview is always visible; expand reveals deeper detail */
function DisclosureSection({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface hover:bg-raised transition-colors text-left gap-2"
        aria-expanded={open}
      >
        <span className="text-sm font-medium text-ink">{summary}</span>
        <span className="text-muted text-xs flex-shrink-0">{open ? '▲ collapse' : '▼ expand'}</span>
      </button>
      {open && (
        <div className="border-t border-border bg-bg">
          {children}
        </div>
      )}
    </div>
  )
}

export default function Home() {
  const { data: m } = useJsonData<MetricsPayload>('viz_metrics.json')

  return (
    <div>
      {/* ── Lead / Hero ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-10 pb-12 md:pt-14 md:pb-16">

          <div className="max-w-3xl">
            <Eyebrow>Live shortlist · front door</Eyebrow>
            <h2 className="font-display font-black text-4xl md:text-6xl text-ink leading-tight mt-2 mb-5 text-balance">
              Static core +<br className="hidden sm:block" /> Book&#8209;2 vol&#8209;target
            </h2>
            <p className="text-base md:text-lg text-body leading-relaxed max-w-2xl mb-6">
              The live research shortlist is <strong>Book 1 static Option A</strong> and{' '}
              <strong>Book 2 unconditional vol-target</strong>. Three archived methods failed
              binding nulls — they remain research record, not promoted books.
              Static GitHub Pages — no live trading.
            </p>

            {/* CIO verdict band — above the fold */}
            <CioVerdictBand />

            {/* Book-2 vs Book-1 delta strip — HTML/CSS art, above fold */}
            {m && <DeltaStrip m={m} />}

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
              link={{ label: 'See Book 1 composition', to: '/books' }}
            />
            <BookCard
              badge="Book 2 · live"
              live
              title="Vol-target"
              descriptor="Risk path — not return alpha"
              body="Same Option A core, scaled by estimated volatility (scale-down only). Cash residual in BIL when risk is elevated. Same ~14.7% return as Book 1 — the shift is milder drawdowns and higher Sharpe."
              link={{ label: 'See Book 2 path vs Book 1', to: '/books' }}
            />
            <BookCard
              badge="Archive · not live"
              live={false}
              title="Archived methods"
              descriptor="FAIL / research record"
              body="Spectral RP, Regime-Aware, and vol-cond factor corr (#13) failed binding nulls — not promoted to books."
              muted
              link={{ label: 'View archive scoreboard', to: '/archive' }}
            />
          </div>
        </div>
      </section>

      {/* ── Most Sharable — key findings (layer 1 overview) ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <div className="flex items-center gap-3 mb-8">
            <span className="text-accent text-base leading-none">◆</span>
            <Eyebrow>Most sharable · key findings</Eyebrow>
          </div>

          {/* Layer 1: overview quotes — corrected label↔body pairs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8 mb-8">
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "Static core + unconditional Book-2 VT. Everything else failed binding nulls — research record only."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase">
                Live shortlist rationale ·{' '}
                <Link to="/books" className="text-accent/70 hover:text-accent no-underline">see shortlist →</Link>
              </cite>
            </div>
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "Path and risk improvement, not return alpha. NW t vs static A ≈ 0 on this panel — milder drawdown is the claim. Book-1 and Book-2 earn the same ~14.7% per year."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase">
                Book-2 vol-target evidence ·{' '}
                <Link to="/runs" className="text-accent/70 hover:text-accent no-underline">see OOS charts →</Link>
              </cite>
            </div>
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "Justina round-1 and #13 did not clear binding nulls on Sharpe. No book cut. Shortlist unchanged."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase">
                CIO verdict on archive ·{' '}
                <Link to="/archive" className="text-accent/70 hover:text-accent no-underline">see scoreboard →</Link>
              </cite>
            </div>
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "XSD is an optional gated sleeve — never a promoted live book. Default is OFF. Do not compare it as a peer to Books 1–2."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase">
                Rotation sleeve framing ·{' '}
                <Link to="/books" className="text-accent/70 hover:text-accent no-underline">see sleeve detail →</Link>
              </cite>
            </div>
          </div>

          {/* Layer 2: progressive disclosure — supporting OOS metrics */}
          <DisclosureSection summary="Supporting OOS data — Book-2 vs Book-1 metrics (expand)">
            {m && (
              <div className="p-5">
                <p className="text-sm text-body mb-4">
                  {m.n_months}-month OOS · {m.start_date} → {m.end_date} · real-BIL sample.
                  Evidence for the live Book-2 sleeve — not a separate promoted book.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
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
                <p className="text-xs text-muted mb-4">
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
            )}
          </DisclosureSection>
        </div>
      </section>

      {/* ── Lab sections (soft footer nav) ── */}
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
                to: '/archive',
                eyebrow: 'Research record',
                title: 'Archive',
                desc: 'Justina round-1 and #13 — failed methods documented as binding-null reference.',
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
