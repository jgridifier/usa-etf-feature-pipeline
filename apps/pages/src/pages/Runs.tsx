import { EquityChart, DrawdownChart } from '../components/charts/EquityDrawdownChart'
import { FtChart, WBilChart } from '../components/charts/FtChart'
import { dataUrl } from '../lib/utils'
import { useJsonData } from '../hooks/useJsonData'
import { pct, num } from '../lib/utils'
import { ArrowDownToLine } from 'lucide-react'
import { Link } from 'react-router-dom'

interface MetricsPayload {
  trial_id: string
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

/** Compact CIO strip for Runs — keeps HOLD / DO NOT PROMOTE / risk-path framing
 *  above the KPI cards so Sharpe 1.06 is never the first story on this page.
 */
function RunsCioStrip() {
  return (
    <div className="border border-border/70 rounded-xl bg-surface overflow-hidden mb-6">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2">
        <span className="text-accent text-xs leading-none">◆</span>
        <span className="text-2xs font-medium uppercase tracking-label text-muted">CIO context · reading these charts</span>
      </div>
      <div className="flex flex-wrap gap-0 divide-y md:divide-y-0 md:divide-x divide-border">
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="text-2xs font-semibold uppercase tracking-label text-up whitespace-nowrap">HOLD</span>
          <span className="text-2xs text-body">Static core + Book-2 VT — both on live shortlist.</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="text-2xs font-semibold uppercase tracking-label text-down whitespace-nowrap">DO NOT PROMOTE</span>
          <span className="text-2xs text-body">Archive + XSD sleeve off — see{' '}
            <Link to="/archive" className="text-accent/70 hover:text-accent no-underline">archive →</Link>
          </span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="text-2xs font-semibold uppercase tracking-label text-accent whitespace-nowrap">SHIFT MEANING</span>
          <span className="text-2xs text-body">Same ~14.7% return — claim is risk path, not return alpha. Higher Sharpe reflects milder drawdown, not outperformance.</span>
        </div>
      </div>
    </div>
  )
}

export default function Runs() {
  const { data: m } = useJsonData<MetricsPayload>('viz_metrics.json')

  return (
    <div>
      {/* ── Page header ── */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-10 pb-10">
          <Eyebrow>Out-of-sample</Eyebrow>
          <h2 className="font-display font-black text-4xl md:text-5xl text-ink leading-tight mt-2 mb-4 text-balance">
            OOS charts
          </h2>
          <p className="text-base text-body max-w-xl leading-relaxed">
            Equity, drawdown, scale factor f<sub>t</sub>, and downloadable CSVs for the live path.
            {m && <> {m.n_months}-month OOS: {m.start_date} → {m.end_date}.</>}
          </p>
        </div>
      </section>

      {/* ── OOS summary metrics — CIO strip leads, Sharpe is context not headline ── */}
      {m && (
        <section className="py-10 bg-hero-gradient border-b border-border">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <SectionRule label="Context + summary" />
            <div className="mt-6">
              {/* CIO HOLD / DO NOT PROMOTE / SHIFT strip — must read before KPI numbers */}
              <RunsCioStrip />

              <Eyebrow>OOS snapshot — Book-2 vol-target</Eyebrow>
              <p className="text-sm text-body mt-1 mb-5 max-w-2xl">
                Moreira &amp; Muir (2017) · mean f = {m.mean_f.toFixed(2)} · months with f&lt;1:{' '}
                {(100 * m.pct_months_f_lt_1).toFixed(0)}% · rf=0 Sharpe parity.
              </p>
              {/* MaxDD and risk metrics lead; Sharpe is secondary context */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="stat-card">
                  <div className="stat-label">Max DD (vt)</div>
                  <div className="stat-value text-down">{pct(m.MaxDD_vt)}</div>
                  <div className="stat-sub">Static A: {pct(m.MaxDD_a)} — risk-path claim</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Ann. return (vt)</div>
                  <div className="stat-value">{pct(m.AnnReturn_vt)}</div>
                  <div className="stat-sub">Static A: {pct(m.AnnReturn_a)} — same path</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Ann. vol (vt)</div>
                  <div className="stat-value">{pct(m.AnnVol_vt)}</div>
                  <div className="stat-sub">Static A: {pct(m.AnnVol_a)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Sharpe (vt)</div>
                  <div className="stat-value text-body">{num(m.Sharpe_vt)}</div>
                  <div className="stat-sub">Static A: {num(m.Sharpe_a)} — higher via milder DD</div>
                </div>
              </div>
              <p className="text-xs text-muted">
                NW t vs static A: <strong className="text-body">{num(m.NW_t)}</strong> — ≈ 0, confirming
                risk-path improvement, not return alpha. Sharpe is higher because drawdown is milder.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Equity ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Chart" />
          <div className="mt-8">
            <Eyebrow>Cumulative wealth</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Book 2 vol-target vs static Option A (Book 1). Base = 1.0 at OOS start.
            </p>
            <div className="border border-border bg-surface rounded-xl p-5">
              <EquityChart />
            </div>
          </div>
        </div>
      </section>

      {/* ── Drawdown ── */}
      <section className="py-12 bg-hero-gradient border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Chart" />
          <div className="mt-8">
            <Eyebrow>Drawdown</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Rolling drawdown from peak. Milder MaxDD for vol-target is the primary risk-path claim.
            </p>
            <div className="border border-border bg-surface rounded-xl p-5">
              <DrawdownChart />
            </div>
          </div>
        </div>
      </section>

      {/* ── f_t ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Scale factor" />
          <div className="mt-8">
            <Eyebrow>Monthly scale factor f_t</Eyebrow>
            <p className="text-sm text-body mt-1 mb-6 max-w-2xl">
              Clip(σ* / σ̂_t, f_min=0.25, f_max=1.0). Scale-down only. Months where f&lt;1 indicate
              elevated estimated volatility — BIL receives cash when f&lt;1.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="border border-border bg-surface rounded-xl p-5">
                <FtChart />
              </div>
              <div className="border border-border bg-surface rounded-xl p-5">
                <WBilChart />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Downloads ── */}
      <section className="py-12">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Data" />
          <div className="mt-8">
            <Eyebrow>Download CSVs</Eyebrow>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { label: 'OOS returns',        file: 'vol_target_oos_returns.csv' },
                { label: 'OOS summary',         file: 'vol_target_oos_summary.csv' },
                { label: 'Monthly weights',     file: 'vol_target_monthly_weights.csv' },
                { label: 'Trial registry',      file: 'vol_target_trial_registry.csv' },
                { label: 'Strategy comparison', file: 'strategy_comparison.csv' },
                { label: 'Suggested weights',   file: 'suggested_weights.csv' },
              ].map(({ label, file }) => (
                <a
                  key={file}
                  href={dataUrl(file)}
                  className="flex items-center gap-3 border border-border bg-surface rounded-xl px-4 py-3 text-sm text-body hover:border-border-bright hover:bg-raised hover:text-ink transition-all no-underline group"
                  download
                >
                  <ArrowDownToLine
                    size={14}
                    className="flex-shrink-0 text-muted group-hover:text-accent transition-colors"
                  />
                  <span className="flex-1">{label}</span>
                  <code className="text-2xs text-muted/50 font-mono">{file}</code>
                </a>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
