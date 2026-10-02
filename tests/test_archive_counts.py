"""Home's FAIL / VOID counts come from the archive cards and agree with the Archive tab and the Methods scoreboard.

Counts: apps/pages/src/data/archive_verdicts.json, one per card by its own badge (FAIL and VOID separately,
no family dedupe). Checked on Home and the Archive tab (SPA, rendered) and on the static Methods
scoreboard (docs/methods/justina_round1_scoreboard.html). Also scans Home and docs/notes for typed counts.
"""
from __future__ import annotations

import collections
import html as htmllib
import json
import re
import sys
from pathlib import Path

from test_no_bare_vt_label import spa  # noqa: F401  (rendered SPA routes fixture)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import archive_void as av  # noqa: E402

WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
ARCHIVE = json.loads((ROOT / 'apps/pages/src/data/archive_verdicts.json').read_text(encoding='utf-8'))
COUNTS = collections.Counter(c['badge'] for c in ARCHIVE['cards'])
QUANT_VOIDS = {'nls_gmv_v1': 'PR #34', 'nls_gmv_v2': 'PR #37', 'nls_gmv_v3': 'PR #40'}
COUNT_WORD = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)'
TYPED_COUNT = re.compile(rf'\b{COUNT_WORD}\s+(?:(?:archived|failed|wide-panel|allocation|binding-null)\s+)*'
                         r'(?:methods?|FAILs?|VOIDs?|runs?)\b', re.I)


def text(dom: str) -> str:
    dom = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', dom, flags=re.S)
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', '', dom)))


def scoreboard() -> str:
    return text((ROOT / 'docs/methods/justina_round1_scoreboard.html').read_text(encoding='utf-8'))


def scoreboard_fail_count() -> int:
    t = scoreboard()
    found = {m.lower() for m in re.findall(r'The (\w+) failed methods are', t)}
    found |= {m.lower() for m in re.findall(r'None of the (\w+) archived methods', t)}
    assert len(found) == 1, found
    return WORDS.index(found.pop())


def test_each_quant_void_run_is_its_own_card():
    cards = {c['id']: c for c in ARCHIVE['cards']}
    for cid, pr in QUANT_VOIDS.items():
        assert cards[cid]['badge'] == 'VOID', cid
        assert cards[cid]['gate']['label'] == pr
        assert cards[cid]['void_reason']['run'] == f"NLS GMV {cid.rsplit('_', 1)[1]}"
    assert COUNTS['VOID'] == len(QUANT_VOIDS) == 3
    # 7 FAILs since 2026-10-02: the Schur card (mechanical FAIL, pending Quant recompute).
    assert COUNTS['FAIL'] == 7 and COUNTS['AUDIT NULL'] == 1
    assert av.counts(ARCHIVE) == dict(COUNTS)


def test_home_source_has_no_typed_count():
    src = (ROOT / 'apps/pages/src/pages/Home.tsx').read_text(encoding='utf-8')
    assert not TYPED_COUNT.findall(re.sub(r'\{[^{}]*\}', ' ', src)), TYPED_COUNT.findall(src)
    assert '{numberWord(failCount, true)} FAILs and {numberWord(voidCount)} {voidNoun} ({voidList})' in src
    assert '{numberWord(failCount, true)} methods failed binding nulls: {failNames}.' in src
    assert '{numberWord(failCount, true)} archived methods failed' in src
    assert '{failNames} failed binding-null gates' in src
    lib = (ROOT / 'apps/pages/src/lib/archiveCounts.ts').read_text(encoding='utf-8')
    assert "countBadge('FAIL')" in lib and "countBadge('VOID')" in lib


def test_notes_have_no_typed_method_counts():
    # docs/notes pages are hash-pinned byte-for-byte; a hit here is reported, never edited.
    hits = {}
    for p in sorted((ROOT / 'docs/notes').glob('*.html')) + sorted((ROOT / 'docs/notes').glob('*.md')):
        found = TYPED_COUNT.findall(text(p.read_text(encoding='utf-8')))
        if found:
            hits[p.name] = found
    assert not hits, hits


def test_scoreboard_counts_match_archive_data():
    assert scoreboard_fail_count() == COUNTS['FAIL']
    t = scoreboard()
    assert f'Bet 1 {av.void_runs(ARCHIVE)} are VOID ({av.void_list(ARCHIVE)})' in t
    for c in av.void_cards(ARCHIVE):
        assert av.badge_text(c) in t


def test_home_count_matches_methods_scoreboard(spa):  # noqa: F811
    home = text(spa['/'])
    m = re.search(r'\b(\w+) FAILs and (\w+) VOIDs? \(([^)]*)\)', home)
    assert m, 'Home count line not rendered'
    fails, voids = WORDS.index(m.group(1).lower()), WORDS.index(m.group(2).lower())
    assert fails == scoreboard_fail_count() == COUNTS['FAIL']
    assert voids == len(av.void_cards(ARCHIVE)) == COUNTS['VOID']
    assert m.group(3) == av.void_list(ARCHIVE)
    assert f'which do not change). {av.number_word(fails, True)} FAILs and' in home
    names = av.join_and([c['name'] for c in ARCHIVE['cards'] if c['badge'] == 'FAIL'])
    assert f'{av.number_word(fails, True)} methods failed binding nulls: {names}.' in home
    assert f'{av.number_word(fails, True)} archived methods failed binding nulls' in home
    arc = text(spa['/archive'])
    a = re.search(r'The (\w+) failed methods are', arc)
    assert a and WORDS.index(a.group(1).lower()) == fails
    assert f'Bet 1 {av.void_runs(ARCHIVE)} are VOID ({av.void_list(ARCHIVE)})' in arc
    for c in av.void_cards(ARCHIVE):
        assert av.badge_text(c) in arc
