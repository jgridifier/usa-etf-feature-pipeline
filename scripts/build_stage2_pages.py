#!/usr/bin/env python3
"""Stage-2 pages: Quant's robustness appendix (rendered) and teaching note (verbatim copy). Stdlib only.

- docs/methods/stage2_robustness.html is rendered from data/processed/stage2/stage2_robustness.md, a
  byte-for-byte copy of Quant's appendix (renamed; working-file names stay out of the repo). Its sha256 is
  pinned in APPENDIX_SHA256 and in data/processed/stage2/PROVENANCE.md.
- docs/methods/stage2_demiguel.html is Quant's teaching note: source bytes pinned in data/pinned_pages/ and published
  with only the lab-header blocks added (scripts/pinned_pages.py); never restyled.
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
TEACHING_SHA256: str | None = '08b251a2425b1802ddf5c8e7de63ab8b97469744d5fbff8490c3c8cb56fb0893'  # final revision (hash verified by CoS, 2026-10-04 09:06 ET; supersedes 8091157e…)
ADDENDUM3_SRC = ROOT / 'data/processed/stage2/stage2_holdout_addendum3.md'
ADDENDUM3_SHA256 = '47234cbc5f1af5beb9a859ccb56da52dfb28cb1164a507b6025a60f3994756df'
ADDENDUM3_PAGE = 'methods/stage2_addendum3.html'
ADDENDUM3_TITLE = 'Stage 2 holdout pre-registration, Addendum 3: final dispositions and errata'
RECHECK_SRC = ROOT / 'data/processed/stage2/stage2_livecore_recheck.md'
RECHECK_SHA256 = '930692cdd2f03e5a5024226a0abb3f17d02d26d86d20f6c841d1adc7740c12ff'
RECHECK_PAGE = 'methods/stage2_livecore_recheck.html'
RECHECK_TITLE = 'Live-core recheck for family 2 (correction to Addendum 3 E4)'
ADDENDUM3_RULING_ID = 's1-1'   # anchor on §1 item 1 (DeMiguel forward-tracked; supersedes 'N_holdout = 1')
# Addendum 2 is not published on Pages yet: the hub keeps a link slot for it (scripts/build_hub_pages.py).
TITLE = 'Stage 2 robustness appendix: KWZ, DeMiguel, replications, holdout power'


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def teaching_published(docs: Path) -> bool:
    """Published = docs/methods/<TEACHING> is the pinned source plus lab-header blocks only (scripts/pinned_pages.py)."""
    import pinned_pages
    p = docs / 'methods' / TEACHING
    return (TEACHING_SHA256 is not None and p.exists()
            and hashlib.sha256(pinned_pages.strip_lab(p.read_text(encoding='utf-8')).encode('utf-8')).hexdigest() == TEACHING_SHA256)


def publish_teaching(source: Path, docs: Path) -> None:
    """Stage Quant's note as the pinned source (data/pinned_pages/methods/<TEACHING>); the build publishes it with the
    lab header (scripts/pinned_pages.py). Refuses a source whose sha256 is not the pinned one."""
    if TEACHING_SHA256 is None:
        raise SystemExit('TEACHING_SHA256 is not pinned yet: the teaching note is not published until its final hash is set')
    got = sha256(source)
    if got != TEACHING_SHA256:
        raise SystemExit(f'teaching note sha256 {got} != pinned {TEACHING_SHA256}; not copied')
    import pinned_pages
    dest = pinned_pages.source_path('methods/' + TEACHING) if docs == pinned_pages.DOCS else docs / 'methods' / TEACHING
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)


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
            cls = 'formula' if '=' in ln else 'cont'     # indented prose continues the list item above it
            html.append(f'<p class="{cls}">{inline(ln.strip())}</p>')
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


STYLE = ('<style>.stage2 .formula{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:.85rem;'
         'overflow-wrap:anywhere;padding:.25rem 0 .25rem .75rem;border-left:2px solid #1c2d6b}'
         '.stage2 table{font-size:.85rem}.stage2 h2{margin-top:2rem}.stage2 code{overflow-wrap:anywhere}'
         '.stage2 .cont{padding-left:1.25rem}.stage2 .lab-link{display:block;font-size:.85rem;margin:.2rem 0 .4rem;padding-left:.6rem;border-left:2px solid #1c2d6b}'
         '.stage2 :target{outline:2px solid #1c2d6b;outline-offset:2px}</style>')
NHOLDOUT_LI = '<li>N_holdout = 1, DeMiguel only.'


def _check(src: Path, pin: str, name: str) -> str:
    if sha256(src) != pin:
        raise SystemExit(f'{name} does not match its pinned sha256; update the pin with Quant\'s new hash')
    md = src.read_text(encoding='utf-8')
    return md.split('\n', 1)[1] if md.startswith('# ') else md


def link_nholdout(html: str, href: str) -> str:
    """Add a lab link to Addendum 3 §1.1 right after the 'N_holdout = 1' ruling (§7).

    Quant's §7 text is not edited: the link is a separate, labelled lab element placed after the list item."""
    i = html.find(NHOLDOUT_LI)
    if i < 0:
        raise SystemExit("robustness appendix: 'N_holdout = 1, DeMiguel only' not found; cannot place the Addendum 3 link")
    j = html.find('</li>', i) + len('</li>')
    note = (f'<li class="lab-link" aria-label="Lab note">Lab note: superseded by '
            f'<a href="{href}">Addendum 3 §1.1</a> (DeMiguel is forward-tracked only; the holdout is not run).</li>')
    return html[:j] + note + html[j:]


def anchor_first_ruling(html: str) -> str:
    """Give §1 item 1 of Addendum 3 a stable id so other pages can link 'Addendum 3 §1.1'."""
    h = html.find('1. Rulings recorded')
    i = html.find('<li>', h)
    if h < 0 or i < 0:
        raise SystemExit('Addendum 3: §1 item 1 not found')
    return html[:i] + f'<li id="{ADDENDUM3_RULING_ID}">' + html[i + 4:]


def _header(sha: str, prov: str) -> str:
    return ('<p class="muted">Quant · 2026-10-04 (ET) · research only, not investment advice. Published verbatim from Quant\'s '
            f'document (sha256 <code>{sha[:12]}…</code>; see {prov}). Nothing was re-run for this page.</p>')


def link_e4(html: str) -> str:
    """Lab link from Addendum 3 E4 to Quant's correction (E4's text is not edited)."""
    if not RECHECK_SRC.exists():
        return html
    i = html.find('E4 (September 2026 core row)')
    if i < 0:
        raise SystemExit('Addendum 3: E4 not found')
    j = html.find('</li>', i) + len('</li>')
    note = ('<li class="lab-link" aria-label="Lab note">Lab note: corrected by Quant\'s '
            '<a href="stage2_livecore_recheck.html">live-core recheck</a>: family 2 already used the corrected month; nothing is recomputed.</li>')
    return html[:j] + note + html[j:]


A6_NOTE = ('Lab note: −0.71 pp (−0.705 at 5 bp, −0.712 at 10 bp) from A_dev_results.json supersedes −0.73, '
           'a transcription error (Quant).')
A6_MARKERS = {'addendum3': "A6's gap is −0.73 pp against the live core.", 'recheck': 'its gap is −0.73 pp'}


def note_a6(html: str, which: str) -> str:
    """Lab note after the list item carrying A6's −0.73 pp gap (the pinned text itself is not edited)."""
    i = html.find(A6_MARKERS[which])
    if i < 0:
        raise SystemExit(f'{which}: A6 −0.73 pp line not found; cannot place the A6 lab note')
    j = html.find('</li>', i) + len('</li>')
    note = f'<li class="lab-link a6-note" aria-label="Lab note">{escape(A6_NOTE)}</li>'
    return html[:j] + note + html[j:]


DSR6_NOTE = "Lab note: 0.563 on complete months (Quant's Sept recompute, sha fe895441…) supersedes 0.533."
DSR6_MARKER = 'it is 0.533 at N = 72'


def note_dsr6(html: str) -> str:
    """Lab note after Addendum 3 E6 (the #6 grid DSR 0.533); the pinned text is not edited."""
    i = html.find(DSR6_MARKER)
    if i < 0:
        raise SystemExit('Addendum 3: E6 0.533 line not found; cannot place the DSR lab note')
    j = html.find('</li>', i) + len('</li>')
    return html[:j] + f'<li class="lab-link dsr6-note" aria-label="Lab note">{escape(DSR6_NOTE)}</li>' + html[j:]


def build_recheck(page_shell, write_page, docs: Path) -> bool:
    if not RECHECK_SRC.exists():
        return False
    body = _check(RECHECK_SRC, RECHECK_SHA256, 'stage2_livecore_recheck.md')
    content = ('<article class="prose stage2">' f'<h1>{escape(RECHECK_TITLE)}</h1>'
               + _header(RECHECK_SHA256, 'data/processed/stage2/PROVENANCE.md')
               + '<p><a href="stage2_addendum3.html">Addendum 3</a> · <a href="stage2_robustness.html">Stage 2 robustness appendix</a></p>'
               + note_a6(render_markdown(body), 'recheck') + '</article>')
    write_page(RECHECK_PAGE, page_shell(RECHECK_TITLE, content, prefix='../', active='methods/index.html', extra_head=STYLE))
    return True


def build_addendum3(page_shell, write_page, docs: Path) -> bool:
    if not ADDENDUM3_SRC.exists():
        return False
    body = _check(ADDENDUM3_SRC, ADDENDUM3_SHA256, 'stage2_holdout_addendum3.md')
    links = ('<p><a href="stage2_robustness.html">Stage 2 robustness appendix</a>'
             + (f' · <a href="{TEACHING}">Teaching note: the DeMiguel tilt</a>' if teaching_published(docs) else '')
             + (' · <a href="results/index.html">Results hub</a>' if (docs / 'methods/results/index.html').exists() else '')
             + '</p>')
    content = ('<article class="prose stage2">' f'<h1>{escape(ADDENDUM3_TITLE)}</h1>'
               + _header(ADDENDUM3_SHA256, 'data/processed/stage2/PROVENANCE.md') + links
               + note_dsr6(note_a6(link_e4(anchor_first_ruling(render_markdown(body))), 'addendum3')) + '</article>')
    write_page(ADDENDUM3_PAGE, page_shell(ADDENDUM3_TITLE, content, prefix='../', active='methods/index.html', extra_head=STYLE))
    return True


def build_page(page_shell, write_page, docs: Path) -> bool:
    build_addendum3(page_shell, write_page, docs)
    build_recheck(page_shell, write_page, docs)
    if not APPENDIX_SRC.exists():
        return False
    body = _check(APPENDIX_SRC, APPENDIX_SHA256, 'stage2_robustness.md')
    if teaching_published(docs):
        teach = f'<a href="{TEACHING}">Quant\'s teaching note: the DeMiguel tilt</a>'
    else:
        teach = 'Quant\'s teaching note is being revised and will be linked here once its final version is published.'
    html = render_markdown(body)
    if ADDENDUM3_SRC.exists():
        html = link_nholdout(html, f'stage2_addendum3.html#{ADDENDUM3_RULING_ID}')
        teach += ' · <a href="stage2_addendum3.html">Addendum 3 (final dispositions and errata)</a>'
    content = (
        '<article class="prose stage2">'
        f'<h1>{escape(TITLE)}</h1>'
        '<p class="muted">Quant · 2026-10-04 (ET) · research only, not investment advice. Published verbatim from Quant\'s '
        f'appendix (sha256 <code>{APPENDIX_SHA256[:12]}…</code>; see data/processed/stage2/PROVENANCE.md). '
        'Every figure below is Quant\'s, from <code>stage2_code/results/</code>; nothing was re-run for this page.</p>'
        f'<p>{teach}' + (' · <a href="results/index.html">Results hub</a>' if (docs / 'methods/results/index.html').exists() else '')
        + '</p>'
        + html +
        '</article>'
    )
    write_page(PAGE, page_shell(TITLE, content, prefix='../', active='methods/index.html', extra_head=STYLE))
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
