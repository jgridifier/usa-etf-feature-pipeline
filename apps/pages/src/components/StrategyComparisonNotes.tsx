import { useJsonData } from '../hooks/useJsonData'

interface Note {
  strategy_id: string
  label: string
  kind: string
  text: string
}

interface NotesPayload {
  file: string
  source: string
  notes: Note[]
}

/** Row notes for strategy_comparison.csv (docs/data/strategy_comparison_notes.json, generated from data by build_pages.py). */
export function StrategyComparisonNotes() {
  const { data } = useJsonData<NotesPayload>('strategy_comparison_notes.json')
  if (!data || !data.notes.length) return null
  return (
    <div className="mt-4 border border-border bg-surface px-4 py-3" data-testid="strategy-comparison-notes">
      <p className="font-sans text-xs text-muted mb-1">
        Row notes · <code className="font-mono">{data.file}</code>
      </p>
      {data.notes.map((n) => (
        <p key={n.strategy_id} className="font-sans text-sm text-body" data-strategy={n.strategy_id}>
          <strong>{n.label}</strong> <code className="font-mono text-2xs text-muted">{n.strategy_id}</code> ({n.kind}): {n.text}
        </p>
      ))}
    </div>
  )
}
