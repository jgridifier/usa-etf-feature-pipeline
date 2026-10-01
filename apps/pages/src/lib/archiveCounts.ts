// Archive counts for page copy, derived from the archive cards (single source:
// src/data/archive_verdicts.json). FAIL and VOID are counted separately.
// tests/test_archive_counts.py checks Home, the Archive tab and the Methods scoreboard agree.
import archive from '../data/archive_verdicts.json'

const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

export function countBadge(badge: string): number {
  return (archive as { cards: { badge: string }[] }).cards.filter(card => card.badge === badge).length
}

export function numberWord(n: number, capital = false): string {
  const w = NUMBER_WORDS[n] ?? String(n)
  return capital ? w.charAt(0).toUpperCase() + w.slice(1) : w
}

export const failCount = countBadge('FAIL')
export const voidCount = countBadge('VOID')
