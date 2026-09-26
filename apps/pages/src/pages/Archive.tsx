import { Link } from 'react-router-dom'

import { Card } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import archive from '../data/archive_verdicts.json'

interface ArchiveCard {
  id: string
  name: string
  detail: string
  badge: string
  verdict: string
  null: string
  rows: { role: string; label: string; sharpe: string; maxdd: string }[]
  nw_t: string
  nw_t_links?: { label: string; href: string }[]
  measured?: { label: string; text: string }
  dsr: string
  gate: { label: string; href: string }
  method_page: string
  artifact: { label: string; href: string }
  archived: string
  archived_via: string
}

interface ArchiveData {
  updated: string
  cards: ArchiveCard[]
}

const archiveData: ArchiveData = archive

const linkClass = 'text-muted hover:text-body underline underline-offset-2 decoration-border'

function resolveHref(href: string) {
  return href.startsWith('http') ? href : './' + href
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

export default function Archive() {
  return (
    <div>
      {/* ── Page header — muted, clearly not a showcase ── */}
      <section className="border-b border-border bg-raised">
        <div className="mx-auto max-w-6xl px-4 md:px-6 pt-10 pb-12">
          <span className="inline-flex items-center gap-1.5 text-2xs font-medium uppercase tracking-label px-2.5 py-1 border border-down/20 text-down/80 bg-down/5 mb-4">
            Research archive · not a showcase · not live books
          </span>
          <h2 className="font-display font-black text-3xl md:text-4xl text-ink leading-tight mt-2 mb-4">
            Methods Archive
          </h2>
          <p className="text-base text-body max-w-2xl mb-5 leading-relaxed">
            Archived methods: Justina round-1 (Spectral RP, Regime-Aware), #13 VCFC, #4 FT-MED, #3 RR-ERC ·
            plus the unconditional Book-2 VT audit null · USA ETF experimental panel · updated {archiveData.updated} (ET)
          </p>
          <div className="inline-block border border-down/20 bg-down/5 px-4 py-3 text-xs text-muted max-w-2xl">
            <strong className="text-ink">Research only — not investment advice.</strong>{' '}
            Negative / null results documented on purpose. The five failed methods are{' '}
            <strong className="text-down">FAIL / ARCHIVE</strong> — not promoted to Books, not a
            showcase, not part of the live shortlist. Unconditional Book-2 VT is an AUDIT NULL (not live, not a FAIL).
          </div>
        </div>
      </section>

      {/* ── CIO frame ── */}
      <section className="py-8 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <div className="border border-border bg-surface px-6 py-5">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent text-sm leading-none">◆</span>
              <span className="text-2xs font-medium uppercase tracking-label text-muted">CIO frame</span>
            </div>
            <p className="font-serif text-base italic text-ink leading-snug mb-3">
              None of the five archived methods cleared its binding null.{' '}
              <strong className="not-italic">No book cut.</strong>
            </p>
            <p className="text-sm text-body leading-relaxed">
              Live shortlist: <strong className="text-ink">static core + VT × gate-first skew overlay</strong> (Justina #6, PR #29).
              Unconditional Book-2 VT is the audit null that overlay was measured against — not live, not a FAIL.
            </p>
            <p className="text-sm text-body leading-relaxed">
              Further candidates must clear the same leakage · null · DSR · empirical gate.{' '}
              <Link to="/" className="text-muted hover:text-body underline underline-offset-2 decoration-border">
                Back to live shortlist →
              </Link>
            </p>
          </div>
        </div>
      </section>

      {/* ── Verdict cards ── */}
      <section className="py-12 border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <SectionRule label="Results" />
          <div className="mt-8">
            <Eyebrow>Verdict cards</Eyebrow>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
              {archiveData.cards.map(card => (
                <Card key={card.id} className="p-5">
                  <Badge variant={card.badge === 'FAIL' ? 'archive' : 'quiet'}>{card.badge}</Badge>
                  <h3 className="font-display text-xl text-ink mt-2">{card.name}</h3>
                  <p className="text-xs text-muted mb-3">{card.detail}</p>
                  <p className="font-serif text-base italic text-ink leading-snug mb-3">{card.verdict}</p>
                  <p className="text-sm text-body mb-3">Binding null: {card.null}</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border bg-raised text-left">
                          {['', 'Sharpe', 'MaxDD'].map(h => (
                            <th key={h} className="px-4 py-3 font-medium text-muted text-2xs uppercase tracking-label">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {card.rows.map(row => (
                          <tr key={row.label} className="border-b border-border last:border-0 align-top">
                            <td className="px-4 py-3 text-body">{row.label}</td>
                            <td className="px-4 py-3 font-mono text-body">{row.sharpe}</td>
                            <td className="px-4 py-3 font-mono text-body">{row.maxdd}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {card.measured && (
                    <p className="mt-3 text-sm text-body">
                      <span className="font-medium text-muted">{card.measured.label}:</span>{' '}
                      <span className="font-mono">{card.measured.text}</span>
                    </p>
                  )}
                  <dl className="mt-4 text-xs text-body space-y-2">
                    <div>
                      <dt className="font-medium text-muted">NW t</dt>
                      <dd className="font-mono">
                        {card.nw_t}
                        {card.nw_t_links?.map(link => (
                          <span key={link.href}>
                            {' · '}
                            <a
                              href={resolveHref(link.href)}
                              {...(link.href.startsWith('http') ? { target: '_blank', rel: 'noreferrer' } : {})}
                              className={linkClass}
                            >
                              {link.label}
                            </a>
                          </span>
                        ))}
                      </dd>
                    </div>
                    <div><dt className="font-medium text-muted">DSR (vs zero Sharpe)</dt><dd className="font-mono">{card.dsr}</dd></div>
                  </dl>
                  <p className="mt-4 text-2xs text-muted">
                    Gate memo / PR: <a href={card.gate.href} target="_blank" rel="noreferrer" className="text-muted hover:text-body underline underline-offset-2 decoration-border">{card.gate.label}</a>{' · '}
                    <a href={'./' + card.method_page} className="text-muted hover:text-body underline underline-offset-2 decoration-border">Method page</a>{' · '}
                    OOS artifact: <a href={card.artifact.href} target="_blank" rel="noreferrer" className="text-muted hover:text-body underline underline-offset-2 decoration-border">{card.artifact.label}</a>{' · '}
                    Archived {card.archived} ({card.archived_via})
                  </p>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── What cleared the process ── */}
      <section className="py-12 bg-hero-gradient border-b border-border">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <div>
            <Eyebrow>What cleared the process (not the nulls)</Eyebrow>
            <ul className="space-y-2 text-sm text-body list-none mt-4">
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
        </div>
      </section>

      {/* ── Teaching links ── */}
      <section className="py-12">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          <Eyebrow>Teaching pages (static HTML)</Eyebrow>
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              { label: 'Spectral RP', href: './methods/spectral_risk_parity.html' },
              { label: 'Regime-Aware Dual-Regime', href: './methods/regime_aware_dual_regime.html' },
              { label: 'Vol-cond factor corr #13', href: './methods/allocation_alpha_vol_cond_factor_corr.html' },
              { label: 'FT-MED #4', href: './methods/allocation_alpha_forecast_tangency_med.html' },
              { label: 'RR-ERC #3', href: './methods/allocation_alpha_regime_resilient_erc.html' },
              { label: 'Vol-target (Book 2)', href: './methods/allocation_alpha_vol_target.html' },
              { label: 'Skewness overlay #6', href: './methods/skewness_managed_stub.html' },
              { label: 'Archive scoreboard (static HTML)', href: './methods/justina_round1_scoreboard.html' },
            ].map(link => (
              <a
                key={link.href}
                href={link.href}
                className="border border-border bg-surface px-3 py-2 text-2xs text-muted hover:border-border-bright hover:text-body transition-all no-underline"
              >
                {link.label}
              </a>
            ))}
          </div>

          <p className="mt-6 text-2xs text-muted/50">
            Sources: card numbers are copied from repo artifacts (data/processed/*/…summary.csv) and gate PR bodies (#10, #11, #13, #24, #26, #27, #29); single source: apps/pages/src/data/archive_verdicts.json.
          </p>
        </div>
      </section>
    </div>
  )
}
