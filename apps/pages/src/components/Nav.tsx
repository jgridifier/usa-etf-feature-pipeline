import { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { cn } from '../lib/utils'

// CIO IA: 4 primary sections — Shortlist (Books), Methods/Archive, Explorer (sandbox), Universe
const PRIMARY_LINKS = [
  { to: '/books',    label: 'Shortlist' },
  { to: '/archive',  label: 'Methods/Archive' },
  { to: '/explorer', label: 'Explorer' },
  { to: '/universe', label: 'Universe' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'font-sans text-xs font-medium uppercase tracking-label transition-colors py-2 relative',
      isActive
        ? 'text-ink after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-ink'
        : 'text-muted hover:text-body',
    )

  const secondaryClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'font-sans text-2xs font-medium uppercase tracking-label transition-colors px-2.5 py-1 rounded border',
      isActive
        ? 'text-muted border-border bg-surface'
        : 'text-muted/50 border-transparent hover:border-border hover:text-muted',
    )

  return (
    <nav className="sticky top-0 z-40 bg-bg/95 backdrop-blur-sm border-b border-border">
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="flex items-center justify-between gap-6 h-10">

          {/* Wordmark — links to home */}
          <Link
            to="/"
            className="hidden md:block font-sans text-2xs font-bold uppercase tracking-label text-ink/60 hover:text-ink transition-colors no-underline flex-shrink-0"
          >
            ETF Lab
          </Link>

          {/* Desktop primary links */}
          <div className="hidden md:flex items-center gap-7 flex-1">
            {PRIMARY_LINKS.map(({ to, label }) => (
              <NavLink key={to} to={to} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </div>

          {/* Secondary right-rail — OOS runs (supporting data, not a primary section) */}
          <div className="hidden md:flex items-center gap-2">
            <NavLink
              to="/runs"
              title="OOS equity and drawdown charts"
              className={secondaryClass}
            >
              Runs
            </NavLink>
          </div>

          {/* Mobile: site shortname + toggle */}
          <Link to="/" className="md:hidden text-xs font-semibold text-ink no-underline uppercase tracking-label">
            ETF Lab
          </Link>
          <button
            type="button"
            className="md:hidden p-1 text-muted hover:text-ink transition-colors"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div
          className="md:hidden border-t border-border bg-surface px-4 py-4 flex flex-col gap-4"
          aria-label="Mobile navigation"
        >
          {PRIMARY_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'text-sm font-medium uppercase tracking-label transition-colors py-1',
                  isActive ? 'text-ink' : 'text-muted hover:text-body',
                )
              }
              onClick={() => setOpen(false)}
            >
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/runs"
            className={({ isActive }) =>
              cn('text-xs text-muted/60 hover:text-muted transition-colors', isActive && 'text-muted')
            }
            onClick={() => setOpen(false)}
          >
            Runs (OOS data)
          </NavLink>
          <p className="text-2xs text-muted/40 border-t border-border pt-3">
            Research only · not investment advice
          </p>
        </div>
      )}
    </nav>
  )
}
