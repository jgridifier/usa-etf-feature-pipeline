// Archive counts and per-run VOID reasons for page copy, derived from the archive cards
// (single source: src/data/archive_verdicts.json). Each card counts once by its own badge, so FAIL
// and VOID are counted separately. Mirrors scripts/archive_void.py.
// tests/test_archive_counts.py checks Home, the Archive tab and the Methods scoreboard agree.
import archive from '../data/archive_verdicts.json'

export interface VoidReason { run: string; kind: string; value: number; threshold: number; source: string }
interface Card { id: string; name: string; badge: string; void_reason?: VoidReason }

const cards = (archive as { cards: Card[] }).cards
const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

export function countBadge(badge: string): number {
  return cards.filter(card => card.badge === badge).length
}

export function numberWord(n: number, capital = false): string {
  const w = NUMBER_WORDS[n] ?? String(n)
  return capital ? w.charAt(0).toUpperCase() + w.slice(1) : w
}

export function joinAnd(items: string[]): string {
  return items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

function fmtG(x: number): string {
  return String(Number(x.toPrecision(6)))
}

export function voidSummary(r: VoidReason): string {
  if (r.kind === 'effective_n') return `effective N ${r.value.toFixed(1)} < ${fmtG(r.threshold)}`
  if (r.kind === 'cash_like') return `cash-like ${(100 * r.value).toFixed(1)}% > ${fmtG(100 * r.threshold)}%`
  throw new Error(`unknown VOID kind ${r.kind}`)
}

export function badgeText(card: { badge: string; void_reason?: VoidReason }): string {
  return card.badge === 'VOID' && card.void_reason ? `VOID: ${voidSummary(card.void_reason)}` : card.badge
}

export const failCount = countBadge('FAIL')
export const voidCount = countBadge('VOID')
export const failNames = joinAnd(cards.filter(c => c.badge === 'FAIL').map(c => c.name))
export const voidCards = cards.filter(c => c.badge === 'VOID')
  .sort((a, b) => (a.void_reason?.run ?? a.name).localeCompare(b.void_reason?.run ?? b.name))
export const voidRuns = joinAnd(voidCards.map(c => c.void_reason?.run ?? c.name))
export const voidList = voidCards.map(c => (c.void_reason ? `${c.void_reason.run}: ${voidSummary(c.void_reason)}` : c.name)).join('; ')
export const voidNoun = voidCount === 1 ? 'VOID' : 'VOIDs'
export const voidVerb = voidCount === 1 ? 'is' : 'are'
