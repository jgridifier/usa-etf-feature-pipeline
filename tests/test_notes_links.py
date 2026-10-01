"""Notes link check: pages may only link to notes that live in docs/notes/.

Only notes written for Jared are published, by copying a cleaned version into
docs/notes/ and rendering it as a page (scripts/build_notes.py). Working files
(QUANT_*, CIO_NOTE_*, engineering tickets, gate files) are never linked or copied.
Pending notes are shown as unlinked markers (data-pending-note), so this check
stays green while they are still missing.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
NOTES = DOCS / 'notes'
SPA_SRC = ROOT / 'apps' / 'pages' / 'src'

LINK_RE = re.compile(r'''\b(?:href|src)\s*=\s*\{?\s*["'`]([^"'`]+)["'`]''', re.I)
NOTE_LIKE = re.compile(
    r'\.md$|(^|/)notes/|CIO_NOTE|QUANT_(NOTE|GATE)|ENGINEERING_TICKET|NEXT_METHOD_HANDOFF', re.I
)
WORKING_NAME = re.compile(r'^(QUANT_|CIO_NOTE|CIO_BET|ENGINEERING_TICKET|NEXT_METHOD)', re.I)


def _notes_registry():
    spec = importlib.util.spec_from_file_location('build_notes', ROOT / 'scripts' / 'build_notes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.NOTES


def _pages():
    for p in sorted(DOCS.rglob('*.html')):
        yield p, p.parent
    for p in sorted(SPA_SRC.rglob('*')):
        if p.suffix in {'.tsx', '.ts', '.jsx', '.js'} and p.is_file():
            yield p, DOCS  # SPA is served from docs/index.html


def note_link_violations(pages=None) -> list[str]:
    bad = []
    for page, base in (pages if pages is not None else _pages()):
        text = page.read_text(encoding='utf-8', errors='replace')
        for m in LINK_RE.finditer(text):
            url = m.group(1).strip()
            parts = urlsplit(url)
            path = parts.path
            if not NOTE_LIKE.search(path):
                continue
            rel = page.relative_to(ROOT) if ROOT in page.parents else page.name
            where = f'{rel} -> {url}'
            if parts.scheme or parts.netloc:
                bad.append(where + ' (absolute link to a note; link the docs/notes/ page instead)')
                continue
            if not path:
                continue
            target = (base / path).resolve()
            if NOTES.resolve() not in target.parents:
                bad.append(where + ' (note outside docs/notes/)')
            elif not target.exists():
                bad.append(where + ' (missing note; mark it pending instead of linking)')
    return bad


def test_pages_only_link_notes_inside_docs_notes():
    bad = note_link_violations()
    assert not bad, 'Note links outside docs/notes/ or to missing notes:\n' + '\n'.join(bad)


def test_checker_flags_outside_and_missing_notes(tmp_path):
    page = tmp_path / 'p.html'
    page.write_text(
        '<a href="../cio_book_shortlist/CIO_NOTE_x.md">x</a>'
        '<a href="notes/does_not_exist.html">y</a>'
        '<a href="https://github.com/o/r/blob/main/QUANT_NOTE_y.md">z</a>'
        '<span data-pending-note="notes/book2_reframe.md">pending</span>',
        encoding='utf-8',
    )
    bad = note_link_violations([(page, DOCS)])
    assert len(bad) == 3, bad


def test_docs_notes_holds_only_registered_reader_notes():
    registry = {slug: status for slug, _, status, _ in _notes_registry()}
    for p in sorted(NOTES.iterdir()):
        assert not WORKING_NAME.match(p.name), f'working file copied into docs/notes: {p.name}'
        assert p.stem in registry, f'unregistered note in docs/notes: {p.name}'
    for slug, status in registry.items():
        if status == 'published':
            assert (NOTES / f'{slug}.md').exists() and (NOTES / f'{slug}.html').exists(), slug


def test_pending_notes_are_marked_not_linked():
    methods_index = (DOCS / 'methods' / 'index.html').read_text(encoding='utf-8')
    for slug, _, status, _ in _notes_registry():
        if status == 'pending':
            assert f'data-pending-note="notes/{slug}.md"' in methods_index, slug
            assert f'href="../notes/{slug}' not in methods_index, slug


# Quant's note is published byte-identical to /workspace/investments/published_notes/.
LW2008_NOTE_SHA256 = 'c82072257fdaa8d5c40f7a691ed92b7d890c7d86913c3129d91cd28b41f26ee4'  # re-pinned 2026-10-01: VT -> vol-target backbone wording


def test_quant_lw2008_note_published_unchanged():
    import hashlib
    path = NOTES / 'book2_lw2008_drawdowns.md'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == LW2008_NOTE_SHA256
    index = (DOCS / 'methods' / 'index.html').read_text(encoding='utf-8')
    assert 'href="../notes/book2_lw2008_drawdowns.html"' in index
    assert 'data-pending-note="notes/book2_lw2008_drawdowns.md"' not in index


# CIO's reframe note is published byte-identical to /workspace/investments/published_notes/.
REFRAME_NOTE_SHA256 = 'e32ea4f0b8c05d97bc5aefbf09cc423e388fe96a5c8384f8818b6429e971c7b3'  # re-pinned 2026-10-01: CIO revision (vol-target backbone)


def test_cio_reframe_note_published_unchanged():
    import hashlib
    path = NOTES / 'book2_reframe.md'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == REFRAME_NOTE_SHA256
    index = (DOCS / 'methods' / 'index.html').read_text(encoding='utf-8')
    assert 'href="../notes/book2_reframe.html"' in index
    assert 'data-pending-note="notes/book2_reframe.md"' not in index
