"""Quant's byte-pinned pages, published with the shared lab header injected at build time.

Source of truth: data/pinned_pages/<docs path>, committed byte-for-byte from Quant's files. Each source's sha256 is
pinned in SOURCES below; the build refuses a source that does not match. The published page in docs/ is the source
plus three <!-- lab:start -->…<!-- lab:end --> blocks (the same convention as the Schur teaching note):
  * before </head>:  a link to docs/assets/lab-header.css (header-only, scoped rules; the page's CSS is untouched);
  * after <body>:    the shared site header (nav_html) and a link back to the results hub;
  * before </body>:  docs/assets/nav.js (the 375px menu toggle).
Removing the lab blocks gives back the source bytes exactly; tests pin the source and the published hash separately.

Swapping in Quant's revised files is one commit:
    python scripts/pinned_pages.py --swap beat_benchmark /path/to/folder index.html=<sha> idea1_….html=<sha> …
which verifies each file against the given sha256, copies it into data/pinned_pages/, rewrites SOURCES here,
rebuilds the published pages and prints the new published hashes for tests/test_beat_benchmark_pages.py.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / 'data' / 'pinned_pages'
DOCS = ROOT / 'docs'
HUB = 'methods/results/index.html'
GLOSSARY = ('methods/beat_benchmark/index.html', 'glossary')   # header link on the beat-benchmark pages (CoS, 2026-10-04)

# docs-relative path -> sha256 of Quant's source bytes (data/pinned_pages/<path>)
SOURCES = {
    'methods/stage2_demiguel.html': '08b251a2425b1802ddf5c8e7de63ab8b97469744d5fbff8490c3c8cb56fb0893',
    # beat-the-benchmark shortlist, final revision of 2026-10-04 (hashes from CoS, 22:48 ET)
    'methods/beat_benchmark/index.html': 'c51c8cedbde9ed1a5646e54de19798d8fb4a933d812ed52931a083f1e52127cb',
    'methods/beat_benchmark/idea1_downside_vol_backbone.html': '3aee82fde8578f09495d93451996a97c3d7dc387704993524a14146375973d19',
    'methods/beat_benchmark/idea2_fixed_blend_book2_core.html': 'cdece2fbd5e9c50542a21cca99d334608ef8433dbdd7417304f309d2c0a0cccf',
    'methods/beat_benchmark/idea3_har_vol_forecast.html': 'f81988643880258ffddb873bc9b35285d0f088278608209f60d629088f5ea296',
}
LAB = re.compile(r'<!-- lab:start -->.*?<!-- lab:end -->', re.S)
BODY = re.compile(r'<body\b[^>]*>')


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def strip_lab(html: str) -> str:
    return LAB.sub('', html)


def _rel(rel: str, target: str) -> str:
    return os.path.relpath(target, os.path.dirname(rel) or '.').replace(os.sep, '/')


def inject(source: str, rel: str, nav_html) -> str:
    """Source page -> published page. Only adds lab blocks; strip_lab(inject(s)) == s."""
    if LAB.search(source):
        raise ValueError(f'{rel}: source already carries lab blocks')
    if source.count('</head>') != 1 or source.count('</body>') != 1 or len(BODY.findall(source)) != 1:
        raise ValueError(f'{rel}: expected one </head>, one <body>, one </body>')
    prefix = _rel(rel, 'index.html')
    prefix = '' if prefix == 'index.html' else prefix[:-len('index.html')]
    head = (f'<!-- lab:start --><link rel="stylesheet" href="{prefix}assets/lab-header.css">'
            f'<link rel="icon" type="image/svg+xml" href="{prefix}favicon.svg"><!-- lab:end -->')
    top = ('<!-- lab:start -->' + nav_html(prefix, 'methods/index.html')
           + f'<p class="lab-backlink"><a href="{_rel(rel, HUB)}">← Results hub</a>'
           + (f' · <a href="{_rel(rel, GLOSSARY[0])}#{GLOSSARY[1]}">Glossary</a>' if rel.startswith('methods/beat_benchmark/') else '')
           + '</p><!-- lab:end -->')
    tail = f'<!-- lab:start --><script src="{prefix}assets/nav.js" defer></script><!-- lab:end -->'
    out = source.replace('</head>', head + '</head>', 1)
    m = BODY.search(out)
    out = out[:m.end()] + top + out[m.end():]
    out = out.replace('</body>', tail + '</body>', 1)
    assert strip_lab(out) == source
    return out


def source_path(rel: str) -> Path:
    return SRC_DIR / rel


def verified_source(rel: str) -> str:
    raw = source_path(rel).read_bytes()
    got = sha256(raw)
    if got != SOURCES[rel]:
        raise SystemExit(f'{rel}: source sha256 {got} != pinned {SOURCES[rel]}; not published')
    return raw.decode('utf-8')


def publish(nav_html, docs: Path = DOCS) -> dict[str, str]:
    """Write every pinned page into docs/ with the lab header; returns {path: published sha256}."""
    out = {}
    for rel in SOURCES:
        html = inject(verified_source(rel), rel, nav_html)
        dest = docs / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding='utf-8')
        out[rel] = sha256(dest.read_bytes())
    return out


def swap(group: str, folder: Path, pins: dict[str, str]) -> None:
    """Copy Quant's revised files for one group (e.g. beat_benchmark) after checking each against its sha256."""
    keys = [k for k in SOURCES if k.startswith(f'methods/{group}/')]
    if sorted(Path(k).name for k in keys) != sorted(pins):
        raise SystemExit(f'need a sha256 for each of {sorted(Path(k).name for k in keys)}')
    for name, want in pins.items():
        got = sha256((folder / name).read_bytes())
        if got != want:
            raise SystemExit(f'{name}: sha256 {got} != given {want}; nothing copied')
    me = Path(__file__).read_text(encoding='utf-8')
    for name, want in pins.items():
        rel = f'methods/{group}/{name}'
        shutil.copyfile(folder / name, source_path(rel))
        assert sha256(source_path(rel).read_bytes()) == want
        me = re.sub(rf"('{re.escape(rel)}': ')[0-9a-f]{{64}}'", rf"\g<1>{want}'", me)
        SOURCES[rel] = want
    Path(__file__).write_text(me, encoding='utf-8')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--swap', nargs='+', metavar=('GROUP FOLDER', 'NAME=SHA'))
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_pages  # noqa: E402
    if a.swap:
        swap(a.swap[0], Path(a.swap[1]), dict(x.split('=', 1) for x in a.swap[2:]))
    for rel, sha in publish(build_pages.nav_html).items():
        print(sha, rel)
