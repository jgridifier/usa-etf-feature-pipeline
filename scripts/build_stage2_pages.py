#!/usr/bin/env python3
"""Stage-2 pages: Quant's robustness appendix (rendered) and teaching note (verbatim copy). Stdlib only.

- docs/methods/stage2_robustness.html is rendered from data/processed/stage2/stage2_robustness.md, a
  byte-for-byte copy of Quant's appendix (renamed; working-file names stay out of the repo). Its sha256 is
  pinned in APPENDIX_SHA256 and in data/processed/stage2/PROVENANCE.md.
- docs/methods/stage2_demiguel_kwz.html is Quant's teaching note, published byte-for-byte and never restyled.
  It is copied ONLY when TEACHING_SHA256 is set and the source matches it:
      python scripts/build_stage2_pages.py --teaching-source /path/to/stage2_demiguel.html
  While TEACHING_SHA256 is None (Quant is revising the note), no teaching page ships and the appendix says so.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPENDIX_SRC = ROOT / 'data/processed/stage2/stage2_robustness.md'
APPENDIX_SHA256 = 'c1ca949521e3132f9bae592acfcb5fe53fa323fdd48b646d6bc6b14963fbde17'
PAGE = 'methods/stage2_robustness.html'
TEACHING = 'stage2_demiguel.html'                   # under docs/methods/ (the old *_kwz.html is never published)
TEACHING_SHA256: str | None = '8091157e656d740ceae02f2f53ec75ff049c02a8e8c56364d05ce379a9e1625d'  # final (CoS, 2026-10-04 08:25 ET)
TITLE = 'Stage 2 robustness appendix: KWZ, DeMiguel, replications, holdout power'


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def teaching_published(docs: Path) -> bool:
    p = docs / 'methods' / TEACHING
    return TEACHING_SHA256 is not None and p.exists() and sha256(p) == TEACHING_SHA256


def publish_teaching(source: Path, docs: Path) -> None:
    if TEACHING_SHA256 is None:
        raise SystemExit('TEACHING_SHA256 is not pinned yet: the teaching note is not published until its final hash is set')
    got = sha256(source)
    if got != TEACHING_SHA256:
        raise SystemExit(f'teaching note sha256 {got} != pinned {TEACHING_SHA256}; not copied')
    shutil.copyfile(source, docs / 'methods' / TEACHING)


# ── minimal Markdown renderer (the subset the appendix uses) ──────────────────
def inline(t: str) -> str:
    codes = []

    def keep(m):
        codes.append(f'<code>{escape(m.group(1))}</code>')
        return f'\x00{len(codes) - 1}\x00'
    s = escape(re.sub(r'`([^`]+)`', keep, t), quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])', r'<em>\1</em>', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: codes[int(m.group(1))], s)


def _table(lines: list[str], caption: str) -> str:
    cells = [[c.strip() for c in ln.strip().strip('|').split('|')] for ln in lines]
    head, body = cells[0], cells[2:]
    return (f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(caption)}"><table><thead><tr>'
            + ''.join(f'<th scope="col">{inline(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in body)
            + '</tbody></table></div>')


def render_markdown(md: str) -> str:
    lines, html, i, heading = md.splitlines(), [], 0, 'table'
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = re.match(r'^(#{1,4})\s+(.*)$', ln)
        if m:
            level = min(len(m.group(1)), 4)
            heading = m.group(2)
            slug = re.sub(r'[^a-z0-9]+', '-', heading.lower()).strip('-')
            html.append(f'<h{level} id="{slug}">{inline(heading)}</h{level}>')
            i += 1
            continue
        if ln.lstrip().startswith('|'):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                block.append(lines[i]); i += 1
            html.append(_table(block, heading))
            continue
        if re.match(r'^\s*(-|\d+\.)\s+', ln):
            html.append(_list(lines, i))
            while i < len(lines) and (re.match(r'^\s*(-|\d+\.)\s+', lines[i]) or
                                      (lines[i].startswith('   ') and lines[i].strip())):
                i += 1
            continue
        if ln.startswith('  ') and not ln.startswith('   -'):
            html.append(f'<p class="formula">{inline(ln.strip())}</p>')
            i += 1
            continue
        para = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#|\||\s*(-|\d+\.)\s|  \S)', lines[i]):
            para.append(lines[i]); i += 1
        html.append(f'<p>{inline(" ".join(p.strip() for p in para))}</p>')
    return '\n'.join(html)


def _list(lines: list[str], start: int) -> str:
    """Render a (possibly nested, two levels) list starting at lines[start]."""
    items, i = [], start
    while i < len(lines):
        m = re.match(r'^(\s*)(-|\d+\.)\s+(.*)$', lines[i])
        if not m:
            break
        indent = len(m.group(1))
        if indent == 0:
            items.append([m.group(2), m.group(3), []])
        elif items:
            items[-1][2].append(m.group(3))
        i += 1
    ordered = items and items[0][0] != '-'
    tag = 'ol' if ordered else 'ul'
    out = [f'<{tag}>']
    for _, text, subs in items:
        sub = ('<ul>' + ''.join(f'<li>{inline(s)}</li>' for s in subs) + '</ul>') if subs else ''
        out.append(f'<li>{inline(text)}{sub}</li>')
    out.append(f'</{tag}>')
    return ''.join(out)


def build_page(page_shell, write_page, docs: Path) -> bool:
    if not APPENDIX_SRC.exists():
        return False
    if sha256(APPENDIX_SRC) != APPENDIX_SHA256:
        raise SystemExit('stage2_robustness.md does not match its pinned sha256; update the pin with Quant\'s new hash')
    md = APPENDIX_SRC.read_text(encoding='utf-8')
    body = md.split('\n', 1)[1] if md.startswith('# ') else md
    if teaching_published(docs):
        teach = f'<a href="{TEACHING}">Quant\'s teaching note: the DeMiguel tilt</a>'
    else:
        teach = 'Quant\'s teaching note is being revised and will be linked here once its final version is published.'
    content = (
        '<article class="prose stage2">'
        f'<h1>{escape(TITLE)}</h1>'
        '<p class="muted">Quant · 2026-10-04 (ET) · research only, not investment advice. Published verbatim from Quant\'s '
        f'appendix (sha256 <code>{APPENDIX_SHA256[:12]}…</code>; see data/processed/stage2/PROVENANCE.md). '
        'Every figure below is Quant\'s, from <code>stage2_code/results/</code>; nothing was re-run for this page.</p>'
        f'<p>{teach}' + (' · <a href="results/index.html">Results hub</a>' if (docs / 'methods/results/index.html').exists() else '')
        + '</p>'
        + render_markdown(body) +
        '</article>'
    )
    style = ('<style>.stage2 .formula{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:.85rem;'
             'overflow-wrap:anywhere;padding:.25rem 0 .25rem .75rem;border-left:2px solid #1c2d6b}'
             '.stage2 table{font-size:.85rem}.stage2 h2{margin-top:2rem}.stage2 code{overflow-wrap:anywhere}</style>')
    write_page(PAGE, page_shell(TITLE, content, prefix='../', active='methods/index.html', extra_head=style))
    return True


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--teaching-source', type=Path)
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_pages  # noqa: E402
    if args.teaching_source:
        publish_teaching(args.teaching_source, build_pages.DOCS)
    build_page(build_pages.page_shell, build_pages.write_page, build_pages.DOCS)
    print('stage-2 pages built; teaching note published:', teaching_published(build_pages.DOCS))
