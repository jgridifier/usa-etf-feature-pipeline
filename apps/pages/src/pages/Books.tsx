import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/badge'
import { WeightsChart } from '../components/charts/WeightsChart'
import { XsdChart } from '../components/charts/XsdChart'
import { ComparisonTable } from '../components/ComparisonTable'
import { dataUrl } from '../lib/utils'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-1">{children}</p>
  )
}

function SectionHead({
  label,
  title,
  sub,
}: {
  label?: string
  title: string
  sub?: React.ReactNode
}) {
  return (
    <div className="mb-6 md:mb-8">
      {label && <SectionLabel>{label}</SectionLabel>}
      <h2 className="text-2xl font-bold text-ink mb-2">{title}</h2>
      {sub && <p className="text-body text-sm max-w-2xl leading-relaxed">{sub}</p>}
    </div>
  )
}

export default function Books() {
  return (
    <div>
      {/* ── Hero ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6 py-14 md:py-18">
          <Badge variant="live" className="mb-4">Live shortlist</Badge>
          <h1 className="text-3xl md:text-5xl font-bold text-ink mb-4 text-balance">
            Live research shortlist
          </h1>
          <p className="text-body max-w-2xl leading-relaxed mb-3">
            Two books for comparison on the experimental USA ETF panel. Everything else that failed
            the leakage / null / DSR gate is archived under{' '}
            <Link to="/archive" className="text-muted hover:text-body underline underline-offset-2 decoration-muted">
              Archive
            </Link>{' '}
            — not promoted here.
          </p>
          <div className="inline-block border border-border rounded-lg px-3 py-2 text-xs text-muted bg-surface">
            Research only — not investment advice. Panel is an arbitrary experimental USA ETF set for
            methodology work.
          </div>
        </div>
      </section>

      {/* ── CIO copy slot — standing books ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <SectionHead
            label="CIO note"
            title="Standing books"
            sub="Live composition unchanged: static core + Book-2 vol-target. Optional XSD sleeve is gated and is not Book 3."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Book 1 */}
            <article className="rounded-xl border border-border bg-surface p-6">
              <div className="flex items-start justify-between mb-4">
                <Badge variant="live">Book 1 · Static core</Badge>
              </div>
              <h3 className="text-lg font-semibold text-ink mb-4">Buy-and-hold reference</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">What it is</dt>
                  <dd className="text-body">
                    Fixed weights <strong>VOO 70% / QQQM 20% / IJR 10%</strong>. No timing, no vol
                    scale. Strategy id <code>static_option_a</code>.
                  </dd>
                </div>
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">Why it's on the shortlist</dt>
                  <dd className="text-body">
                    Clean null for "did timing or risk management add anything?" Every overlay is
                    judged against this path (and against Book 2 when the claim is risk-managed).
                  </dd>
                </div>
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">What it is not</dt>
                  <dd className="text-body">Not a Justina method. Not a multifactor optimizer showcase.</dd>
                </div>
              </dl>
              <div className="mt-4 pt-4 border-t border-border text-2xs text-muted">
                OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~15.9% vol · MaxDD ~−25.6% ·
                Sharpe ~0.92 · ~68 months (2021-02 → 2026-09). Turnover ≈ 0.
              </div>
            </article>

            {/* Book 2 */}
            <article className="rounded-xl border border-border bg-surface p-6">
              <div className="flex items-start justify-between mb-4">
                <Badge variant="live">Book 2 · Vol-target</Badge>
              </div>
              <h3 className="text-lg font-semibold text-ink mb-4">Default research path</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">What it is</dt>
                  <dd className="text-body">
                    Same Option A core, scaled by estimated volatility (scale-down only in v1); cash
                    residual in <strong>BIL</strong> when risk is high. Strategy id{' '}
                    <code>vol_target_option_a</code>.
                  </dd>
                </div>
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">Why it's on the shortlist</dt>
                  <dd className="text-body">
                    On this panel it improves the risk path vs Book 1 (higher Sharpe_rf0, milder MaxDD)
                    without a strong return-alpha claim vs static (NW t vs Book 1 ≈ 0). That is a{' '}
                    <strong>path/risk</strong> book, not a "beat the market" story.
                  </dd>
                </div>
                <div>
                  <dt className="text-2xs uppercase tracking-widest text-muted mb-0.5">What it is not</dt>
                  <dd className="text-body">
                    Not the archived conditional factor-corr overlay (#13), which{' '}
                    <strong>failed</strong> vs this unconditional Book 2 on Sharpe.
                  </dd>
                </div>
              </dl>
              <div className="mt-4 pt-4 border-t border-border text-2xs text-muted">
                OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~13.9% vol · MaxDD ~−20.1% ·
                Sharpe ~1.06 · same window. Modest turnover from scaling.
              </div>
            </article>
          </div>

          {/* Not on shortlist callout */}
          <div className="mt-5 rounded-xl border border-border bg-raised px-5 py-4 text-sm text-muted">
            <strong className="text-ink">Not on the shortlist:</strong>{' '}
            Spectral risk parity (null: Ledoit–Wolf MinVar), Regime-aware dual-regime (null:
            Unconditional ERC), Vol-cond factor corr #13 (null: Unconditional Book-2 VT) — all{' '}
            <strong className="text-down">FAIL — archive</strong>. Full table:{' '}
            <Link to="/archive" className="text-muted hover:text-body underline underline-offset-2 decoration-border">
              Archive / Justina round-1 scoreboard
            </Link>.
          </div>
        </div>
      </section>

      {/* ── Comparison ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <SectionHead
            label="Comparison"
            title="Strategy comparison"
            sub={<>From <code>strategy_comparison.csv</code> (live Books 1–2; optional XSD sleeve may appear).</>}
          />
          <ComparisonTable />
        </div>
      </section>

      {/* ── Weights charts ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <SectionHead
            label="Weights"
            title="Current weights"
            sub="Latest as-of bars from monthly weights / suggested_weights. Not a live broker allocation."
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-3">Book 1 — Static core</p>
              <WeightsChart bookId="static_option_a" />
            </div>
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-3">Book 2 — Vol-target</p>
              <WeightsChart bookId="vol_target_option_a" />
            </div>
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-3">Optional sleeve — XSD</p>
              <WeightsChart bookId="score_rotate_xsd" />
              <p className="text-2xs text-muted mt-2">
                <code>score_rotate_xsd</code> is default <strong>OFF</strong>. Not Book 3.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── XSD timeline ── */}
      <section className="py-12 border-b border-border bg-hero-gradient">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <SectionHead
            label="Optional sleeve"
            title="XSD ON / OFF"
            sub={<>ScoreSimple gate from <code>strategy_diagnostics.csv</code> (<code>on</code> / <code>rotate_on</code>). Optional sleeve only.</>}
          />
          <div className="rounded-xl border border-border bg-surface p-5">
            <XsdChart />
          </div>
        </div>
      </section>

      {/* ── Weight snapshot table ── */}
      <section className="py-12">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <SectionHead label="Data" title="Weight snapshot" />
          <WeightSnapshotTable />
        </div>
      </section>
    </div>
  )
}

function WeightSnapshotTable() {
  const rows = [
    { strategy_id: 'static_option_a', ticker: 'VOO', weight: '0.7', basis: 'static research template' },
    { strategy_id: 'static_option_a', ticker: 'QQQM', weight: '0.2', basis: 'static research template' },
    { strategy_id: 'static_option_a', ticker: 'IJR', weight: '0.1', basis: 'static research template' },
    { strategy_id: 'vol_target_option_a', ticker: 'VOO', weight: '0.7', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'QQQM', weight: '0.2', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'IJR', weight: '0.1', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
    { strategy_id: 'vol_target_option_a', ticker: 'BIL', weight: '0.0', basis: 'historical OOS sample: VT_option_a_L63_sigexpanding_fmax1p0' },
  ]

  return (
    <div className="overflow-x-auto rounded-xl border border-border" tabIndex={0} role="region" aria-label="Latest weights snapshot">
      <table className="w-full text-xs whitespace-nowrap">
        <thead>
          <tr className="border-b border-border bg-raised">
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-left">strategy_id</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-left">ticker</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-right">weight</th>
            <th className="px-4 py-3 font-medium text-muted uppercase tracking-wider text-2xs text-left">basis</th>
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
