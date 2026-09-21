import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/badge'

interface ScoreboardRow {
  method: string
  methodNote: string
  bindingNull: string
  methodSharpe: string
  nullSharpe: string
  stress: string
  links: { label: string; href: string }[]
}

const SCOREBOARD: ScoreboardRow[] = [
  {
    method: 'Spectral Risk Parity (ADIA Lab mapping)',
    methodNote: 'Name mode, N≥100, 65m OOS, n_trials=4',
    bindingNull: 'Ledoit–Wolf MinVar',
    methodSharpe: '1.06 / −8.4%',
    nullSharpe: '1.60 / −4.5%\n(ERC 0.98 / −10.1%; EW 0.83 / −18.4%)',
    stress: 'Mild MaxDD edge vs ERC only; loses to MinVar on vol and drawdown. Sleeve mode (343m) last on Sharpe.',
    links: [{ label: 'method page', href: './methods/spectral_risk_parity.html' }],
  },
  {
    method: 'Regime-Aware Dual-Regime (Luo & Mulvey mapping)',
    methodNote: 'Category sleeves, 262m, trial_count=4, gross of costs',
    bindingNull: 'Unconditional ERC',
    methodSharpe: '0.51 / −38.6%\n(best dual: vol_corr_spread ERC)',
    nullSharpe: '0.74 / −22.8%\n(EW 0.70 / −42%; always-calm 0.53 / −52%)',
    stress: 'Ex-post stress (n=53): dual mean −3.3%/mo vs uncond ERC −2.5%/mo — no left-tail rescue. Name-level same pattern (0.57/−33% vs 0.90/−22%).',
    links: [{ label: 'method page', href: './methods/regime_aware_dual_regime.html' }],
  },
  {
    method: 'Vol-cond-factor-corr (#13)',
    methodNote: 'Book-2 VT × corr/vol gate; min_names=100; 21 sleeves; 12 trials; 5 bps; best trial L21/C12/g0.5 (~70m)',
    bindingNull: 'Unconditional Book-2 VT',
    methodSharpe: '1.05 / −15.4%\n(best Sharpe trial; no trial beats Book-2 Sharpe)',
    nullSharpe: 'Book-2 1.11 / −20.5%\n(also fails vs static Option A on NW t, all negative)',
    stress: 'All 12 trials NW t vs Book-2 negative (≈ −1.43 to −3.10). MaxDD milder than Book-2 in 12/12 — risk compression only; not allocation alpha vs live Book-2.',
    links: [{ label: 'method page', href: './methods/allocation_alpha_vol_cond_factor_corr.html' }],
  },
]

export default function Archive() {
  return (
    <div>
      {/* ── Hero — muted, clearly not a showcase ── */}
      <section className="border-b border-border bg-raised">
        <div className="mx-auto max-w-5xl px-4 md:px-6 py-12">
          <Badge variant="archive" className="mb-4">Research archive · not a showcase · not live books</Badge>
          <h1 className="text-2xl md:text-3xl font-bold text-ink mb-3">Methods Archive</h1>
          <p className="text-body text-sm max-w-2xl mb-5">
            Justina round-1 (Spectral RP + Regime-Aware Dual-Regime) + vol-cond-factor-corr (#13) ·
            USA ETF experimental panel · updated 2026-09-21 (ET)
          </p>
          {/* Research disclaimer box */}
          <div className="inline-block border border-down/20 bg-down/5 rounded-lg px-4 py-3 text-xs text-muted max-w-2xl">
            <strong className="text-ink">Research only — not investment advice.</strong>{' '}
            Negative / null results documented on purpose. These methods are{' '}
            <strong className="text-down">FAIL / ARCHIVE</strong> — not promoted to Books, not a
            showcase, not part of the live shortlist.
          </div>
        </div>
      </section>

      {/* ── CIO frame ── */}
      <section className="py-8 border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <div className="rounded-xl border border-border bg-surface px-5 py-4 text-sm text-muted">
            <strong className="text-ink">CIO frame:</strong> Justina round-1 and the Book-2
            conditional-correlation upgrade (#13) did not clear binding nulls on Sharpe (and round-1
            also failed the risk path). <strong className="text-ink">No book cut.</strong> Live
            shortlist stays <strong className="text-ink">static core + unconditional Book-2 vol-target</strong>{' '}
            until something clears the same leakage · null · DSR · empirical gate.
          </div>
        </div>
      </section>

      {/* ── Scoreboard ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-1">Results</p>
          <h2 className="text-xl font-bold text-ink mb-6">Scoreboard</h2>

          <div
            className="overflow-x-auto rounded-xl border border-border"
            tabIndex={0}
            role="region"
            aria-label="Methods Archive scoreboard"
          >
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-raised text-left">
                  {[
                    'Method', 'Binding null',
                    'Method Sharpe / MaxDD', 'Null Sharpe / MaxDD',
                    'Stress / A/B path', 'Verdict', 'Links',
                  ].map(h => (
                    <th key={h} className="px-4 py-3 font-medium text-muted text-2xs uppercase tracking-wider whitespace-nowrap first:min-w-[180px]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SCOREBOARD.map((row, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-raised transition-colors align-top">
                    <td className="px-4 py-4 min-w-[180px]">
                      <span className="font-medium text-ink block">{row.method}</span>
                      <span className="text-muted/70">{row.methodNote}</span>
                    </td>
                    <td className="px-4 py-4 text-body min-w-[120px]">{row.bindingNull}</td>
                    <td className="px-4 py-4 font-mono whitespace-pre-line min-w-[140px]">{row.methodSharpe}</td>
                    <td className="px-4 py-4 font-mono whitespace-pre-line min-w-[140px]">{row.nullSharpe}</td>
                    <td className="px-4 py-4 text-body min-w-[200px] max-w-xs">{row.stress}</td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      <span className="font-semibold text-down">FAIL — archive</span>
                    </td>
                    <td className="px-4 py-4">
                      {row.links.map(link => (
                        <a
                          key={link.href}
                          href={link.href}
                          className="block text-muted hover:text-body text-2xs underline underline-offset-2 decoration-border"
                        >
                          {link.label}
                        </a>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── What cleared / didn't ── */}
      <section className="py-12 bg-hero-gradient border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6 grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h2 className="text-base font-semibold text-ink mb-3">What cleared the process (not the nulls)</h2>
            <ul className="space-y-2 text-sm text-body list-none">
              {[
                'Walk-forward leakage gates + unit tests (decision / feature_end ≤ t; labels next month).',
                'Predeclared nulls and DSR / trial counts reported (normal-approx DSR where applicable).',
                'Brand-scrub / experimental-panel language only.',
              ].map((item, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-up mt-0.5 flex-shrink-0">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink mb-3">What did not clear</h2>
            <ul className="space-y-2 text-sm text-body list-none">
              {[
                ['Spectral', 'no edge vs LW MinVar on Sharpe or risk path; sleeve cut rejects.'],
                ['Regime-Aware', 'dual eligibility overlay worse than unconditional ERC on Sharpe, MaxDD, and stress months; higher turnover.'],
                ['Vol-cond-factor-corr (#13)', 'no Sharpe beat of unconditional Book-2 VT; every NW t vs Book-2 negative. Milder MaxDD alone does not clear the book bar.'],
              ].map(([name, detail], i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-down mt-0.5 flex-shrink-0">✗</span>
                  <span>
                    <strong className="text-ink">{name}:</strong>{' '}
                    {detail}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Books implication + links ── */}
      <section className="py-12">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <div className="rounded-xl border border-border bg-surface px-5 py-4 text-sm text-muted mb-8">
            <strong className="text-ink">Books implication:</strong> No new book from Justina round-1 or
            from #13. Existing shortlist unchanged:{' '}
            <strong className="text-ink">static core + unconditional Book-2 vol-target</strong>. Next
            method candidates must clear the same leakage · null · DSR · empirical gate before CoS
            design-pass or promoted Pages.{' '}
            <Link to="/" className="text-muted hover:text-body underline underline-offset-2 decoration-border">
              Back to live shortlist →
            </Link>
          </div>

          <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-3">Teaching pages (static HTML)</p>
          <div className="flex flex-wrap gap-2">
            {[
              { label: 'Spectral RP', href: './methods/spectral_risk_parity.html' },
              { label: 'Regime-Aware Dual-Regime', href: './methods/regime_aware_dual_regime.html' },
              { label: 'Vol-cond factor corr', href: './methods/allocation_alpha_vol_cond_factor_corr.html' },
              { label: 'Vol-target (Book 2)', href: './methods/allocation_alpha_vol_target.html' },
              { label: 'Justina round-1 scoreboard (legacy HTML)', href: './methods/justina_round1_scoreboard.html' },
            ].map(link => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-2xs text-muted hover:border-border-bright hover:text-body transition-all no-underline"
              >
                {link.label}
              </a>
            ))}
          </div>

          <p className="mt-6 text-2xs text-muted/60">
            Sources: <code>JUSTINA_ROUND1_SCOREBOARD.md</code>,{' '}
            <code>QUANT_GATE_vol_cond_factor_corr.md</code>,{' '}
            <code>data/processed/vol_cond_factor_corr/vol_cfc_oos_summary.csv</code> (best Sharpe trial{' '}
            <code>VCFC_option_a_vt_L21_C12_g0p5_mkt_vol</code>).
          </p>
        </div>
      </section>
    </div>
  )
}
