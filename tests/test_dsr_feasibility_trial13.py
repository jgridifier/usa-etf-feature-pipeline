"""Trial-13 DSR feasibility page (Quant, 2026-10-03; CoS approved).

feasibility.json is recomputed from the committed trial registry with deflated_sharpe_bailey_lp (T = 119,
N = 13) and must match the committed file; the hurdles must match Quant's figures within rounding; and
every figure on the page must come from the JSON. Not an archived trial: no archive card.
"""
import copy
import html as _html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_dsr_feasibility as page_mod  # noqa: E402
import dsr_feasibility_trial13 as calc  # noqa: E402

JSON = ROOT / 'data' / 'processed' / 'dsr_feasibility_trial13' / 'feasibility.json'
PAGE = ROOT / 'docs' / page_mod.PAGE
INDEX = ROOT / 'docs' / 'methods' / 'index.html'
ARCHIVE = ROOT / 'apps' / 'pages' / 'src' / 'data' / 'archive_verdicts.json'


def _committed():
    return json.loads(JSON.read_text(encoding='utf-8'))


def _text(raw):
    raw = raw[raw.index('<main'):raw.index('</main>')]
    return _html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', raw)))


def _close(a, b, path='$'):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            _close(a[k], b[k], f'{path}.{k}')
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f'{path}[{i}]')
    elif isinstance(a, float):
        assert b == pytest.approx(a, abs=1e-9), path
    else:
        assert a == b, path


def _hurdles(d, key):
    case = next(c for c in d['cases'] if c['key'] == key)
    return {h['dsr']: h['sharpe_exbil_annual'] for h in case['hurdles']}


def test_json_recomputes_from_registry():
    _close(calc.compute(), _committed())


def test_values_match_quant_within_rounding():
    d = _committed()
    assert d['inputs']['T'] == 119 and d['inputs']['N'] == 13
    assert d['inputs']['kurtosis_convention'].startswith('raw')
    assert round(d['inputs']['sr_var_cross_trial_monthly'], 6) == 0.014061
    assert round(d['sr0_annual'], 2) == 0.70
    normal = _hurdles(d, 'normal')
    assert [round(normal[t], 2) for t in (0.5, 0.9, 0.95)] == [0.70, 1.12, 1.24]
    assert round(d['c4']['hurdle_normal'], 2) == 1.24
    # Quant confirmed (2026-10-03): T = 119, raw kurtosis; skew -0.5 / kurtosis 5 gives 1.30, not the note's earlier 1.31.
    assert round(_hurdles(d, 'fat_tail_moderate')[0.95], 2) == 1.30
    assert round(_hurdles(d, 'fat_tail_severe')[0.95], 2) == 1.37
    assert [round(x, 2) for x in d['c4']['hurdle_fat_tail_range']] == [1.30, 1.37]
    fat = {c['key']: (c['skew'], c['kurtosis_raw']) for c in d['cases']}
    assert fat == {'normal': (0.0, 3.0), 'fat_tail_moderate': (-0.5, 5.0), 'fat_tail_severe': (-1.0, 7.0)}
    assert round(d['reference']['capped_equal_weight_sharpe_exbil'], 3) == 0.645
    assert round(d['check']['schur_dsr_reproduced'], 3) == 0.428
    assert d['decision']['status'] == 'pending' and d['decision']['owner'] == 'Jared'


def _build(d):
    out = {}
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_pages
    orig = page_mod.load
    page_mod.load = lambda: d
    try:
        page_mod.build_dsr_feasibility(build_pages.page_shell, lambda rel, html: out.__setitem__(rel, html))
    finally:
        page_mod.load = orig
    return out[page_mod.PAGE]


def test_committed_page_is_built_from_json():
    assert _build(_committed()) == PAGE.read_text(encoding='utf-8')


def test_page_figures_come_from_json():
    d = _committed()
    text = _text(PAGE.read_text(encoding='utf-8'))
    fig = lambda x, k=2: f'{x:.{k}f}'
    allowed = {fig(d['sr0_annual']), fig(d['c4']['hurdle_normal']), *(fig(x) for x in d['c4']['hurdle_fat_tail_range']),
               fig(d['reference']['capped_equal_weight_sharpe_exbil'], 3), f"{d['reference']['hurdle_to_ew_ratio']:.1f}",
               fig(d['check']['schur_dsr_reproduced'], 3), fig(d['check']['schur_dsr_recorded'], 3),
               fig(d['check']['schur_sharpe_exbil'], 3), f"{d['inputs']['sr_var_cross_trial_monthly']:.6f}",
               *(str(d['inputs'][k]) for k in ('T', 'N', 'registry_trials', 'registry_trials_with_sharpe')),
               str(d['check']['N']), *(fig(h['sharpe_exbil_annual']) for c in d['cases'] for h in c['hurdles']),
               *(f'{h["dsr"]:.2f}'.rstrip('0').rstrip('.') for h in d['cases'][0]['hurdles']),
               *(f'{c["kurtosis_raw"]:g}' for c in d['cases']), *(f'{abs(c["skew"]):g}' for c in d['cases']),
               '2014',  # citation year, in the JSON's method string
               '3'}     # 'normal = 3', the JSON's kurtosis convention
    figures = set(re.findall(r'(?<![\w.])\d+(?:\.\d+)?(?![\w])', re.sub(r'Book [12]\b|trial_registry|Trial-13', '', text)))
    assert figures <= allowed, figures - allowed
    # The headline figures are present.
    for x in (fig(d['c4']['hurdle_normal']), fig(d['reference']['capped_equal_weight_sharpe_exbil'], 3),
              *(fig(x) for x in d['c4']['hurdle_fat_tail_range']), fig(d['sr0_annual'])):
        assert x in text
    # Changing the JSON changes the page.
    alt = copy.deepcopy(d)
    alt['c4']['hurdle_normal'] = 9.87
    alt['reference']['capped_equal_weight_sharpe_exbil'] = 0.123
    built = _text(_build(alt))
    assert 'about 9.87, versus 0.123' in built


def test_page_leads_with_result_and_has_required_copy():
    raw = PAGE.read_text(encoding='utf-8')
    text = _text(raw)
    d = _committed()
    assert text.index('Result: trial 13 can’t pass C4') < text.index('Hurdles')
    assert 'The hurdle is a lower bound. If trial 13 scores well, it raises the cross-trial variance, and that raises SR0.' in text
    assert text.index('lower bound') < text.index('Hurdles')
    for opt in d['decision']['options']:
        assert opt in text
    assert 'Decision: pending with Jared.' in text
    assert 'vol-target backbone' in text
    assert raw.count('assets/nav.js') == 1 and 'class="nav-toggle"' in raw
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in raw
    assert 'lab:start' not in raw and '<img' not in raw  # site shell, not restyled; no images (brand and gold checks: repo-wide tests)


def test_methods_index_links_page_and_archive_untouched():
    assert f'href="{page_mod.PAGE.removeprefix("methods/")}"' in INDEX.read_text(encoding='utf-8')
    assert 'dsr_feasibility' not in ARCHIVE.read_text(encoding='utf-8')


def test_no_quant_files_in_repo():
    import subprocess
    files = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert not [f for f in files if Path(f).name.startswith('QUANT_')]
