import { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { cn } from '../lib/utils'

const PRIMARY_LINKS = [
  { to: '/',         label: 'Home',     exact: true },
  { to: '/books',    label: 'Books' },
  { to: '/runs',     label: 'Runs' },
  { to: '/explorer', label: 'Explorer' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'text-xs font-medium uppercase tracking-label transition-colors py-2 relative',
      isActive
        ? 'text-ink after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-accent'
        : 'text-muted hover:text-body',
    )

  return (
    <nav className="sticky top-0 z-40 bg-bg/95 backdrop-blur-sm border-b border-border">
      <div className="mx-auto max-w-6xl px-4 md:px-6">
        <div className="flex items-center justify-between gap-6 h-10">

          {/* Desktop primary links */}
          <div className="hidden md:flex items-center gap-7">
            {PRIMARY_LINKS.map(({ to, label, exact }) => (
              <NavLink key={to} to={to} end={exact} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </div>

          {/* Archive — visually secondary, right-aligned */}
          <div className="hidden md:flex items-center">
            <NavLink
              to="/archive"
              className={({ isActive }) =>
                cn(
                  'text-2xs font-medium uppercase tracking-label transition-colors px-2.5 py-1 rounded border',
                  isActive
                    ? 'text-muted border-border bg-surface'
                    : 'text-muted/60 border-transparent hover:border-border hover:text-muted',
                )
              }
            >
              Archive
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
          {PRIMARY_LINKS.map(({ to, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
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
            to="/archive"
            className={({ isActive }) =>
              cn('text-xs text-muted/60 hover:text-muted transition-colors', isActive && 'text-muted')
            }
            onClick={() => setOpen(false)}
          >
            Archive (research record only)
          </NavLink>
          <p className="text-2xs text-muted/40 border-t border-border pt-3">
            Research only · not investment advice
          </p>
        </div>
      )}
    </nav>
  )
}
