import { type ReactNode } from 'react'
import Masthead from './Masthead'
import TickerBanner from './TickerBanner'
import Nav from './Nav'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <Masthead />
      <TickerBanner />
      <Nav />

      <main className="flex-1">
        {children}
      </main>

      <footer className="border-t border-border mt-16">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          {/* Triple rule footer header */}
          <div className="py-6 border-b border-border">
            <p className="font-display font-bold text-sm text-muted text-center uppercase tracking-masthead">
              USA ETF Lab
            </p>
          </div>

          <div className="py-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
            <p className="text-xs text-muted max-w-lg leading-relaxed">
              Research only · not investment advice · experimental panel · no performance guarantees.
              Outputs are research artifacts for personal portfolio exploration. No claim of future
              performance, guaranteed alpha, or personalised recommendations.
            </p>
            <p className="text-2xs text-muted/40 flex-shrink-0">
              Static GitHub Pages
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
