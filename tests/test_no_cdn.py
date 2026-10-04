"""Runtime scripts must work offline without remote code dependencies.

Fonts are self-hosted too (docs/assets/fonts.css); tests/test_no_outside_host.py checks
that no page or stylesheet loads anything from an outside host.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REMOTE_SCRIPT = re.compile(
    r'<script\b[^>]*\bsrc\s*=\s*[\"\']?https?://'
    r'|\bimport\s*\(\s*[\"\']https?://'
    r'|\bimport\s+[^;]*?\bfrom\s*[\"\']https?://'
    r'|\bimport\s*[\"\']https?://', re.I,
)


def test_no_remote_javascript():
    paths = subprocess.check_output(['git', 'ls-files', '-z', 'docs', 'scripts'], cwd=ROOT).decode().split('\0')
    violations = []
    for name in paths:
        path = Path(name)
        if name.startswith('docs/assets/vendor/') or name.endswith('.map'):
            continue
        if not ((name.startswith('docs/') and path.suffix in {'.html', '.js', '.css'})
                or (path.parent == Path('scripts') and path.suffix == '.py')):
            continue
        if REMOTE_SCRIPT.search((ROOT / path).read_text()):
            violations.append(name)
    assert not violations, f'Remote runtime scripts: {violations}'
