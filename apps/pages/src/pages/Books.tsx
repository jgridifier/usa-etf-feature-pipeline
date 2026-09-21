import { Link } from 'react-router-dom'
import { WeightsChart } from '../components/charts/WeightsChart'
import { XsdChart } from '../components/charts/XsdChart'
import { ComparisonTable } from '../components/ComparisonTable'
import { dataUrl } from '../lib/utils'

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

export default function Books() {
  return (
    <div>
      {/* ── Page header ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-10 pb-12">
          <Eyebrow>Live shortlist</Eyebrow>
          <h2 className="font-display font-black text-4xl md:text-5xl text-ink leading-tight mt-2 mb-5 text-balance">
            Live research shortlist
          </h2>
          <p className="text-base text-body max-w-2xl leading-relaxed mb-4">
            Two books on the experimental USA ETF panel. Everything that failed the leakage / null /
            DSR gate is archived — not promoted here.
          </p>
          <div className="inline-block border border-border rounded-lg px-3 py-2 text-xs text-muted bg-surface">
            Research only — not investment advice. Panel is an arbitrary experimental USA ETF set
            for methodology work.
          </div>
        </div>
      </section>

      {/* ── CIO copy slot — standing books ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="CIO note · standing books" />

          {/* [CIO: the block below is the primary copy slot for shortlist framing] */}
          <div className="mt-8 border border-border rounded-xl bg-surface px-6 py-5 mb-8">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent text-sm leading-none">◆</span>
              <span className="text-2xs font-medium uppercase tracking-label text-muted">CIO frame</span>
            </div>
            <p className="font-serif text-lg md:text-xl italic text-ink leading-snug mb-3">
              Live composition unchanged: static core + Book-2 VT only. XSD is an optional gated
              sleeve — not a live book.
            </p>
            <p className="text-sm text-body leading-relaxed">
              Justina round-1 and the Book-2 conditional-correlation upgrade (#13) did not clear
              binding nulls on Sharpe. <strong>No book cut.</strong> Next method candidates must
              clear the same leakage · null · DSR · empirical gate before CoS design-pass or
              promoted Pages.
            </p>
          </div>

          {/* Book cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
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
              <p className="text-xs uppercase tracking-label text-muted mb-5">
                Buy-and-hold reference
              </p>
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
              <div className="mt-5 pt-4 border-t border-border text-2xs text-muted leading-relaxed">
                OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~15.9% vol · MaxDD ~−25.6% ·
                Sharpe ~0.92 · ~68 months (2021-02 → 2026-09). Turnover ≈ 0.
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
              <p className="text-xs uppercase tracking-label text-muted mb-5">
                Default research path
              </p>
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
              <div className="mt-5 pt-4 border-t border-border text-2xs text-muted leading-relaxed">
                OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~13.9% vol · MaxDD ~−20.1% ·
                Sharpe ~1.06 · same window. Modest turnover from scaling.
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

      {/* ── Comparison ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Strategy comparison" />
          <div className="mt-8">
            <Eyebrow>Strategy comparison</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              From <code>strategy_comparison.csv</code> (live Books 1–2; optional XSD sleeve may appear).
            </p>
            <ComparisonTable />
          </div>
        </div>
      </section>

      {/* ── Weights charts ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Current weights" />
          <div className="mt-8">
            <Eyebrow>Current weights</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Latest as-of bars from monthly weights / suggested_weights. Not a live broker allocation.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="border border-border bg-surface rounded-xl p-4">
                <p className="section-eyebrow mb-3">Book 1 — Static core</p>
                <WeightsChart bookId="static_option_a" />
              </div>
              <div className="border border-border bg-surface rounded-xl p-4">
                <p className="section-eyebrow mb-3">Book 2 — Vol-target</p>
                <WeightsChart bookId="vol_target_option_a" />
              </div>
            </div>
            {/* XSD: demoted — optional gated sleeve, never a standing-book peer */}
            <div className="mt-4 border border-dashed border-border/70 bg-bg/40 rounded-lg p-3 opacity-70 max-w-md">
              <p className="section-eyebrow mb-2 text-muted/80">Optional gated sleeve — XSD</p>
              <WeightsChart bookId="score_rotate_xsd" />
              <p className="text-2xs text-muted mt-2">
                <code>score_rotate_xsd</code> is default <strong>OFF</strong>. Not a live book.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── XSD timeline ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Optional sleeve" />
          <div className="mt-8">
            <Eyebrow>XSD ON / OFF</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              ScoreSimple gate from <code>strategy_diagnostics.csv</code> (<code>on</code> /{' '}
              <code>rotate_on</code>). Optional sleeve only.
            </p>
            <div className="border border-border bg-surface rounded-xl p-5">
              <XsdChart />
            </div>
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
