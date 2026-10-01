/**
 * Display labels for the vol-target backbone ("VT" in internal names).
 * Prose says "vol-target backbone"; tables, cards, legends and tooltips say "Backbone".
 * Mirror of scripts/labels.py. Used to relabel the frozen archive_verdicts.json at
 * display time (the file on disk is unchanged). Never apply to ticker text: VT the
 * ETF (Vanguard Total World) stays "VT".
 */
const APOS = "(&rsquo;|’|')"
const PROSE_RULES: [RegExp, string][] = [
  [new RegExp('Book-2' + APOS + 's VT backbone', 'g'), 'Book 2$1s vol-target backbone'],
  [/Book-2 VT backbone/g, 'vol-target backbone'],
  [/Book-2 VT\b/g, 'vol-target backbone'],
  [/\bVT backbone/g, 'vol-target backbone'],
  [/\bVT ×/g, 'vol-target backbone ×'],
  [/\bVT null\b/g, 'vol-target backbone null'],
  [new RegExp('\\bVT' + APOS + 's\\b', 'g'), 'the vol-target backbone$1s'],
  [/\b(tracked|for|vs|versus|than|against) VT\b/g, '$1 the vol-target backbone'],
  [/\(VT\)/g, '(Backbone)'],
]
const LABEL_RULES: [RegExp, string][] = [
  [/Book-2 VT( backbone)?\b/g, 'Backbone'],
  [/\bVT backbone\b/g, 'Backbone'],
  [/\bVT\b/g, 'Backbone'],
]
const apply = (rules: [RegExp, string][], s: string) => rules.reduce((t, [re, rep]) => t.replace(re, rep), s)
export const relabelProse = (s: string) => apply(PROSE_RULES, s)
export const relabelLabel = (s: string) => apply(LABEL_RULES, s)

const LABEL_FIELDS = new Set(['name', 'null', 'label'])
const SKIP = new Set(['id', 'href', 'method_page', 'badge'])

export function relabelArchive<T>(obj: T, key?: string): T {
  if (Array.isArray(obj)) return obj.map(v => relabelArchive(v, key)) as T
  if (obj && typeof obj === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) out[k] = SKIP.has(k) ? v : relabelArchive(v, k)
    return out as T
  }
  if (typeof obj === 'string') return (key && LABEL_FIELDS.has(key) ? relabelLabel(obj) : relabelProse(obj)) as T
  return obj
}
