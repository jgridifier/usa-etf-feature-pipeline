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


def test_stage2_wrap_is_published_verbatim_at_its_pinned_hash():
    import hashlib
    spec = importlib.util.spec_from_file_location('build_notes', ROOT / 'scripts' / 'build_notes.py')
    bn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bn)
    pin = '2efdf27b345d152cdb111406ea10dd4167617d0f47b21591bf68308063814491'
    assert bn.NOTE_SHA256['stage2_wrap'] == pin
    md = ROOT / 'docs/notes/stage2_wrap.md'
    assert hashlib.sha256(md.read_bytes()).hexdigest() == pin
    assert ('stage2_wrap', 'CIO note: stage 2 wrap-up (Oct 2026)', 'published', '') in bn.NOTES
    html = (ROOT / 'docs/notes/stage2_wrap.html').read_text(encoding='utf-8')
    assert 'Stage 2 wrap-up: nothing beat the static core' in html


def test_stage2_wrap_backbone_cagr_banner_is_dated_and_from_backbone_json():
    """The pinned wrap-up note prints the Backbone CAGR as 15.1%; the true figure is 15.0016% (68m 2021-02..2026-09).
    The note's bytes stay pinned, so a dated build-time lab note carries the correction, every figure from
    data/processed/hub/subjects/backbone.json (CoS, 2026-10-04)."""
    import json
    import re
    d = json.loads((ROOT / 'data/processed/hub/subjects/backbone.json').read_text(encoding='utf-8'))
    own, core = d['own'], d['vs_core']['own_window']['b']
    assert (own['n'], own['start'], own['end']) == (68, '2021-02', '2026-09')
    assert abs(own['cagr'] - 0.150016) < 1e-6
    html = (ROOT / 'docs/notes/stage2_wrap.html').read_text(encoding='utf-8')
    m = re.search(r'<p class="callout note-banner" role="note">(.*?)</p>', html, re.S)
    assert m, 'no banner on the wrap-up note'
    text = m.group(1).replace('&#x27;', "'")
    assert text.startswith('Lab note, 2026-10-04:')
    want = (f"Over the 68 months 2021-02 to 2026-09, the backbone and the core are level on CAGR "
            f"({100 * own['cagr']:.2f}% vs {100 * core['cagr']:.2f}%), and the backbone's edge is lower risk "
            f"(Sharpe {own['sharpe_exbil']:.2f} vs {core['sharpe_exbil']:.2f}), not higher return.")
    assert want in text, text
    assert '15.00% vs 14.96%' in text and 'Sharpe 0.86 vs 0.77' in text and 'No verdict changes' in text
    md = (ROOT / 'docs/notes/stage2_wrap.md').read_text(encoding='utf-8')
    assert [l for l in md.splitlines() if '15.1%' in l] == ['| Backbone | 15.1% | 0.86 |']   # the only 15.1%
    src = (ROOT / 'scripts/build_notes.py').read_text(encoding='utf-8')
    for lit in ('15.00', '14.96', '0.86 vs', '0.77'):
        assert lit not in src, lit                          # computed, not typed in


def test_banner_follows_the_data(monkeypatch, tmp_path):
    import json
    spec = importlib.util.spec_from_file_location('build_notes', ROOT / 'scripts' / 'build_notes.py')
    bn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bn)
    d = json.loads(bn.BACKBONE_JSON.read_text(encoding='utf-8'))
    d['own']['cagr'] = 0.2
    p = tmp_path / 'backbone.json'
    p.write_text(json.dumps(d))
    monkeypatch.setattr(bn, 'BACKBONE_JSON', p)
    assert 'level on CAGR (20.00% vs' in bn.banner_text('stage2_wrap')
