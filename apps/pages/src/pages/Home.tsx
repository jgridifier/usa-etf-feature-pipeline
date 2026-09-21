import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/badge'
import { LinkButton } from '../components/ui/button'
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

interface StatCardProps {
  label: string
  value: string
  sub?: string
  accent?: boolean
  dim?: boolean
}

function StatCard({ label, value, sub, accent, dim }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${dim ? 'text-down' : accent ? 'text-accent' : 'text-ink'}`}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function ShortlistCard({
  badge,
  badgeVariant,
  title,
  description,
  href,
  muted,
  footerLink,
}: {
  badge: string
  badgeVariant: 'live' | 'quiet'
  title: string
  description: string
  href?: string
  muted?: boolean
  footerLink?: { label: string; to: string }
}) {
  const inner = (
    <div
      className={`rounded-xl border p-5 h-full transition-all ${
        muted
          ? 'border-border bg-surface opacity-50 cursor-default'
          : 'border-border bg-surface hover:border-border-bright hover:bg-raised cursor-pointer'
      }`}
    >
      <Badge variant={badgeVariant} className="mb-3">{badge}</Badge>
      <h3 className="text-base font-semibold text-ink mb-2">{title}</h3>
      <p className="text-sm text-body leading-relaxed">{description}</p>
      {footerLink && (
        <p className="mt-3 text-xs">
          <Link to={footerLink.to} className="text-muted hover:text-body">
            {footerLink.label} →
          </Link>
        </p>
      )}
    </div>
  )

  if (href && !muted) {
    return <Link to={href} className="no-underline block h-full">{inner}</Link>
  }
  return inner
}

export default function Home() {
  const { data: m } = useJsonData<MetricsPayload>('viz_metrics.json')

  return (
    <div>
      {/* ── Hero ── */}
      <section className="relative overflow-hidden border-b border-border">
        {/* Background grid texture */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: 'linear-gradient(#4f7ef8 1px, transparent 1px), linear-gradient(90deg, #4f7ef8 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
        <div className="relative mx-auto max-w-5xl px-4 md:px-6 py-20 md:py-28">
          <Badge variant="live" className="mb-5">Live shortlist</Badge>
          <h1 className="text-4xl md:text-6xl font-bold text-ink mb-5 text-balance leading-tight">
            Static core +<br className="hidden md:block" /> Book-2 vol-target
          </h1>
          <p className="text-lg text-body max-w-2xl mb-8 leading-relaxed">
            The live research shortlist is <strong>Book 1 static Option A</strong> plus{' '}
            <strong>Book 2 unconditional vol-target</strong>. Archive / failed-null methods are
            not on this door. Static GitHub Pages — no live trading.
          </p>
          <div className="flex flex-wrap gap-3">
            <LinkButton href="#/books" variant="primary" size="md">Open live shortlist</LinkButton>
            <LinkButton href="#/runs" variant="secondary" size="md">OOS runs</LinkButton>
            <LinkButton href="#/explorer" variant="secondary" size="md">Explorer</LinkButton>
          </div>
        </div>
      </section>

      {/* ── Live books grid ── */}
      <section className="py-14 border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <div className="flex items-center justify-between mb-8">
            <div>
              <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-1">Front door</p>
              <h2 className="text-2xl font-bold text-ink">What is live right now</h2>
            </div>
            <Link to="/books" className="text-xs text-muted hover:text-body no-underline">
              View all →
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ShortlistCard
              badge="Book 1 · live"
              badgeVariant="live"
              title="Static core"
              description="Fixed weights VOO 70% / QQQM 20% / IJR 10%. Buy-and-hold reference — clean null for timing / risk overlays."
              href="/books"
            />
            <ShortlistCard
              badge="Book 2 · live"
              badgeVariant="live"
              title="Vol-target"
              description="Same Option A core, scale-down into BIL when risk is high. Path/risk book vs Book 1 — not a beat-the-market story."
              href="/books"
            />
            <ShortlistCard
              badge="Not live"
              badgeVariant="quiet"
              title="Archive / failed nulls"
              description="Spectral RP, Regime-Aware, and vol-cond factor corr (#13) failed binding nulls — research record only."
              muted
              footerLink={{ label: 'View archive', to: '/archive' }}
            />
          </div>
        </div>
      </section>

      {/* ── OOS metrics strip ── */}
      <section className="py-14 bg-hero-gradient border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <div className="mb-8">
            <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-1">Supporting OOS</p>
            <h2 className="text-2xl font-bold text-ink mb-2">Book 2 path vs static Option A</h2>
            <p className="text-body text-sm">
              {m?.n_months ?? 68}-month OOS ·{' '}
              {m?.start_date ?? '2021-02-26'} → {m?.end_date ?? '2026-09-16'} · real-BIL sample.
              Evidence for the live Book-2 sleeve — not a separate promoted book.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard label="Sharpe (vt)" value={num(m?.Sharpe_vt, 2)} sub={`Static A: ${num(m?.Sharpe_a, 2)}`} accent />
            <StatCard label="Max drawdown (vt)" value={pct(m?.MaxDD_vt)} sub={`Static A: ${pct(m?.MaxDD_a)}`} dim />
            <StatCard label="Ann. vol (vt)" value={pct(m?.AnnVol_vt)} sub={`Static A: ${pct(m?.AnnVol_a)}`} />
            <StatCard label="NW t vs A" value={num(m?.NW_t, 2)} sub="Path/risk, not return alpha" />
          </div>

          {m && (
            <p className="text-xs text-muted mb-6">
              Moreira &amp; Muir (2017) · mean f = {m.mean_f.toFixed(2)} · months with f&lt;1:{' '}
              {(100 * m.pct_months_f_lt_1).toFixed(0)}%
            </p>
          )}

          <div className="flex flex-wrap gap-3">
            <LinkButton href="#/runs" variant="primary" size="sm">Open OOS charts</LinkButton>
            <LinkButton href="#/books" variant="secondary" size="sm">Live shortlist weights</LinkButton>
          </div>
        </div>
      </section>

      {/* ── IA tiles ── */}
      <section className="py-14">
        <div className="mx-auto max-w-5xl px-4 md:px-6">
          <p className="text-2xs font-medium uppercase tracking-widest text-muted mb-8">Lab sections</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                to: '/books', badge: 'Books',
                title: 'Shortlist weights & comparison',
                desc: 'Live Books 1–2 with standing-book cards, weights, and comparison.',
              },
              {
                to: '/runs', badge: 'Runs',
                title: 'Out-of-sample charts',
                desc: 'Equity, drawdown, scale factor f_t, and downloadable CSVs.',
              },
              {
                to: '/explorer', badge: 'Explorer',
                title: 'Time Series Explorer',
                desc: 'Growth-panel metrics and charts for research diagnostics.',
              },
            ].map(item => (
              <Link key={item.to} to={item.to} className="no-underline block">
                <div className="rounded-xl border border-border bg-surface p-5 hover:border-border-bright hover:bg-raised transition-all h-full">
                  <Badge variant="default" className="mb-3">{item.badge}</Badge>
                  <h3 className="text-sm font-semibold text-ink mb-2">{item.title}</h3>
                  <p className="text-xs text-body leading-relaxed">{item.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
