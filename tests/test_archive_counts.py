"""Home's FAIL / VOID counts come from the archive cards and agree with the Methods scoreboard.

Counts: apps/pages/src/data/archive_verdicts.json (FAIL and VOID counted separately).
Checked on Home (SPA, rendered), the Archive tab (SPA, rendered) and the static Methods
scoreboard (docs/methods/justina_round1_scoreboard.html).
"""
from __future__ import annotations

import collections
import html as htmllib
import json
import re
from pathlib import Path

import pytest

from test_no_bare_vt_label import spa  # noqa: F401  (rendered SPA routes fixture)

ROOT = Path(__file__).resolve().parents[1]
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
ARCHIVE = json.loads((ROOT / 'apps/pages/src/data/archive_verdicts.json').read_text(encoding='utf-8'))
COUNTS = collections.Counter(c['badge'] for c in ARCHIVE['cards'])


def text(dom: str) -> str:
    dom = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', dom, flags=re.S)
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', '', dom)))


def word(n: int) -> str:
    return WORDS[n]


def scoreboard_fail_count() -> int:
    t = text((ROOT / 'docs/methods/justina_round1_scoreboard.html').read_text(encoding='utf-8'))
    found = {m.lower() for m in re.findall(r'The (\w+) failed methods are', t)}
    found |= {m.lower() for m in re.findall(r'None of the (\w+) archived methods', t)}
    assert len(found) == 1, found
    return WORDS.index(found.pop())


def test_counts_in_archive_data():
    assert COUNTS['FAIL'] == 6 and COUNTS['VOID'] == 1


def test_home_source_has_no_typed_count():
    src = (ROOT / 'apps/pages/src/pages/Home.tsx').read_text(encoding='utf-8')
    assert not re.search(r'\b(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine) FAILs\b', src)
    assert '{numberWord(failCount, true)} FAILs and {numberWord(voidCount)} VOID' in src
    lib = (ROOT / 'apps/pages/src/lib/archiveCounts.ts').read_text(encoding='utf-8')
    assert "countBadge('FAIL')" in lib and "countBadge('VOID')" in lib


def test_scoreboard_count_matches_archive_data():
    assert scoreboard_fail_count() == COUNTS['FAIL']


def test_home_count_matches_methods_scoreboard(spa):  # noqa: F811
    home = text(spa['/'])
    m = re.search(r'\b(\w+) FAILs and (\w+) VOID\b', home)
    assert m, 'Home count line not rendered'
    fails, voids = WORDS.index(m.group(1).lower()), WORDS.index(m.group(2).lower())
    assert fails == scoreboard_fail_count() == COUNTS['FAIL']
    assert voids == COUNTS['VOID']
    arc = re.search(r'The (\w+) failed methods are', text(spa['/archive']))
    assert arc and WORDS.index(arc.group(1).lower()) == fails
