"""Display labels for the vol-target backbone ("VT" in internal names).

Jared-facing text says "vol-target backbone" in prose and "Backbone" in tables,
cards, legends and tooltips. Internal ids, column names and JSON keys keep "vt".
VT the ETF ticker (Vanguard Total World) is never passed through these helpers.
Mirrored in apps/pages/src/lib/labels.ts for the frozen archive_verdicts.json,
which is relabelled at display time and left unchanged on disk.
"""
from __future__ import annotations

import re

APOS = r"(&rsquo;|’|')"
PROSE_RULES = [
    (re.compile(r"Book-2" + APOS + r"s VT backbone"), r"Book 2\1s vol-target backbone"),
    (re.compile(r"Book-2 VT backbone"), "vol-target backbone"),
    (re.compile(r"Book-2 VT\b"), "vol-target backbone"),
    (re.compile(r"\bVT backbone"), "vol-target backbone"),
    (re.compile(r"\bVT ×"), "vol-target backbone ×"),
    (re.compile(r"\bVT null\b"), "vol-target backbone null"),
    (re.compile(r"\bVT" + APOS + r"s\b"), r"the vol-target backbone\1s"),
    (re.compile(r"\b(tracked|for|vs|versus|than|against) VT\b"), r"\1 the vol-target backbone"),
    (re.compile(r"\(VT\)"), "(Backbone)"),
]
LABEL_RULES = [
    (re.compile(r"Book-2 VT( backbone)?\b"), "Backbone"),
    (re.compile(r"\bVT backbone\b"), "Backbone"),
    (re.compile(r"\bVT\b"), "Backbone"),
]


def _apply(rules, text: str) -> str:
    for pat, rep in rules:
        text = pat.sub(rep, text)
    return text


def relabel_prose(text: str) -> str:
    return _apply(PROSE_RULES, text)


def relabel_label(text: str) -> str:
    return _apply(LABEL_RULES, text)


ARCHIVE_LABEL_FIELDS = {'name', 'null', 'label'}


def relabel_archive(obj, key: str | None = None):
    """Relabel display text in archive_verdicts.json; ids, hrefs and keys untouched."""
    if isinstance(obj, dict):
        return {k: (v if k in {'id', 'href', 'method_page', 'badge'} else relabel_archive(v, k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [relabel_archive(v, key) for v in obj]
    if isinstance(obj, str):
        return relabel_label(obj) if key in ARCHIVE_LABEL_FIELDS else relabel_prose(obj)
    return obj
