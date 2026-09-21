import { useEffect } from 'react'
import { Badge } from '../components/ui/badge'

export default function Explorer() {
  useEffect(() => {
    window.location.replace('./explorer/index.html')
  }, [])

  return (
    <div>
      <section className="border-b border-border">
        <div className="mx-auto max-w-5xl px-4 md:px-6 py-24 text-center">
          <Badge className="mb-4">Explorer</Badge>
          <h1 className="text-3xl font-bold text-ink mb-4">Time Series Explorer</h1>
          <p className="text-body mb-8">Redirecting to explorer…</p>
          <a
            href="./explorer/index.html"
            className="inline-flex items-center gap-2 rounded-lg bg-accent text-white px-6 py-2.5 text-sm font-medium hover:bg-accent/90 transition-colors no-underline"
          >
            Open Explorer →
          </a>
        </div>
      </section>
    </div>
  )
}
