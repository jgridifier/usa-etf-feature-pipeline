import { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { cn } from '../lib/utils'

const PRIMARY_LINKS = [
  { to: '/', label: 'Home', exact: true },
  { to: '/books', label: 'Books' },
  { to: '/runs', label: 'Runs' },
  { to: '/explorer', label: 'Explorer' },
]

export default function Nav() {
  const [open, setOpen] = useState(false)

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'text-sm font-medium transition-colors relative py-0.5',
      isActive
        ? 'text-ink after:absolute after:bottom-0 after:left-0 after:right-0 after:h-px after:bg-accent'
        : 'text-body hover:text-ink',
    )

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 md:px-6 py-4">
        {/* Wordmark */}
        <Link
          to="/"
          className="flex items-center gap-2 no-underline group"
          aria-label="USA ETF Lab home"
        >
          <span className="h-5 w-5 rounded-sm bg-accent/90 flex items-center justify-center flex-shrink-0">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <rect x="1" y="1" width="3.5" height="3.5" rx="0.5" fill="white" opacity="0.9"/>
              <rect x="5.5" y="1" width="3.5" height="3.5" rx="0.5" fill="white" opacity="0.5"/>
              <rect x="1" y="5.5" width="3.5" height="3.5" rx="0.5" fill="white" opacity="0.5"/>
              <rect x="5.5" y="5.5" width="3.5" height="3.5" rx="0.5" fill="white" opacity="0.9"/>
            </svg>
          </span>
          <span className="font-semibold text-ink text-sm tracking-tight group-hover:text-accent transition-colors">
            USA ETF Lab
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-7" aria-label="Main">
          {PRIMARY_LINKS.map(({ to, label, exact }) => (
            <NavLink key={to} to={to} end={exact} className={linkClass}>
              {label}
            </NavLink>
          ))}
          {/* Archive — de-emphasised, no primary color */}
          <NavLink
            to="/archive"
            className={({ isActive }) =>
              cn(
                'text-xs font-medium transition-colors px-2 py-1 rounded border',
                isActive
                  ? 'text-muted border-border bg-surface'
                  : 'text-muted border-transparent hover:border-border hover:text-body',
              )
            }
          >
            Archive
          </NavLink>
        </nav>

        {/* Mobile toggle */}
        <button
          type="button"
          className="md:hidden p-1 rounded text-body hover:text-ink transition-colors"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen(o => !o)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <nav
          className="md:hidden border-t border-border bg-bg px-4 py-4 flex flex-col gap-5"
          aria-label="Mobile main"
        >
          {PRIMARY_LINKS.map(({ to, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={linkClass}
              onClick={() => setOpen(false)}
            >
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/archive"
            className={({ isActive }) =>
              cn('text-xs text-muted hover:text-body transition-colors', isActive && 'text-body')
            }
            onClick={() => setOpen(false)}
          >
            Archive (not promoted)
          </NavLink>
          <p className="text-2xs text-muted border-t border-border pt-3">
            Research only · not investment advice
          </p>
        </nav>
      )}
    </header>
  )
}
