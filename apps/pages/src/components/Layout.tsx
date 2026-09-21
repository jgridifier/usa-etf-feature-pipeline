import { type ReactNode } from 'react'
import Nav from './Nav'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <Nav />
      <main className="flex-1">
        {children}
      </main>
      <footer className="border-t border-border py-8 px-4">
        <div className="mx-auto max-w-6xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <p className="text-xs text-muted">
            Research only · not investment advice · experimental panel · no performance guarantees.
          </p>
          <p className="text-2xs text-muted/60">
            Design tokens from public editorial UI patterns. Research panel only.
          </p>
        </div>
      </footer>
    </div>
  )
}
