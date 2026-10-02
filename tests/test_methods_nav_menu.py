"""Every methods page with the site header's mobile menu button also loads the script that opens it.

The 375px menu (.nav-toggle) only works with assets/nav.js. restyle_methods_shell injected the header
without the script, so the menu did not open on restyled pages (found on the live site, 2026-10-02).
"""
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / 'docs'
# Published byte-for-byte from Quant's source; its menu needs the script added in the source.
BYTE_COPIES = {'allocation_alpha_schur.html'}


def test_nav_toggle_pages_load_nav_js():
    missing = []
    for p in sorted((DOCS / 'methods').glob('*.html')):
        html = p.read_text(encoding='utf-8')
        if 'class="nav-toggle"' in html and 'assets/nav.js' not in html and p.name not in BYTE_COPIES:
            missing.append(p.name)
    assert not missing, missing
