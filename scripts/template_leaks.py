"""Find unrendered template placeholders in the visible text of a built HTML page.

A leak is a '{' followed by a Python identifier and then '(', '[' or '.' (an f-string / str.format field such as
{row.cagr} or {fmt(x)}), or a bare {name} with no math context. Text inside <script>, <style>, <pre>, <code>,
<math>, elements whose class names math / katex / MathJax, and TeX delimiters \\( \\), \\[ \\], $$ $$ is exempt, as
is a brace that follows '_', '^' or a TeX command (f_{t-1}, x^{2}, \\frac{a}{b}). Literal formulas such as
f_{t−1} and {0.5, 1} are not identifiers after '{' and never match.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

SKIP_TAGS = {'script', 'style', 'pre', 'code', 'math', 'template', 'noscript'}
MATH_CLASS = re.compile(r'(?:^|[\s-])(math|katex|mathjax|MathJax)(?:$|[\s-])', re.I)
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
TEX = re.compile(r'\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$', re.S)
FIELD = re.compile(r'\{[A-Za-z_][A-Za-z0-9_]*[\(\[.]')
BARE = re.compile(r'\{[A-Za-z_][A-Za-z0-9_]*\}')
MATH_BEFORE = re.compile(r'(?:[_^]|\\[A-Za-z]+(?:\{[^{}]*\})*)\s*$')   # f_{, x^{, \frac{a}{


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []      # per open element: does it (or an ancestor) exempt its text?
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        skip = (bool(self.stack) and self.stack[-1]) or tag in SKIP_TAGS or bool(MATH_CLASS.search(a.get('class') or ''))
        self.stack.append(skip)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack:
            return
        self.stack.pop()

    def handle_data(self, data):
        if not (self.stack and self.stack[-1]):
            self.parts.append(data)


def visible_text(html: str) -> str:
    p = _Visible()
    p.feed(html)
    p.close()
    return TEX.sub(' ', ''.join(p.parts))


def leaks(html: str) -> list[str]:
    text = visible_text(html)
    found = []
    for rx in (FIELD, BARE):
        for m in rx.finditer(text):
            if MATH_BEFORE.search(text[max(0, m.start() - 40):m.start()]):
                continue
            found.append(text[max(0, m.start() - 20):m.end() + 20].replace('\n', ' '))
    return found
