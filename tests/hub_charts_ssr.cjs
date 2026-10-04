// SVG goldens exercise the shipped bundle at phone and desktop widths, offline.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
require(path.join(root, 'docs/assets/vendor/echarts-6.1.0.custom.min.js'));
vm.runInThisContext(fs.readFileSync(path.join(root, 'docs/assets/hub-theme.js'), 'utf8'));
const palette = new Set(['1a1410','3f434a','6b7079','c3c7cf','f4f5f7','1c2d6b',
  '0e1a42','858a94','5b6ba8','b8bcc4','ffffff','000000']);
function checkColors(svg) {
  for (const match of svg.matchAll(/(?:fill|stroke)=["']([^"']+)["']/g)) {
    const color = match[1].toLowerCase();
    if (color === 'none' || color === 'transparent' || color.startsWith('url(')) continue;
    let hex;
    if (/^#[\da-f]{3}$/.test(color)) hex = color.slice(1).split('').map(c => c+c).join('');
    else if (/^#[\da-f]{6}$/.test(color)) hex = color.slice(1);
    else if (/^rgb\(/.test(color)) hex = color.match(/[\d.]+/g).map(n => Number(n).toString(16).padStart(2, '0')).join('');
    else assert.fail(`Unexpected SVG color: ${color}`);
    assert(palette.has(hex) || hex.slice(0,2) === hex.slice(2,4) && hex.slice(2,4) === hex.slice(4,6), color);
  }
}
// ECharts uses process-global IDs; normalize them without changing geometry or paint.
function normalize(svg) {
  return svg.replace(/zr\d+/g, 'zr0');
}
try {
  const directory = path.join(__dirname, 'data/hub_chart_snapshots');
  for (const file of fs.readdirSync(directory).filter(f => f.endsWith('.json')).sort()) {
    for (const width of [375, 720]) {
      const option = JSON.parse(fs.readFileSync(path.join(directory, file), 'utf8'));
      delete option._hub;
      const chart = echarts.init(null, 'hub', {renderer: 'svg', ssr: true, width, height: 240});
      let svg;
      try { chart.setOption(option); svg = normalize(chart.renderToSVGString()); }
      finally { chart.dispose(); }
      assert(svg.includes('<svg') && svg.includes('<path'), `${file}: empty SVG`);
      checkColors(svg);
      const golden = path.join(directory, file.replace('.json', `-${width}.svg`));
      if (process.argv.includes('--write')) fs.writeFileSync(golden, svg);
      else assert.equal(svg, fs.readFileSync(golden, 'utf8'), `${file} at ${width}px differs`);
    }
  }
  console.log('Hub chart SSR: 10 SVG snapshots passed');
  process.exit(0);
} catch (error) { console.error(error); process.exit(1); }
