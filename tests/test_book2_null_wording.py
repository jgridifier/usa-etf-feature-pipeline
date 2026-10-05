"""Book 2 own-null table (#57, Quant / CIO): 68-month windows, MinVar shown with its p-value and a 'secondary null'
note, and no 'significant' wording (only p-values). The verdict sentence is left exactly as recorded."""
from __future__ import annotations

import html as htmllib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs/methods/results/book2.html'
DATA = ROOT / 'data/processed/hub/subjects/book2.json'
NOTE = 'secondary null; Book 2 is judged against the vol-target backbone (two-sided p 0.33)'
SIG = re.compile(r'signific|p\s*[<≤]\s*0?\.05', re.I)


def _text(path: Path) -> str:
    s = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', path.read_text(encoding='utf-8'), flags=re.S)
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', s)))


def _null_table(page: str) -> str:
    i = page.index('Own null comparisons (Sharpe ex-BIL')
    return page[i:page.index('Windows:', i)]


def test_minvar_row_has_its_p_value_and_the_secondary_null_note():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    rows = {r['label']: r for r in d['vs_nulls']}
    mv, bb = rows['LW MinVar'], next(r for r in d['vs_nulls'] if r.get('primary'))
    assert round(mv['sharpe_test']['p_two_sided'], 3) == 0.043 and round(bb['sharpe_test']['p_two_sided'], 2) == 0.33
    table = _null_table(_text(PAGE))
    assert re.search(r'LW MinVar 0\.87 2\.02 0\.022 0\.043 ' + re.escape(NOTE), table), table[:1200]
    assert table.count('secondary null') == 1


def test_caption_states_68_months_for_every_null():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    assert {(r['start'], r['end'], r['n']) for r in d['vs_nulls']} == {('2021-02', '2026-09', 68)}
    assert 'Windows: Backbone, Equal weight, LW MinVar, ERC: 2021-02 to 2026-09, 68 months each.' in _text(PAGE)


def test_no_significant_wording_on_the_book2_page_except_the_unchanged_verdict():
    verdict = json.loads(DATA.read_text(encoding='utf-8'))['verdict']['text']
    assert verdict == ('Live book. Admitted as a drawdown-control overlay under its gate-first rule. Max drawdown −10.1% '
                       'vs −25.6% for the core, and Sharpe ex-BIL 0.99 vs 0.77, but CAGR 13.9% vs 15.0%. Its Sharpe edge '
                       'over the vol-target backbone is not significant.')
    page = _text(PAGE)
    assert page.count(verdict) == 1
    rest = page.replace(verdict, ' ')
    assert not SIG.search(rest), rest[max(0, SIG.search(rest).start() - 120):SIG.search(rest).end() + 60]
    assert 'Significance (two-sided 5%)' not in page and 'significant_5pct_two_sided' not in page


def test_no_page_calls_the_minvar_gap_significant():
    files = [p for p in (ROOT / 'docs').rglob('*') if p.suffix in ('.html', '.js', '.json', '.md') and 'vendor' not in p.parts
             and not p.name.startswith('v2-echarts')]
    files += sorted((ROOT / 'data/processed/hub').rglob('*.json'))
    bad = []
    for p in files:
        s = p.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'signific(?!ant_5pct)', s, re.I):   # data key significant_5pct_two_sided is not wording
            win = s[max(0, m.start() - 160):m.end() + 160]
            if 'MinVar' in win and not re.search(r'\b(not|no)\b[^.;]{0,30}$', s[max(0, m.start() - 40):m.start()]):
                bad.append((p.relative_to(ROOT).as_posix(), win))
    assert not bad, bad[:3]
