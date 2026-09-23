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

function ThickRule({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 my-0">
      <div className="flex-1 h-[2px] bg-ink/20" />
      {label && (
        <span className="font-sans text-2xs text-muted/60 uppercase tracking-label flex-shrink-0 px-2 font-medium">
          {label}
        </span>
      )}
      <div className="flex-1 h-[2px] bg-ink/20" />
    </div>
  )
}

/** CIO verdict band — 3-beat plain-language summary, above the fold. */
function CioVerdictBand() {
  return (
    <div className="border border-border bg-surface overflow-hidden mb-5">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 bg-ink">
        <span className="font-sans text-2xs font-bold uppercase tracking-label text-bg/80">CIO Verdict</span>
        <span className="font-sans text-2xs text-bg/40 uppercase tracking-label">Plain language</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border">
        {/* Beat 1: HOLD */}
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="font-sans text-2xs font-bold uppercase tracking-label text-up whitespace-nowrap md:mb-1.5">HOLD</p>
          <div>
            <p className="font-serif text-sm text-ink leading-snug font-medium md:mb-1">Static core + Book-2 vol-target</p>
            <p className="hidden md:block font-sans text-2xs text-body leading-relaxed">
              Book 1 (fixed VOO/QQQM/IJR) and Book 2 (same core, volatility-scaled) are the live
              shortlist. Hold both.
            </p>
          </div>
        </div>
        {/* Beat 2: DO NOT PROMOTE */}
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="font-sans text-2xs font-bold uppercase tracking-label text-down whitespace-nowrap md:mb-1.5">DO NOT PROMOTE</p>
          <div>
            <p className="font-serif text-sm text-ink leading-snug font-medium md:mb-1">Archive failures + XSD sleeve</p>
            <p className="hidden md:block font-sans text-2xs text-body leading-relaxed">
              Spectral RP, Regime-Aware, and #13 failed binding-null gates — archived only.
              XSD is a gated sleeve, default <strong>OFF</strong>, never a live book.
            </p>
          </div>
        </div>
        {/* Beat 3: SHIFT meaning */}
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="font-sans text-2xs font-bold uppercase tracking-label text-accent whitespace-nowrap md:mb-1.5">SHIFT MEANING</p>
          <div>
            <p className="font-serif text-sm text-ink leading-snug font-medium md:mb-1">Book-2 = risk path, not return alpha</p>
            <p className="hidden md:block font-sans text-2xs text-body leading-relaxed">
              Book-2 and Book-1 earn roughly the same annual return (~14.7%). The shift is
              milder drawdown (−20% vs −26%) and higher Sharpe — not outperformance.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Typographic weight mosaic — VOO/QQQM/IJR/BIL as bold letterpress blocks. */
function WeightMosaic() {
  const blocks: Array<{ ticker: string; weight: string; pct: number; sub: string; book: string }> = [
    { ticker: 'VOO',  weight: '70%', pct: 70, sub: 'US large cap',       book: 'B1 + B2' },
    { ticker: 'QQQM', weight: '20%', pct: 20, sub: 'US tech/growth',      book: 'B1 + B2' },
    { ticker: 'IJR',  weight: '10%', pct: 10, sub: 'US small cap',        book: 'B1 + B2' },
    { ticker: 'BIL',  weight: 'var', pct: 8,  sub: 'Cash residual',       book: 'B2 only' },
  ]

  return (
    <div className="border border-border bg-surface overflow-hidden mb-5">
      <div className="px-3 py-2 border-b border-border bg-raised">
        <span className="font-sans text-2xs font-medium uppercase tracking-label text-muted">
          Composition · Book 1 + Book 2 static weights / BIL cash residual
        </span>
      </div>
      <div className="flex h-28 md:h-32 divide-x divide-border">
        {blocks.map(b => (
          <div
            key={b.ticker}
            className="flex flex-col justify-between p-2 md:p-3 overflow-hidden relative bg-bg"
            style={{ flexBasis: `${b.pct}%`, minWidth: b.pct < 15 ? '3.5rem' : undefined }}
          >
            <span
              className="font-display font-black text-ink leading-none select-none"
              style={{
                fontSize: b.pct >= 50 ? 'clamp(1.6rem, 4vw, 3rem)' :
                          b.pct >= 15 ? 'clamp(1rem, 2.5vw, 1.8rem)' : '0.85rem',
                opacity: b.pct < 15 ? 0.7 : 1,
              }}
            >
              {b.ticker}
            </span>
            <div>
              <div className="font-mono font-bold text-ink text-xs md:text-sm leading-none">{b.weight}</div>
              <div className="font-sans text-2xs text-muted mt-0.5 leading-tight hidden md:block">{b.sub}</div>
              <div className="font-sans text-3xs text-muted/60 mt-0.5 leading-tight">{b.book}</div>
            </div>
            <div
              className="absolute bottom-0 left-0 right-0 h-[3px] bg-ink"
              style={{ opacity: b.pct >= 50 ? 0.7 : b.pct >= 15 ? 0.4 : 0.2 }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

/** CSS risk-path / MaxDD visual — paired drawdown band art. */
function MaxDdVisual({ m }: { m: MetricsPayload }) {
  const ddPp = (Math.abs(m.MaxDD_a) - Math.abs(m.MaxDD_vt)) * 100
  const rangeMax = 40
  const vtPct  = Math.min(100, (Math.abs(m.MaxDD_vt) / rangeMax) * 100)
  const statPct = Math.min(100, (Math.abs(m.MaxDD_a) / rangeMax) * 100)

  return (
    <div className="border border-border bg-surface overflow-hidden mb-6">
      <div className="px-3 py-2 border-b border-border bg-raised flex items-center justify-between gap-2">
        <span className="font-sans text-2xs font-medium uppercase tracking-label text-muted">
          Risk-path · MaxDD comparison
        </span>
        <span className="font-mono text-2xs font-bold text-up">
          +{ddPp.toFixed(1)}pp milder
        </span>
      </div>

      <div className="p-4 space-y-3">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="font-sans text-2xs font-medium text-muted uppercase tracking-label">Book 2 vol-target</span>
            <span className="font-mono text-xs font-bold text-ink">{pct(m.MaxDD_vt)}</span>
          </div>
          <div className="relative h-8 bg-raised border border-border overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-border" />
            <div
              className="absolute top-0 left-0 h-full"
              style={{
                width: `${vtPct}%`,
                background: 'rgba(139,26,26,0.12)',
                borderRight: '2px solid rgba(139,26,26,0.5)',
              }}
            />
            <div className="absolute inset-0 flex items-center px-2">
              <span className="font-sans text-2xs text-down/70 font-medium">
                MaxDD {pct(m.MaxDD_vt)} ← milder peak loss
              </span>
            </div>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="font-sans text-2xs font-medium text-muted uppercase tracking-label">Book 1 static</span>
            <span className="font-mono text-xs font-bold text-ink">{pct(m.MaxDD_a)}</span>
          </div>
          <div className="relative h-8 bg-raised border border-border overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-px bg-border" />
            <div
              className="absolute top-0 left-0 h-full"
              style={{
                width: `${statPct}%`,
                background: 'rgba(139,26,26,0.22)',
                borderRight: '2px solid rgba(139,26,26,0.7)',
              }}
            />
            <div className="absolute inset-0 flex items-center px-2">
              <span className="font-sans text-2xs text-down/70 font-medium">
                MaxDD {pct(m.MaxDD_a)} ← deeper peak loss
              </span>
            </div>
          </div>
        </div>

        <p className="font-sans text-2xs text-muted leading-relaxed pt-1">
          {m.n_months}mo OOS · {m.start_date} → {m.end_date} ·
          NW t ≈ {num(m.NW_t, 2)} (return parity — risk-path claim only) ·
          Sharpe {num(m.Sharpe_vt, 2)} vs {num(m.Sharpe_a, 2)}
        </p>
      </div>
    </div>
  )
}

/**
 * Progressive disclosure using native <details>/<summary>.
 */
function DisclosureSection({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  return (
    <details
      open={defaultOpen}
      className="group border border-border overflow-hidden"
    >
      <summary className="list-none w-full flex items-center justify-between px-4 py-3 bg-surface hover:bg-raised transition-colors cursor-pointer gap-2 select-none [&::-webkit-details-marker]:hidden">
        <span className="font-sans text-sm font-medium text-ink">{summary}</span>
        <span className="font-sans text-muted text-xs flex-shrink-0 group-open:hidden">▼ expand</span>
        <span className="font-sans text-muted text-xs flex-shrink-0 hidden group-open:inline">▲ collapse</span>
      </summary>
      <div className="border-t border-border bg-bg">
        {children}
      </div>
    </details>
  )
}

/** Editorial article-stream card — live shortlist only (Books 1 and 2). */
function ArticleCard({
  label,
  status,
  statusColor,
  headline,
  lede,
  link,
}: {
  label: string
  status: string
  statusColor: 'up' | 'down' | 'muted'
  headline: string
  lede: string
  link?: { label: string; to: string }
}) {
  const statusClasses = {
    up: 'text-up border-up/30 bg-up/5',
    down: 'text-down border-down/30 bg-down/5',
    muted: 'text-muted border-border bg-surface',
  }

  const inner = (
    <article className="border-b border-border py-5 px-0">
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className={`font-sans text-2xs font-medium uppercase tracking-label px-2 py-0.5 border ${statusClasses[statusColor]}`}>
              {status}
            </span>
            <span className="font-sans text-2xs text-muted uppercase tracking-label">{label}</span>
          </div>
          <h3 className="font-display font-bold text-xl md:text-2xl text-ink leading-tight mb-2">{headline}</h3>
          <p className="font-serif text-sm text-body leading-relaxed">{lede}</p>
        </div>
        {link && (
          <div className="flex-shrink-0 hidden md:block">
            <span className="font-sans text-2xs text-muted/60 uppercase tracking-label">{link.label} →</span>
          </div>
        )}
      </div>
    </article>
  )

  if (link) {
    return (
      <Link to={link.to} className="no-underline block hover:bg-surface/50 transition-colors -mx-4 px-4">
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
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-8 pb-10 md:pt-12 md:pb-14">

          <div className="max-w-3xl">
            <Eyebrow>Live shortlist · front door</Eyebrow>
            <h2 className="font-display font-black text-3xl md:text-6xl text-ink leading-tight mt-1.5 mb-4 text-balance">
              Static core +<br className="hidden sm:block" /> Book&#8209;2 vol&#8209;target
            </h2>
            <p className="font-serif text-sm md:text-base text-body leading-relaxed max-w-2xl mb-5">
              Two live books on the experimental USA ETF panel. Three archived methods failed
              binding nulls — research record only. Static GitHub Pages — no live trading.
            </p>

            {/* CIO verdict band — 3 beats above the fold */}
            <CioVerdictBand />

            {/* Typographic weight mosaic — VOO/QQQM/IJR/BIL composition */}
            <WeightMosaic />

            {/* CSS MaxDD risk-path visual */}
            {m && <MaxDdVisual m={m} />}

            <div className="flex flex-wrap gap-3">
              <Link
                to="/books"
                className="font-sans inline-flex items-center gap-2 bg-ink text-bg text-sm font-medium px-5 py-2.5 no-underline hover:bg-ink/80 transition-colors"
              >
                Open live shortlist
              </Link>
              <Link
                to="/runs"
                className="font-sans inline-flex items-center gap-2 border border-border text-body text-sm font-medium px-5 py-2.5 no-underline hover:border-border-bright hover:text-ink transition-all"
              >
                OOS runs
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Editorial article stream — live shortlist: exactly 2 books ── */}
      <section className="py-10 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Live shortlist" />
          <div className="mt-4">
            <ArticleCard
              label="Book 1 · live"
              status="HOLD"
              statusColor="up"
              headline="Static core"
              lede="Fixed weights VOO 70% / QQQM 20% / IJR 10%. No timing, no vol scale. Clean null for any overlay or timing claim. Buy-and-hold reference for the entire panel."
              link={{ label: 'See Book 1 composition', to: '/books' }}
            />
            <ArticleCard
              label="Book 2 · live"
              status="HOLD"
              statusColor="up"
              headline="Vol-target + skewness gate"
              lede="Same Option A core, vol-scaled with skewness/left-tail gate applied (Gong–Lynch–Ogden 2025, Justina #6). f̃_t = f_t · g_t; cash residual in BIL. Same ~14.7% return as Book 1 — the shift is milder drawdowns and higher Sharpe. Risk path, not return alpha."
              link={{ label: 'See Book 2 path vs Book 1', to: '/books' }}
            />
          </div>
        </div>
      </section>

      {/* ── Methods · Archive — clearly separate from live shortlist ── */}
      <section className="py-10 border-b border-border bg-raised/40">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Methods · Archive — research record" />
          <div className="mt-6 border border-down/20 bg-down/5 px-5 py-4">
            <div className="flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-sans text-2xs font-medium uppercase tracking-label px-2 py-0.5 border text-down border-down/30 bg-down/5">
                    FAIL — archive
                  </span>
                  <span className="font-sans text-2xs text-muted uppercase tracking-label">Not a live book · not promoted</span>
                </div>
                <h3 className="font-display font-bold text-xl text-ink leading-tight mb-2">Wide-panel FAILs — rigor signal</h3>
                <p className="font-serif text-sm text-body leading-relaxed mb-3">
                  Spectral RP, Regime-Aware Dual-Regime, and vol-cond-factor-corr (#13) failed binding
                  nulls on Sharpe. Documented on purpose — these failures are the trust signal, not a
                  parallel product shelf. Research record only.
                </p>
                <Link
                  to="/archive"
                  className="font-sans text-2xs text-muted hover:text-body underline underline-offset-2 decoration-border no-underline hover:no-underline"
                >
                  View Methods / Archive scoreboard →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Key findings — 2 shortlist findings only, compact Archive link ── */}
      <section className="py-10 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Key findings" />

          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6">
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "Static core + unconditional Book-2 VT. Everything else failed binding nulls — research record only."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase font-sans">
                Live shortlist rationale ·{' '}
                <Link to="/books" className="text-accent/70 hover:text-accent no-underline">see shortlist →</Link>
              </cite>
            </div>
            <div className="quote-block">
              <p className="font-serif text-base md:text-lg italic text-ink leading-snug">
                "Path and risk improvement, not return alpha. NW t vs static A ≈ 0 on this panel — milder drawdown is the claim. Book-1 and Book-2 earn the same ~14.7% per year."
              </p>
              <cite className="text-2xs text-muted not-italic mt-2 block tracking-label uppercase font-sans">
                Book-2 vol-target evidence ·{' '}
                <Link to="/runs" className="text-accent/70 hover:text-accent no-underline">see OOS charts →</Link>
              </cite>
            </div>
          </div>

          {/* Compact Archive scoreboard link */}
          <div className="mt-6 pt-6 border-t border-border/60">
            <p className="font-sans text-2xs text-muted uppercase tracking-label mb-2">Methods / Archive</p>
            <p className="font-sans text-xs text-body mb-3">
              Justina round-1 (Spectral RP, Regime-Aware) and #13 (vol-cond-factor-corr) — all failed
              binding-null gates. Wide-panel failures documented as the rigor record.
            </p>
            <Link
              to="/archive"
              className="font-sans inline-flex items-center gap-2 border border-border text-body text-xs font-medium px-4 py-2 no-underline hover:border-border-bright hover:text-ink transition-all"
            >
              Archive scoreboard →
            </Link>
          </div>

          {/* Progressive disclosure — supporting OOS metrics */}
          <div className="mt-8">
            <DisclosureSection summary="Supporting OOS data — Book-2 vs Book-1 metrics (expand)">
              {m && (
                <div className="p-5">
                  <p className="font-serif text-sm text-body mb-4">
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
                  <p className="font-sans text-xs text-muted mb-4">
                    Moreira &amp; Muir (2017) · mean f = {m.mean_f.toFixed(2)} · months with f&lt;1:{' '}
                    {(100 * m.pct_months_f_lt_1).toFixed(0)}%
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      to="/runs"
                      className="font-sans inline-flex items-center gap-2 bg-ink text-bg text-sm font-medium px-4 py-2 no-underline hover:bg-ink/80 transition-colors"
                    >
                      Open OOS charts
                    </Link>
                    <Link
                      to="/books"
                      className="font-sans inline-flex items-center gap-2 border border-border text-body text-sm font-medium px-4 py-2 no-underline hover:border-border-bright hover:text-ink transition-all"
                    >
                      Live shortlist weights
                    </Link>
                  </div>
                </div>
              )}
            </DisclosureSection>
          </div>
        </div>
      </section>

      {/* ── Lab sections footer nav — 4 sections per CIO IA ── */}
      <section className="py-10">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Lab sections" />
          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
            {[
              {
                to: '/books',
                eyebrow: 'Shortlist',
                title: 'Books',
                desc: 'Live Books 1–2 — static core and vol-target. Current weights and comparison table.',
              },
              {
                to: '/archive',
                eyebrow: 'Methods · Archive',
                title: 'Archive',
                desc: 'Failed wide-panel runs — Justina round-1, #13. Binding-null reference, not a book shelf.',
              },
              {
                to: '/explorer',
                eyebrow: 'Explorer (sandbox)',
                title: 'Explorer',
                desc: 'Research sandbox — time-series explorer, not a live shortlist peer.',
              },
              {
                to: '/universe',
                eyebrow: 'Universe',
                title: 'Universe',
                desc: 'Issuer universe — USA ETF panel constituents and coverage chips.',
              },
            ].map(item => (
              <Link key={item.to} to={item.to} className="no-underline block group">
                <div className="border border-border/60 bg-transparent px-4 py-3.5 h-full transition-colors group-hover:border-border group-hover:bg-surface/50">
                  <p className="section-eyebrow mb-1 text-muted/70">{item.eyebrow}</p>
                  <h3 className="font-display font-semibold text-lg text-ink/90 mb-1 leading-tight group-hover:text-ink">{item.title}</h3>
                  <p className="font-sans text-xs text-muted leading-relaxed">{item.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
