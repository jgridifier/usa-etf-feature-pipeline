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

      <footer className="border-t-2 border-ink mt-16">
        <div className="mx-auto max-w-6xl px-4 md:px-6">
          {/* Footer wordmark rule */}
          <div className="py-5 border-b border-border/60 text-center">
            <p className="font-display font-black text-base text-ink uppercase tracking-[0.22em]">
              USA ETF Lab
            </p>
            <p className="font-sans text-2xs text-muted uppercase tracking-label mt-1">
              Research Edition · Experimental USA Equities Panel
            </p>
          </div>

          <div className="py-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
            <p className="font-serif text-xs text-muted max-w-lg leading-relaxed italic">
              Research only · not investment advice · experimental panel · no performance guarantees.
              Outputs are research artifacts for personal portfolio exploration. No claim of future
              performance, guaranteed alpha, or personalised recommendations.
            </p>
            <p className="font-sans text-2xs text-muted/50 flex-shrink-0">
              Static GitHub Pages
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
