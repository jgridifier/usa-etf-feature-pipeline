"""Every built page lays out at 375px with no horizontal scroll (PM re-test of a221d3c, items 2-5).

Renders the committed docs/ in headless Chrome with a 375x812 mobile viewport (tests/tools/cdp375.mjs)
and checks, per page:
  * document scrollWidth <= 375 (Addendum 3's 64-character hashes used to push it to 576px);
  * the open header menu's links are at least 44px tall, and so is the toggle;
  * nothing is fetched from an outside host (fonts are self-hosted);
and on the hub leaderboard scatter: no two point labels overlap (Spectral RP / EPO, RR-ERC / Regime dual)
and a tap on the Backbone dot, which sits on the dashed zero line, opens its tooltip. On the Schur page
the head-to-head power chart shows the full "LW MinVar (capped QP)" and "Equal weight (capped)" labels.

Like test_live_figures, it fails in CI when Chrome or node is missing and skips locally.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
DRIVER = ROOT / 'tests' / 'tools' / 'cdp375.mjs'
PINNED_NO_SHELL = {'methods/stage2_demiguel.html'}  # Quant's teaching note: byte-for-byte, no lab header
PAGES = sorted(str(p.relative_to(DOCS)) for p in DOCS.rglob('*.html'))

PROBE = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const res = {scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth};
  const host = location.host;
  res.outside = performance.getEntriesByType('resource').map(e => e.name)
    .filter(u => { try { return new URL(u).host !== host && !u.startsWith('data:'); } catch (e) { return false; } });
  let toggle = document.querySelector('.nav-toggle') ||
    [...document.querySelectorAll('button')].find(b => /menu/i.test(b.getAttribute('aria-label') || ''));
  if (toggle) {
    const tb = toggle.getBoundingClientRect();
    res.toggle = [Math.round(tb.width), Math.round(tb.height)];
    toggle.click(); await sleep(400);
    const links = [...document.querySelectorAll('.site-nav a, nav [aria-label="Mobile navigation"] a, nav div[aria-label] a')]
      .filter(a => a.offsetParent && a.getBoundingClientRect().height > 0);
    res.menu = links.map(a => [a.textContent.trim(), Math.round(a.getBoundingClientRect().height)]);
    res.menuScrollWidth = document.documentElement.scrollWidth;
    toggle = document.querySelector('.nav-toggle') ||
      [...document.querySelectorAll('button')].find(b => /menu/i.test(b.getAttribute('aria-label') || ''));
    toggle.click(); await sleep(200);
  }
  const rectOf = e => { const b = e.getBoundingRect().clone(); b.applyTransform(e.getComputedTransform()); return [b.x, b.y, b.width, b.height]; };
  const sc = document.querySelector('#chart-scatter');
  if (sc && window.echarts) {
    sc.open = true; sc.dispatchEvent(new Event('toggle')); await sleep(1500);
    const el = sc.querySelector('[data-hub-chart]'); const chart = el && echarts.getInstanceByDom(el);
    if (chart) {
      const data = chart.getOption().series[0].data; const names = new Set(data.map(d => d.name));
      const labels = chart.getZr().storage.getDisplayList()
        .filter(e => e.style && names.has(e.style.text) && !e.invisible && !e.ignore).map(e => [e.style.text, rectOf(e)]);
      const ov = [];
      for (let a = 0; a < labels.length; a++) for (let b = a + 1; b < labels.length; b++) {
        const p = labels[a][1], q = labels[b][1];
        if (p[0] < q[0] + q[2] && q[0] < p[0] + p[2] && p[1] < q[1] + q[3] && q[1] < p[1] + p[3]) ov.push([labels[a][0], labels[b][0]]);
      }
      res.scatter = {labels: labels.map(l => l[0]), overlaps: ov};
      const bb = data.find(d => d.name === 'Backbone');
      if (bb) {
        const [x, y] = chart.convertToPixel({seriesIndex: 0}, bb.value);
        chart.getZr().handler.dispatch('click', {offsetX: x, offsetY: y, zrX: x, zrY: y});
        chart.getZr().handler.dispatch('mousemove', {offsetX: x, offsetY: y, zrX: x, zrY: y});
        await sleep(600);
        const tip = [...el.querySelectorAll('div')].find(d => /z-index:\s*9999999/.test(d.getAttribute('style') || '')
          && getComputedStyle(d).display !== 'none' && getComputedStyle(d).visibility !== 'hidden' && getComputedStyle(d).opacity !== '0');
        res.scatter.backboneTip = tip ? tip.textContent : null;
      }
    }
  }
  if (location.pathname.endsWith('/results/schur.html') && window.echarts) {
    document.querySelectorAll('details').forEach(d => { d.open = true; d.dispatchEvent(new Event('toggle')); });
    await sleep(2000);
    res.axisText = [];
    document.querySelectorAll('[data-hub-chart]').forEach(el => {
      const c = echarts.getInstanceByDom(el); if (!c) return;
      const W = el.getBoundingClientRect().width;
      const texts = c.getZr().storage.getDisplayList().filter(e => e.style && typeof e.style.text === 'string' && e.style.text);
      if (!texts.some(e => /capped/.test(e.style.text))) return;
      // the chart naming the capped nulls: every text element, with whether it sits fully inside the chart
      texts.forEach(e => { const r = rectOf(e); res.axisText.push([e.style.text, r[0] >= 0 && r[0] + r[2] <= W + 1]); });
    });
  }
  return res;
})()
"""


def _which(*names):
    for n in names:
        if n and shutil.which(n):
            return shutil.which(n)
    return None


@pytest.fixture(scope='module')
def rendered():
    chrome = _which(os.environ.get('CHROME'), 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
    node = _which('node')
    if chrome is None or node is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome and node are required in CI for the 375px layout check')
        pytest.skip('no Chrome/node available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}/'
    try:
        cfg = {'urls': [base + p for p in PAGES], 'expression': PROBE, 'settle_ms': 1200}
        out = subprocess.run([node, '--experimental-websocket', str(DRIVER), chrome, json.dumps(cfg)],
                             capture_output=True, text=True, timeout=600, check=True).stdout
    finally:
        server.shutdown()
    raw = json.loads(out.strip().splitlines()[-1])
    return {u[len(base):]: v for u, v in raw.items()}


def test_every_page_was_rendered(rendered):
    assert 'methods/stage2_addendum3.html' in PAGES and 'methods/results/index.html' in PAGES
    assert set(rendered) == set(PAGES)
    errs = {p: v for p, v in rendered.items() if not isinstance(v, dict) or 'error' in v}
    assert not errs, errs


@pytest.mark.parametrize('page', PAGES)
def test_no_horizontal_scroll_at_375(rendered, page):
    r = rendered[page]
    assert r['innerWidth'] == 375, (page, r['innerWidth'])
    assert r['scrollWidth'] <= 375, (page, r['scrollWidth'])
    if 'menuScrollWidth' in r:
        assert r['menuScrollWidth'] <= 375, (page, r['menuScrollWidth'])


@pytest.mark.parametrize('page', [p for p in PAGES if p not in PINNED_NO_SHELL])
def test_open_menu_links_are_44px_tap_targets(rendered, page):
    r = rendered[page]
    assert r.get('toggle'), f'{page}: no menu toggle at 375px'
    assert min(r['toggle']) >= 44, (page, r['toggle'])
    assert len(r['menu']) >= 4, (page, r['menu'])
    short = [m for m in r['menu'] if m[1] < 44]
    assert not short, (page, short)


@pytest.mark.parametrize('page', PAGES)
def test_nothing_loads_from_an_outside_host(rendered, page):
    assert rendered[page]['outside'] == [], (page, rendered[page]['outside'])


def test_scatter_labels_do_not_overlap_and_backbone_dot_has_a_tooltip(rendered):
    s = rendered['methods/results/index.html'].get('scatter')
    assert s, 'scatter chart did not render'
    assert {'Spectral RP', 'EPO', 'RR-ERC', 'Regime dual', 'Backbone'} <= set(s['labels']), s['labels']
    assert s['overlaps'] == [], s['overlaps']
    assert s['backboneTip'] and 'Backbone' in s['backboneTip'] and 'CAGR diff' in s['backboneTip'], s['backboneTip']


def test_schur_power_chart_shows_full_capped_labels(rendered):
    texts = rendered['methods/results/schur.html'].get('axisText') or []
    joined = ' '.join(' '.join(t.split()) for t, _ in texts)
    assert 'LW MinVar' in joined and 'Equal weight' in joined and joined.count('(capped') >= 2, texts
    assert all(inside for _, inside in texts), texts
