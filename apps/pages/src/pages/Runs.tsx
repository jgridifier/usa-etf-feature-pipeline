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
  Sharpe_exbil_vt: number
  Sharpe_exbil_a: number
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

/** Compact CIO strip for Runs */
function RunsCioStrip() {
  return (
    <div className="border border-border bg-surface overflow-hidden mb-6">
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 bg-ink">
        <span className="font-sans text-2xs font-bold uppercase tracking-label text-bg/80">CIO context</span>
        <span className="font-sans text-2xs text-bg/40 uppercase tracking-label">Reading these charts</span>
      </div>
      <div className="flex flex-wrap gap-0 divide-y md:divide-y-0 md:divide-x divide-border">
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="font-sans text-2xs font-bold uppercase tracking-label text-up whitespace-nowrap">HOLD</span>
          <span className="font-sans text-2xs text-body">Static core + Book-2 VT — both on live shortlist.</span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="font-sans text-2xs font-bold uppercase tracking-label text-down whitespace-nowrap">DO NOT PROMOTE</span>
          <span className="font-sans text-2xs text-body">Archive + XSD sleeve off — see{' '}
            <Link to="/archive" className="text-accent/70 hover:text-accent no-underline">archive →</Link>
          </span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2.5 min-w-0">
          <span className="font-sans text-2xs font-bold uppercase tracking-label text-accent whitespace-nowrap">SHIFT MEANING</span>
          <span className="font-sans text-2xs text-body">Same ~14.7% return — claim is risk path, not return alpha.</span>
        </div>
      </div>
    </div>
  )
}

/** CSS risk-path figure — the primary above-fold visual for the Runs page.
 *  Two swimlanes: vol-target (milder DD) and static (deeper DD).
 *  No canvas, no ECharts — pure HTML/CSS composition.
 */
function RiskPathFigure({ m }: { m: MetricsPayload }) {
  const ddPp = (Math.abs(m.MaxDD_a) - Math.abs(m.MaxDD_vt)) * 100
  const rangeMax = 35 // visual scale: 0-35% drawdown range
  const vtPct   = Math.min(100, (Math.abs(m.MaxDD_vt) / rangeMax) * 100)
  const statPct = Math.min(100, (Math.abs(m.MaxDD_a) / rangeMax) * 100)

  return (
    <div className="border border-border bg-surface overflow-hidden mb-6">
      {/* Figure header — the story sentence */}
      <div className="px-4 py-3 border-b border-border bg-raised">
        <p className="font-serif text-base md:text-lg text-ink leading-snug">
          <strong>HOLD</strong> — Book-2 vol-target delivers the same return as Book 1 static with{' '}
          <span className="text-up font-semibold">+{ddPp.toFixed(1)}pp milder</span> peak drawdown.
          Risk-path improvement, not return alpha.
        </p>
      </div>

      {/* DD band composition */}
      <div className="p-4 md:p-6">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-sans text-2xs text-muted uppercase tracking-label font-medium">
            Max drawdown depth — OOS {m.n_months}mo ({m.start_date} → {m.end_date})
          </span>
          <span className="font-mono text-xs font-bold text-up">+{ddPp.toFixed(1)}pp milder</span>
        </div>

        <div className="space-y-3">
          {/* Book 2 — vol-target (milder) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="font-sans text-2xs font-bold text-up uppercase tracking-label">HOLD</span>
                <span className="font-sans text-xs text-muted">Book-2 VT backbone (no skew gate)</span>
              </div>
              <span className="font-mono text-sm font-bold text-ink">{pct(m.MaxDD_vt)}</span>
            </div>
            <div className="relative h-10 md:h-12 bg-raised border border-border overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-px bg-border-bright/40" />
              <div
                className="absolute top-0 left-0 h-full transition-all"
                style={{
                  width: `${vtPct}%`,
                  background: 'rgba(139,26,26,0.10)',
                  borderRight: '3px solid rgba(139,26,26,0.45)',
                }}
              />
              <div className="absolute inset-0 flex items-center px-3">
                <span className="font-sans text-2xs text-down/60 font-medium">
                  MaxDD {pct(m.MaxDD_vt)} ← milder peak loss · Sharpe {num(m.Sharpe_exbil_vt, 2)} ex-BIL (legacy rf=0 {num(m.Sharpe_vt, 2)})
                </span>
              </div>
            </div>
          </div>

          {/* Book 1 — static (deeper) */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="font-sans text-2xs font-bold text-ink/50 uppercase tracking-label">HOLD</span>
                <span className="font-sans text-xs text-muted">Book 1 — static</span>
              </div>
              <span className="font-mono text-sm font-bold text-ink">{pct(m.MaxDD_a)}</span>
            </div>
            <div className="relative h-10 md:h-12 bg-raised border border-border overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-px bg-border-bright/40" />
              <div
                className="absolute top-0 left-0 h-full transition-all"
                style={{
                  width: `${statPct}%`,
                  background: 'rgba(139,26,26,0.22)',
                  borderRight: '3px solid rgba(139,26,26,0.65)',
                }}
              />
              <div className="absolute inset-0 flex items-center px-3">
                <span className="font-sans text-2xs text-down/70 font-medium">
                  MaxDD {pct(m.MaxDD_a)} ← deeper peak loss · Sharpe {num(m.Sharpe_exbil_a, 2)} ex-BIL (legacy rf=0 {num(m.Sharpe_a, 2)})
                </span>
              </div>
            </div>
          </div>

          {/* Delta annotation */}
          <div className="flex items-start gap-3 pt-2 border-t border-border/60">
            <div className="flex-1">
              <p className="font-sans text-2xs text-muted leading-relaxed">
                NW t vs static A: <strong className="font-mono text-body">{num(m.NW_t, 2)}</strong>{' '}
                ≈ 0 — return parity confirmed. Sharpe is higher because drawdown is milder, not
                because Book 2 generates alpha. Ann. return: {pct(m.AnnReturn_vt)} (VT) vs{' '}
                {pct(m.AnnReturn_a)} (static).
              </p>
            </div>
          </div>
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
          <p className="font-serif text-base text-body max-w-xl leading-relaxed">
            Risk-path evidence for the live shortlist. Equity, drawdown, scale factor f
            <sub>t</sub>, and downloadable CSVs.
            {m && <> {m.n_months}-month OOS: {m.start_date} → {m.end_date}.</>}
          </p>
        </div>
      </section>

      {/* ── CIO context + MaxDD risk-path figure ── */}
      <section className="py-10 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="CIO context + risk-path" />
          <div className="mt-6">
            <RunsCioStrip />
            {m && <RiskPathFigure m={m} />}
          </div>
        </div>
      </section>

      {/* ── OOS KPI summary ── */}
      {m && (
        <section className="py-10 bg-hero-gradient border-b border-border">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <ThickRule label="OOS snapshot" />
            <div className="mt-6">
              <Eyebrow>Book-2 VT backbone (no skew gate) — key metrics</Eyebrow>
              <p className="font-sans text-sm text-body mt-1 mb-5 max-w-2xl">
                Moreira &amp; Muir (2017) · mean f = {m.mean_f.toFixed(2)} · months with f&lt;1:{' '}
                {(100 * m.pct_months_f_lt_1).toFixed(0)}% · Sharpe in excess of BIL (legacy rf = 0 kept).
                Live Book 2 adds the #6 skew gate: 0.97 in excess of BIL.
              </p>
              {/* MaxDD leads; Sharpe last with context note */}
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
                  <div className="stat-label">Sharpe ex-BIL (vt)</div>
                  <div className="stat-value text-body">{num(m.Sharpe_exbil_vt)}</div>
                  <div className="stat-sub">Static A: {num(m.Sharpe_exbil_a)} — higher via milder DD · legacy rf=0 {num(m.Sharpe_vt)} / {num(m.Sharpe_a)}</div>
                </div>
              </div>
              <p className="font-sans text-xs text-muted">
                NW t vs static A: <strong className="text-body font-mono">{num(m.NW_t)}</strong> — ≈ 0,
                confirming risk-path improvement, not return alpha.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Chart lab (collapsible) — all ECharts behind expand ── */}
      <section className="py-10 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Chart lab" />
          <div className="mt-6">
            <details className="group border border-border overflow-hidden">
              <summary className="list-none flex items-center justify-between px-4 py-3 bg-surface hover:bg-raised transition-colors cursor-pointer gap-2 select-none [&::-webkit-details-marker]:hidden">
                <div>
                  <span className="font-sans text-sm font-semibold text-ink">Chart lab — OOS equity, drawdown, f_t</span>
                  <span className="font-sans text-2xs text-muted ml-3 hidden md:inline">
                    4 charts · cumulative wealth, drawdown, scale factor, BIL weight
                  </span>
                </div>
                <div className="flex-shrink-0 flex items-center gap-2">
                  <span className="font-sans text-muted text-xs group-open:hidden">▼ expand charts</span>
                  <span className="font-sans text-muted text-xs hidden group-open:inline">▲ collapse</span>
                </div>
              </summary>

              <div className="border-t border-border bg-bg divide-y divide-border">
                {/* Cumulative wealth */}
                <div className="p-5 md:p-6">
                  <Eyebrow>Cumulative wealth</Eyebrow>
                  <p className="font-sans text-sm text-body mt-1 mb-4 max-w-2xl">
                    Book 2 vol-target vs static Option A (Book 1). Base = 1.0 at OOS start.
                  </p>
                  <div className="border border-border bg-surface p-4">
                    <EquityChart />
                  </div>
                </div>

                {/* Drawdown */}
                <div className="p-5 md:p-6 bg-hero-gradient">
                  <Eyebrow>Drawdown</Eyebrow>
                  <p className="font-sans text-sm text-body mt-1 mb-4 max-w-2xl">
                    Rolling drawdown from peak. Milder MaxDD for vol-target is the primary risk-path claim.
                  </p>
                  <div className="border border-border bg-surface p-4">
                    <DrawdownChart />
                  </div>
                </div>

                {/* Scale factor */}
                <div className="p-5 md:p-6">
                  <Eyebrow>Monthly scale factor f_t</Eyebrow>
                  <p className="font-sans text-sm text-body mt-1 mb-4 max-w-2xl">
                    Clip(σ* / σ̂_t, f_min=0.25, f_max=1.0). Scale-down only. Months where f&lt;1
                    indicate elevated estimated volatility — BIL receives cash when f&lt;1.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="border border-border bg-surface p-4">
                      <FtChart />
                    </div>
                    <div className="border border-border bg-surface p-4">
                      <WBilChart />
                    </div>
                  </div>
                </div>
              </div>
            </details>
          </div>
        </div>
      </section>

      {/* ── Downloads ── */}
      <section className="py-10">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <ThickRule label="Data" />
          <div className="mt-6">
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
                  className="flex items-center gap-3 border border-border bg-surface px-4 py-3 text-sm text-body hover:border-border-bright hover:bg-raised hover:text-ink transition-all no-underline group"
                  download
                >
                  <ArrowDownToLine
                    size={14}
                    className="flex-shrink-0 text-muted group-hover:text-ink transition-colors"
                  />
                  <span className="font-sans flex-1">{label}</span>
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
