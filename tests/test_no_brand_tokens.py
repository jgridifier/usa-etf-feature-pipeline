"""Prevent institutional branding and policy claims in the checked tree."""
from pathlib import Path
import re

# Split literals keep the gate itself clean without an allowlist.
PATTERNS = [
    r'\b' + 'gold' + r'man\b',
    r'\b' + 'sa' + r'chs\b',
    'pre' + r'-?clearance',
    r'\bgs\s+' + r'policy\b',
    'pre-' + 'approved',
    r'\bfirm\s+' + r'annex\b',
    r'\bgs\s+' + r'usa\b',
]
FORBIDDEN = re.compile('|'.join(PATTERNS), re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]
SCAN = ['README.md', 'pyproject.toml', 'config', 'src', 'tests', 'data/raw', 'docs', 'scripts']
EXCLUDED = {'.git', '.venv', '__pycache__', '.pytest_cache'}


def test_no_brand_tokens():
    violations = []
    for name in SCAN:
        root = ROOT / name
        assert root.exists(), f'Missing checked path: {name}'
        for path in ([root] if root.is_file() else sorted(root.rglob('*'))):
            if not path.is_file() or any(p in EXCLUDED or p.endswith('.egg-info') for p in path.parts):
                continue
            for number, line in enumerate(path.read_bytes().decode('utf-8', errors='replace').splitlines(), 1):
                if FORBIDDEN.search(line):
                    violations.append(f'{path.relative_to(ROOT)}:{number}')
    assert not violations, 'Forbidden branding at:\n' + '\n'.join(violations)


def test_gate_patterns_and_ticker_boundaries():
    examples = ['gold' + 'man', 'sa' + 'chs', 'pre' + 'clearance',
                'pre-' + 'clearance', 'GS ' + 'policy', 'pre-' + 'approved',
                'firm ' + 'annex', 'GS ' + 'USA']
    for text in examples:
        assert FORBIDDEN.search(text.upper())
    assert not FORBIDDEN.search('GSIE GSLC GSUS GSSC ETF GUSA')
