"""Archive counts and per-run VOID reasons, read from apps/pages/src/data/archive_verdicts.json.

Each card counts once by its own badge (no family dedupe): FAIL and VOID are counted separately.
A VOID card carries ``void_reason`` (run, kind, value, threshold, source); its badge text is built
from those fields. Mirrored in apps/pages/src/lib/archiveCounts.ts.
"""
from __future__ import annotations

NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']


def counts(archive: dict) -> dict:
    out: dict = {}
    for card in archive['cards']:
        out[card['badge']] = out.get(card['badge'], 0) + 1
    return out


def number_word(n: int, capital: bool = False) -> str:
    w = NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)
    return w[:1].upper() + w[1:] if capital else w


def join_and(items: list[str]) -> str:
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def void_summary(reason: dict) -> str:
    v, t = reason['value'], reason['threshold']
    if reason['kind'] == 'effective_n':
        return f'effective N {v:.1f} < {t:g}'
    if reason['kind'] == 'cash_like':
        return f'cash-like {100 * v:.1f}% > {100 * t:g}%'
    raise ValueError(f'unknown VOID kind {reason["kind"]!r}')


def badge_text(card: dict) -> str:
    r = card.get('void_reason')
    return f"VOID: {void_summary(r)}" if card['badge'] == 'VOID' and r else card['badge']


def void_cards(archive: dict) -> list[dict]:
    return sorted((c for c in archive['cards'] if c['badge'] == 'VOID'),
                  key=lambda c: c.get('void_reason', {}).get('run', c['name']))


def void_runs(archive: dict) -> str:
    return join_and([c['void_reason']['run'] for c in void_cards(archive)])


def void_list(archive: dict) -> str:
    """'NLS GMV v1: cash-like 99.8% > 50%; …', sorted by run."""
    return '; '.join(f"{c['void_reason']['run']}: {void_summary(c['void_reason'])}" for c in void_cards(archive))


def void_verb(archive: dict) -> str:
    return 'is' if len(void_cards(archive)) == 1 else 'are'
