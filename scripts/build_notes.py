"""Render notes written for Jared (docs/notes/*.md) as static site pages.

Only reader-facing notes live in docs/notes/. Working files (QUANT_*, CIO_NOTE_*,
engineering tickets, run folders) are never copied here; a note is published by
copying a cleaned version into docs/notes/<slug>.md and listing it in NOTES.
Pending notes are listed with status='pending' and rendered as an unlinked
marker until their .md lands, so the notes link check stays green.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / 'docs' / 'notes'

# slug, title, status ('published' | 'pending'), pending reason
NOTES = [
    ('allocator_candidates', 'CIO note: candidates for the 100+ ETF allocator (30 Sep 2026)', 'published', ''),
    ('book2_lw2008_drawdowns', 'Quant note: Book 2 vs the vol-target backbone (Sharpe test and drawdowns, Oct 2026)', 'published', ''),
    ('book2_reframe', 'CIO note: Book 2, the drawdown-controlled version of the same core (Oct 2026)', 'published', ''),
    ('stage2_wrap', 'CIO note: stage 2 wrap-up (Oct 2026)', 'published', ''),
]
# Pinned notes: published verbatim; the build refuses a copy whose bytes differ (CIO + CoS approved 2026-10-04).
NOTE_SHA256 = {'stage2_wrap': '2efdf27b345d152cdb111406ea10dd4167617d0f47b21591bf68308063814491'}
# Build-time banners: injected above the note body; the .md sources are not edited (PM, 2026-10-04).
SEPT_FIX_BANNER = 'Superseded: Book 2 Sharpe ex-BIL is 0.99 after the September full-month fix.'
NOTE_BANNERS = {'book2_reframe': SEPT_FIX_BANNER, 'book2_lw2008_drawdowns': SEPT_FIX_BANNER}
BACKBONE_JSON = ROOT / 'data' / 'processed' / 'hub' / 'subjects' / 'backbone.json'


def backbone_cagr_banner() -> str:
    """Dated lab note for the pinned stage-2 wrap-up (CoS, 2026-10-04): its table prints the Backbone CAGR as 15.1%.
    Every figure comes from data/processed/hub/subjects/backbone.json (own; vs_core.own_window.b is the core)."""
    import json
    d = json.loads(BACKBONE_JSON.read_text(encoding='utf-8'))
    own, core = d['own'], d['vs_core']['own_window']['b']
    assert (own['n'], own['start'], own['end']) == (core['n'], core['start'], core['end'])
    pct = lambda x: f'{100 * x:.2f}%'
    return (f"Lab note, 2026-10-04: the Backbone row of the table in §6 prints CAGR 15.1%; from the hub data it is "
            f"{pct(own['cagr'])}. Over the {own['n']} months {own['start']} to {own['end']}, the backbone and the core are "
            f"level on CAGR ({pct(own['cagr'])} vs {pct(core['cagr'])}), and the backbone's edge is lower risk "
            f"(Sharpe {own['sharpe_exbil']:.2f} vs {core['sharpe_exbil']:.2f}), not higher return. No verdict changes. "
            f"The note itself is published verbatim at its pinned hash.")


# Callable banners are computed from data at build time.
NOTE_BANNERS['stage2_wrap'] = backbone_cagr_banner


def _inline(text: str) -> str:
    parts = re.split(r'(`[^`]+`)', text)
    out = []
    for part in parts:
        if part.startswith('`') and part.endswith('`') and len(part) > 1:
            out.append('<code>' + escape(part[1:-1]) + '</code>')
            continue
        s = escape(part, quote=False)
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', s)
        s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', s)
        out.append(s)
    return ''.join(out)


def md_to_html(md: str) -> str:
    """Minimal Markdown subset: headings, paragraphs, nested lists, pipe tables."""
    lines = md.splitlines()
    html: list[str] = []
    stack: list[tuple[str, int]] = []  # (tag, indent)
    para: list[str] = []

    def flush_para():
        if para:
            html.append('<p>' + _inline(' '.join(para)) + '</p>')
            para.clear()

    def close_lists(to_indent: int = -1):
        while stack and stack[-1][1] > to_indent:
            tag, _ = stack.pop()
            html.append(f'</li></{tag}>')

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush_para()
            i += 1
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            flush_para(); close_lists()
            level = min(len(m.group(1)) + 0, 6)
            html.append(f'<h{level}>{_inline(m.group(2).strip())}</h{level}>')
            i += 1
            continue
        if line.lstrip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            flush_para(); close_lists()
            def cells(row):
                return [c.strip() for c in row.strip().strip('|').split('|')]
            head = cells(line)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                body.append(cells(lines[i])); i += 1
            html.append(
                '<div class="table-scroll" tabindex="0" role="region" aria-label="table">'
                '<table><thead><tr>' + ''.join(f'<th scope="col">{_inline(h)}</th>' for h in head)
                + '</tr></thead><tbody>'
                + ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in r) + '</tr>' for r in body)
                + '</tbody></table></div>'
            )
            continue
        m = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', line)
        if m:
            flush_para()
            indent = len(m.group(1))
            tag = 'ol' if m.group(2)[0].isdigit() else 'ul'
            if stack and stack[-1][1] == indent:
                html.append('</li><li>')
            elif stack and stack[-1][1] > indent:
                close_lists(indent)
                if stack and stack[-1][1] == indent:
                    html.append('</li><li>')
                else:
                    stack.append((tag, indent)); html.append(f'<{tag}><li>')
            else:
                stack.append((tag, indent)); html.append(f'<{tag}><li>')
            html.append(_inline(m.group(3)))
            i += 1
            continue
        if stack and line.startswith(' '):
            html.append(' ' + _inline(line.strip()))
            i += 1
            continue
        close_lists()
        para.append(line.strip())
        i += 1
    flush_para(); close_lists()
    return '\n'.join(html)


def notes_list_html(prefix: str) -> str:
    """List for the Methods page; prefix is the path from that page to docs/notes/."""
    items = []
    for slug, title, status, reason in NOTES:
        if status == 'published':
            items.append(f'<li><a href="{prefix}{slug}.html">{escape(title)}</a></li>')
        else:
            items.append(
                f'<li><span class="note-pending" data-pending-note="notes/{slug}.md">'
                f'{escape(title)}</span> <em class="muted">({escape(reason)})</em></li>'
            )
    return '<ul class="method-list">' + ''.join(items) + '</ul>'


def banner_text(slug: str) -> str:
    b = NOTE_BANNERS[slug]
    return b() if callable(b) else b


def build_notes(page_shell, write_page) -> None:
    for slug, title, status, _ in NOTES:
        if status != 'published':
            continue
        path = NOTES_DIR / f'{slug}.md'
        if slug in NOTE_SHA256:
            import hashlib
            got = hashlib.sha256(path.read_bytes()).hexdigest()
            if got != NOTE_SHA256[slug]:
                raise SystemExit(f'notes/{slug}.md sha256 {got} != pinned {NOTE_SHA256[slug]}; not published')
        md = path.read_text(encoding='utf-8')
        body = md_to_html(md)
        content = (
            '<section class="band"><div class="band-inner note-body">'
            '<p><span class="badge">Note for Jared</span></p>'
            + (f'<p class="callout note-banner" role="note">{escape(banner_text(slug))}</p>' if slug in NOTE_BANNERS else '')
            + body
            + f'<p class="dl"><a href="{slug}.md">Markdown source</a> · '
            '<a href="../methods/index.html#notes">All notes</a></p>'
            '</div></section>'
        )
        write_page(f'notes/{slug}.html', page_shell(
            title, content, prefix='../', active='methods/index.html', include_charts=False,
        ))
