import { Link } from 'react-router-dom'
import { XsdChart } from '../components/charts/XsdChart'
import { ComparisonTable } from '../components/ComparisonTable'
import { useJsonData } from '../hooks/useJsonData'
import { pct, num, dataUrl } from '../lib/utils'

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

/** CIO verdict band — 3-beat summary for Books page */
function CioVerdictBand() {
  return (
    <div className="border border-border/80 rounded-xl bg-surface overflow-hidden mb-5">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2">
        <span className="text-accent text-xs leading-none">◆</span>
        <span className="text-2xs font-medium uppercase tracking-label text-muted">CIO verdict · plain language</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border">
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-up whitespace-nowrap md:mb-1.5">HOLD</p>
          <div>
            <p className="text-sm text-ink leading-snug font-medium md:mb-1">Static core + Book-2 vol-target</p>
            <p className="hidden md:block text-2xs text-body leading-relaxed">
              Both books are on the live shortlist. No new books from Justina round-1 or #13.
            </p>
          </div>
        </div>
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-down whitespace-nowrap md:mb-1.5">DO NOT PROMOTE</p>
          <div>
            <p className="text-sm text-ink leading-snug font-medium md:mb-1">Archive fails · XSD sleeve off</p>
            <p className="hidden md:block text-2xs text-body leading-relaxed">
              Spectral RP, Regime-Aware, #13 — binding-null failures, archived only.
              XSD is default <strong>OFF</strong> — never a peer to Books 1–2.
            </p>
          </div>
        </div>
        <div className="flex md:block items-start gap-3 px-3 py-3 md:px-5 md:py-4">
          <p className="text-2xs font-semibold uppercase tracking-label text-accent whitespace-nowrap md:mb-1.5">SHIFT MEANING</p>
          <div>
            <p className="text-sm text-ink leading-snug font-medium md:mb-1">Book-2 = risk path, not return alpha</p>
            <p className="hidden md:block text-2xs text-body leading-relaxed">
              Book-1 and Book-2 earn ~14.7% ann. return. Choosing Book-2 buys milder drawdowns
              and higher Sharpe — not better absolute return.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/** HTML/CSS weight proportion bar for a single asset */
function WeightBar({ ticker, weight }: { ticker: string; weight: number }) {
  const pctWidth = Math.round(weight * 100)
  const colors: Record<string, string> = {
    VOO: 'bg-accent',
    QQQM: 'bg-up',
    IJR: 'bg-accent/60',
    BIL: 'bg-muted',
  }
  const bar = colors[ticker] ?? 'bg-border-bright'
  return (
    <div className="flex items-center gap-2.5 py-1">
      <span className="font-mono text-2xs text-muted w-10 shrink-0">{ticker}</span>
      <div className="flex-1 h-4 bg-raised rounded overflow-hidden">
        <div
          className={`h-full ${bar} rounded transition-all`}
          style={{ width: `${pctWidth}%` }}
        />
      </div>
      <span className="font-mono text-2xs text-ink w-9 text-right shrink-0">
        {pctWidth}%
      </span>
    </div>
  )
}

/** HTML/CSS weight composition display for a book */
function BookWeightArt({
  title,
  weights,
  note,
}: {
  title: string
  weights: { ticker: string; weight: number }[]
  note?: React.ReactNode
}) {
  return (
    <div className="border border-border bg-surface rounded-xl p-4">
      {title && <p className="section-eyebrow mb-3">{title}</p>}
      <div className="space-y-0.5">
        {weights.map(w => (
          <WeightBar key={w.ticker} ticker={w.ticker} weight={w.weight} />
        ))}
      </div>
      {note && <div className="text-2xs text-muted mt-3 pt-2 border-t border-border">{note}</div>}
    </div>
  )
}

/** HTML/CSS delta strip: Book-2 vs Book-1 — MaxDD delta uses absolute pp */
function DeltaStrip({ m }: { m: MetricsPayload }) {
  const sharpeDelta = m.Sharpe_vt - m.Sharpe_a
  const ddPp = (Math.abs(m.MaxDD_a) - Math.abs(m.MaxDD_vt)) * 100
  const volDelta = m.AnnVol_a - m.AnnVol_vt

  const items = [
    {
      label: 'Sharpe (rf=0)',
      vt: num(m.Sharpe_vt, 2),
      base: num(m.Sharpe_a, 2),
      delta: `+${num(sharpeDelta, 2)}`,
      good: true,
      vtBar: Math.min(100, (m.Sharpe_vt / 1.5) * 100),
      baseBar: Math.min(100, (m.Sharpe_a / 1.5) * 100),
    },
    {
      label: 'Max drawdown',
      vt: pct(m.MaxDD_vt),
      base: pct(m.MaxDD_a),
      delta: `+${ddPp.toFixed(1)}pp milder`,
      good: true,
      vtBar: Math.min(100, (Math.abs(m.MaxDD_vt) / 0.4) * 100),
      baseBar: Math.min(100, (Math.abs(m.MaxDD_a) / 0.4) * 100),
    },
    {
      label: 'Ann. vol',
      vt: pct(m.AnnVol_vt),
      base: pct(m.AnnVol_a),
      delta: `−${pct(volDelta)} lower`,
      good: true,
      vtBar: Math.min(100, (m.AnnVol_vt / 0.25) * 100),
      baseBar: Math.min(100, (m.AnnVol_a / 0.25) * 100),
    },
    {
      label: 'NW t vs Book-1',
      vt: num(m.NW_t, 2),
      base: '—',
      delta: '≈ 0 (risk path only)',
      good: null as boolean | null,
      vtBar: null as number | null,
      baseBar: null as number | null,
    },
  ]

  return (
    <div className="border border-border rounded-xl bg-surface overflow-hidden mb-6">
      <div className="px-4 py-2.5 border-b border-border">
        <span className="text-2xs font-medium uppercase tracking-label text-muted">
          Book-2 vs Book-1 · {m.n_months}mo OOS · {m.start_date} → {m.end_date}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-border">
        {items.map(item => (
          <div key={item.label} className="px-4 py-4">
            <p className="text-2xs text-muted uppercase tracking-label mb-2">{item.label}</p>
            {item.vtBar != null && (
              <div className="mb-3 space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-3xs text-muted/70 w-10 shrink-0">Book-2</span>
                  <div className="flex-1 h-4 bg-raised rounded overflow-hidden">
                    <div className="h-full bg-accent rounded" style={{ width: `${item.vtBar}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-3xs text-muted/70 w-10 shrink-0">Book-1</span>
                  <div className="flex-1 h-4 bg-raised rounded overflow-hidden">
                    <div className="h-full bg-border-bright rounded" style={{ width: `${item.baseBar!}%` }} />
                  </div>
                </div>
              </div>
            )}
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="font-mono text-base text-ink font-semibold">{item.vt}</span>
              <span className="text-2xs text-muted">vs {item.base}</span>
            </div>
            <p className={`text-2xs mt-1 font-medium ${
              item.good === true ? 'text-up' : item.good === false ? 'text-down' : 'text-muted'
            }`}>
              {item.delta}
            </p>
          </div>
        ))}
      </div>
      <div className="px-4 py-2 border-t border-border bg-raised">
        <p className="text-2xs text-muted/70">
          <strong className="text-muted">Same ~14.7% ann. return as Book-1 — shift buys milder drawdowns + higher Sharpe, not outperformance.</strong>{' '}
          <Link to="/runs" className="text-accent/80 hover:text-accent no-underline">See full OOS charts →</Link>
        </p>
      </div>
    </div>
  )
}

/**
 * Progressive disclosure using native <details>/<summary>.
 * No React state — keyboard, click, and automated harnesses all work natively.
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
      className="group border border-border rounded-xl overflow-hidden"
    >
      <summary className="list-none w-full flex items-center justify-between px-4 py-3 bg-surface hover:bg-raised transition-colors cursor-pointer gap-2 select-none [&::-webkit-details-marker]:hidden">
        <span className="text-sm font-medium text-ink">{summary}</span>
        <span className="text-muted text-xs flex-shrink-0 group-open:hidden">▼ expand</span>
        <span className="text-muted text-xs flex-shrink-0 hidden group-open:inline">▲ collapse</span>
      </summary>
      <div className="border-t border-border bg-bg">
        {children}
      </div>
    </details>
  )
}

export default function Books() {
  const { data: m } = useJsonData<MetricsPayload>('viz_metrics.json')

  return (
    <div>
      {/* ── Page header ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-8 pb-10">
          <Eyebrow>Live shortlist</Eyebrow>
          <h2 className="font-display font-black text-3xl md:text-5xl text-ink leading-tight mt-2 mb-4 text-balance">
            Live research shortlist
          </h2>
          <p className="text-sm text-body max-w-2xl leading-relaxed mb-5">
            Two books on the experimental USA ETF panel. Everything that failed the leakage / null /
            DSR gate is archived — not promoted here.
          </p>

          {/* CIO verdict band — above fold, plain language */}
          <CioVerdictBand />

          {/* Book-2 vs Book-1 delta strip — HTML/CSS proportion mosaic */}
          {m && <DeltaStrip m={m} />}

          <div className="inline-block border border-border rounded-lg px-3 py-2 text-xs text-muted bg-surface">
            Research only — not investment advice. Panel is an arbitrary experimental USA ETF set
            for methodology work.
          </div>
        </div>
      </section>

      {/* ── Standing book cards (layer 1 — overview) ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Standing books · overview" />

          {/* Book cards — layer 1 */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Book 1 */}
            <article className="article-card p-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-2xs font-medium uppercase tracking-label px-2 py-0.5 rounded-full border border-up/30 text-up bg-up/5">
                  Book 1 · live
                </span>
              </div>
              <h3 className="font-display font-bold text-2xl text-ink mb-1 leading-tight">
                Static core
              </h3>
              <p className="text-xs uppercase tracking-label text-muted mb-3">
                Buy-and-hold reference
              </p>
              <p className="text-sm text-body leading-relaxed mb-4">
                Fixed weights <strong>VOO 70% / QQQM 20% / IJR 10%</strong>. No timing, no
                vol scale. Clean null for any overlay or timing claim.
              </p>
              <div className="text-2xs text-muted pt-3 border-t border-border">
                OOS snapshot: ~14.7% ann. return · ~15.9% vol · MaxDD ~−25.6% · Sharpe ~0.92 · 68 months
              </div>
            </article>

            {/* Book 2 */}
            <article className="article-card p-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-2xs font-medium uppercase tracking-label px-2 py-0.5 rounded-full border border-up/30 text-up bg-up/5">
                  Book 2 · live
                </span>
              </div>
              <h3 className="font-display font-bold text-2xl text-ink mb-1 leading-tight">
                Vol-target
              </h3>
              <p className="text-xs uppercase tracking-label text-muted mb-3">
                Risk path — not return alpha
              </p>
              <p className="text-sm text-body leading-relaxed mb-4">
                Same Option A core, scaled by estimated volatility (scale-down only). Cash in{' '}
                <strong>BIL</strong> when risk is high. Same ~14.7% return as Book 1 — the
                shift is milder drawdown (−20% vs −26%) and higher Sharpe (1.06 vs 0.92).
              </p>
              <div className="text-2xs text-muted pt-3 border-t border-border">
                OOS snapshot: ~14.7% ann. return · ~13.9% vol · MaxDD ~−20.1% · Sharpe ~1.06 · 68 months
              </div>
            </article>
          </div>

          {/* Not on shortlist callout */}
          <div className="mt-5 border border-down/20 bg-down/5 rounded-xl px-5 py-4 text-sm text-muted">
            <strong className="text-ink">Not on the shortlist:</strong>{' '}
            Spectral risk parity, Regime-aware dual-regime, Vol-cond factor corr #13 — all{' '}
            <strong className="text-down">FAIL — archive</strong>. Full table:{' '}
            <Link to="/archive" className="text-muted hover:text-body underline underline-offset-2 decoration-border">
              Archive / Justina round-1 scoreboard
            </Link>.
          </div>
        </div>
      </section>

      {/* ── Layer 2: expand for full book detail ── */}
      <section className="py-8 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Deep detail" />
          <div className="mt-6 space-y-3">

            <DisclosureSection summary="Book 1 — Static core: full detail (WHAT / WHY / WHAT IT IS NOT)">
              <div className="p-6">
                <dl className="space-y-4 text-sm">
                  <div>
                    <dt className="section-eyebrow mb-0.5">What it is</dt>
                    <dd className="text-body leading-relaxed">
                      Fixed weights <strong>VOO 70% / QQQM 20% / IJR 10%</strong>. No timing, no
                      vol scale. Strategy id <code>static_option_a</code>.
                    </dd>
                  </div>
                  <div>
                    <dt className="section-eyebrow mb-0.5">Why it's on the shortlist</dt>
                    <dd className="text-body leading-relaxed">
                      Clean null for "did timing or risk management add anything?" Every overlay is
                      judged against this path (and against Book 2 when the claim is risk-managed).
                    </dd>
                  </div>
                  <div>
                    <dt className="section-eyebrow mb-0.5">What it is not</dt>
                    <dd className="text-body leading-relaxed">
                      Not a Justina method. Not a multifactor optimizer showcase.
                    </dd>
                  </div>
                </dl>
              </div>
            </DisclosureSection>

            <DisclosureSection summary="Book 2 — Vol-target: full detail (WHAT / WHY / WHAT IT IS NOT)">
              <div className="p-6">
                <dl className="space-y-4 text-sm">
                  <div>
                    <dt className="section-eyebrow mb-0.5">What it is</dt>
                    <dd className="text-body leading-relaxed">
                      Same Option A core, scaled by estimated volatility (scale-down only in v1);
                      cash residual in <strong>BIL</strong> when risk is high. Strategy id{' '}
                      <code>vol_target_option_a</code>.
                    </dd>
                  </div>
                  <div>
                    <dt className="section-eyebrow mb-0.5">Why it's on the shortlist</dt>
                    <dd className="text-body leading-relaxed">
                      On this panel it improves the risk path vs Book 1 (higher Sharpe_rf0, milder
                      MaxDD) without a strong return-alpha claim vs static (NW t vs Book 1 ≈ 0). A{' '}
                      <strong>path/risk</strong> book, not a "beat the market" story.
                    </dd>
                  </div>
                  <div>
                    <dt className="section-eyebrow mb-0.5">What it is not</dt>
                    <dd className="text-body leading-relaxed">
                      Not the archived conditional factor-corr overlay (#13), which{' '}
                      <strong>failed</strong> vs this unconditional Book 2 on Sharpe.
                    </dd>
                  </div>
                </dl>
              </div>
            </DisclosureSection>

          </div>
        </div>
      </section>

      {/* ── Current weights — HTML/CSS proportion art ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Current weights" />
          <div className="mt-8">
            <Eyebrow>Current weights</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Latest as-of bars from monthly weights / suggested_weights. Not a live broker allocation.
            </p>

            {/* Books 1 & 2 only — HTML/CSS proportion bars */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-4">
              <BookWeightArt
                title="Book 1 — Static core"
                weights={[
                  { ticker: 'VOO', weight: 0.70 },
                  { ticker: 'QQQM', weight: 0.20 },
                  { ticker: 'IJR', weight: 0.10 },
                ]}
                note="Fixed. No rebalancing trigger beyond periodic drift check."
              />
              <BookWeightArt
                title="Book 2 — Vol-target"
                weights={[
                  { ticker: 'VOO', weight: 0.70 },
                  { ticker: 'QQQM', weight: 0.20 },
                  { ticker: 'IJR', weight: 0.10 },
                  { ticker: 'BIL', weight: 0.00 },
                ]}
                note={
                  <>
                    <strong className="text-ink">BIL 0% as-of</strong> — current vol estimate is low (f_t ≈ 1.0).{' '}
                    Historically BIL receives cash when f_t &lt; 1: in this OOS window,{' '}
                    {m
                      ? `${(m.pct_months_f_lt_1 * 100).toFixed(0)}% of months had f<1 (mean f = ${m.mean_f.toFixed(2)})`
                      : 'a meaningful fraction of months had f<1'
                    }.{' '}
                    <Link to="/runs" className="text-accent/70 hover:text-accent no-underline">
                      See f_t path →
                    </Link>
                  </>
                }
              />
            </div>

            {/* XSD sleeve — collapsed by default, clearly demoted */}
            <DisclosureSection summary="Optional gated sleeve — XSD (default OFF, not a live book — expand to view)">
              <div className="p-5">
                <div className="border border-dashed border-border/70 rounded-lg p-4 bg-bg/60 max-w-md">
                  <p className="section-eyebrow mb-2 text-muted/80">Optional gated sleeve — XSD</p>
                  <BookWeightArt
                    title=""
                    weights={[
                      { ticker: 'VOO', weight: 0.65 },
                      { ticker: 'QQQM', weight: 0.20 },
                      { ticker: 'IJR', weight: 0.10 },
                      { ticker: 'BIL', weight: 0.05 },
                    ]}
                  />
                  <p className="text-2xs text-muted mt-3">
                    <code>score_rotate_xsd</code> is default <strong>OFF</strong>. Gate must be ON for this to be
                    active. Not a live book — never a peer to Books 1–2.
                  </p>
                </div>
              </div>
            </DisclosureSection>
          </div>
        </div>
      </section>

      {/* ── Strategy comparison — Books 1-2 first, XSD subordinate ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Strategy comparison" />
          <div className="mt-8">
            <Eyebrow>Strategy comparison</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Live Books 1–2 vs benchmark. Optional XSD sleeve shown last, subordinate — not a peer.
            </p>
            <ComparisonTable />
          </div>
        </div>
      </section>

      {/* ── XSD timeline — in progressive disclosure ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Optional sleeve diagnostics" />
          <div className="mt-8">
            <DisclosureSection summary="XSD ON/OFF gate timeline — optional sleeve only (expand to view chart)">
              <div className="p-5">
                <p className="text-sm text-body mb-4">
                  ScoreSimple gate from <code>strategy_diagnostics.csv</code> (<code>on</code> /{' '}
                  <code>rotate_on</code>). Optional sleeve only — not a live book.
                </p>
                <div className="border border-border bg-surface rounded-xl p-5">
                  <XsdChart />
                </div>
              </div>
            </DisclosureSection>
          </div>
        </div>
      </section>

      {/* ── Weight snapshot table ── */}
      <section className="py-12">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Data" />
          <div className="mt-8">
            <Eyebrow>Weight snapshot</Eyebrow>
            <div className="mt-4">
              <WeightSnapshotTable />
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

function WeightSnapshotTable() {
  const rows = [
    { strategy_id: 'static_option_a',    ticker: 'VOO',  weight: '0.7', basis: 'static research template' },
    { strategy_id: 'static_option_a',    ticker: 'QQQM', weight: '0.2', basis: 'static research template' },
    { strategy_id: 'static_option_a',    ticker: 'IJR',  weight: '0.1', basis: 'static research template' },
    { strategy_id: 'vol_target_option_a', ticker: 'VOO',  weight: '0.7', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'QQQM', weight: '0.2', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'IJR',  weight: '0.1', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'BIL',  weight: '0.0', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
  ]

  return (
    <div
      className="overflow-x-auto rounded-xl border border-border"
      tabIndex={0}
      role="region"
      aria-label="Latest weights snapshot"
    >
      <table className="w-full text-xs whitespace-nowrap">
        <thead>
          <tr className="border-b border-border bg-raised">
            {['strategy_id', 'ticker', 'weight', 'basis'].map(h => (
              <th
                key={h}
                className={`px-4 py-3 font-medium text-muted uppercase tracking-label text-2xs ${
                  h === 'weight' ? 'text-right' : 'text-left'
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0 hover:bg-raised transition-colors">
              <td className="px-4 py-3 font-mono text-muted">{r.strategy_id}</td>
              <td className="px-4 py-3 font-mono font-medium text-ink">{r.ticker}</td>
              <td className="px-4 py-3 font-mono text-right text-ink">{r.weight}</td>
              <td className="px-4 py-3 text-muted">{r.basis}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-4 py-2.5 border-t border-border bg-raised text-2xs">
        <a
          href={dataUrl('latest_weights_snapshot.csv')}
          className="text-accent hover:text-accent/80 no-underline"
          download
        >
          Download CSV
        </a>
      </div>
    </div>
  )
}
