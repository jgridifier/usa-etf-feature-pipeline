"""vol_target_oos_* reach the pages, the hub and the apps from data/processed/live/ only (CoS, 2026-10-04).

The top-level data/processed/vol_target_oos_{returns,summary}.csv (cash = 0 research run, ending at the partial day
2026-09-16) were retired: moved byte-for-byte to data/processed/frozen/vol_target_cash0_2026-09-16/ for the gate audits
(cash_null_audit, EPO's gross Book 1 reference) and replaced by a README pointer.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'data/processed'
LIVE = PROC / 'live'
NAMES = ('vol_target_oos_returns.csv', 'vol_target_oos_summary.csv')
PAGE_BUILDERS = [*sorted((ROOT / 'scripts').glob('build_*.py')), ROOT / 'scripts/hub_charts.py',
                 ROOT / 'scripts/pinned_pages.py', ROOT / 'src/usa_etf_features/hub_data.py']
APPS = sorted((ROOT / 'apps/pages/src').rglob('*.ts*'))


def test_top_level_copies_are_retired():
    for n in NAMES:
        assert not (PROC / n).exists(), n
        assert (PROC / 'frozen/vol_target_cash0_2026-09-16' / n).exists(), n
    assert 'data/processed/live/vol_target_oos_returns.csv' in (PROC / 'vol_target_oos_README.md').read_text()


def test_published_copies_are_the_live_files():
    for n in NAMES:
        assert (ROOT / 'docs/data' / n).read_bytes() == (LIVE / n).read_bytes(), n
    assert (ROOT / 'docs/data/vol_target_oos_returns.csv').read_text().rstrip().splitlines()[-1].startswith('2026-09-30')


def test_page_builders_name_no_vol_target_file_outside_live():
    bad = []
    for p in PAGE_BUILDERS:
        for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            code = line.split('#', 1)[0]
            for m in re.finditer(r"['\"]([^'\"]*vol_target_oos_[a-z]+\.csv)['\"]", code):
                lit = m.group(1)
                # bare names are docs/data reads (build_pages.read_csv) and copies from live/ (copy_cio_inputs)
                if '/' in lit and not lit.startswith(('data/processed/live/', 'live/')):
                    bad.append(f'{p.relative_to(ROOT)}:{i}: {lit}')
            if re.search(r"_f\(\s*'vol_target_oos_", code):
                bad.append(f'{p.relative_to(ROOT)}:{i}: hub _f() outside live/')
    assert not bad, bad
    src = (ROOT / 'scripts/build_pages.py').read_text(encoding='utf-8')
    assert "shutil.copyfile(ROOT / 'data' / 'processed' / 'live' / name, DATA / name)" in src


def test_apps_import_no_vol_target_data_outside_docs_data():
    for p in APPS:
        s = p.read_text(encoding='utf-8')
        for m in re.finditer(r"import[^;]*['\"]([^'\"]*vol_target_oos[^'\"]*)['\"]", s):
            raise AssertionError(f'{p}: imports {m.group(1)}')
        assert 'data/processed/vol_target_oos' not in s, p


def test_hub_builder_opens_vol_target_files_only_under_live():
    sys.path.insert(0, str(ROOT / 'src'))
    from usa_etf_features import hub_data
    opened, on = [], [True]

    def hook(event, args):
        if on[0] and event == 'open' and args and isinstance(args[0], (str, Path)) and 'vol_target_oos_' in str(args[0]):
            opened.append(Path(args[0]).resolve())
    sys.addaudithook(hook)
    try:
        hub_data.build(ROOT)
    finally:
        on[0] = False
    assert opened, 'hub builder read no vol_target_oos_* file'
    outside = [str(p) for p in opened if LIVE.resolve() not in p.parents]
    assert not outside, outside
