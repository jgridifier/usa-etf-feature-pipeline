// Headless-Chrome check at a phone viewport (375x812, mobile): node --experimental-websocket cdp375.mjs <chrome> <json>
// <json> = {"urls": [...], "expression": "<JS returning a JSON-able value>", "shots": {"url": "out.png"}}
// Prints {url: value} as JSON. Used by tests/test_mobile_375.py and to take the PM screenshots.
import {spawn} from 'node:child_process';
import {mkdtempSync, writeFileSync} from 'node:fs';
const [chromePath, cfgText] = process.argv.slice(2);
const cfg = JSON.parse(cfgText);
const dir = mkdtempSync('/tmp/cdp375-');
const chrome = spawn(chromePath, ['--headless=new', '--no-sandbox', '--disable-gpu', '--remote-debugging-port=0',
  `--user-data-dir=${dir}`, '--window-size=375,812', 'about:blank'], {stdio: ['ignore', 'ignore', 'pipe']});
const kill = () => { try { chrome.kill('SIGKILL'); } catch {} };
setTimeout(() => { kill(); console.error('timeout'); process.exit(2); }, 240000);
const ws0 = await new Promise((res, rej) => { let b = ''; chrome.stderr.on('data', d => { b += d; const m = b.match(/ws:\/\/\S+/); if (m) res(m[0]); }); setTimeout(() => rej(new Error('no devtools url')), 60000); });
const port = new URL(ws0).port;
const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(t => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map(); let loaded = false;
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method === 'Page.loadEventFired') loaded = true; };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({id: i, method, params})); });
await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', {width: 375, height: 812, deviceScaleFactor: 2, mobile: true});
const out = {};
for (const url of cfg.urls) {
  loaded = false;
  await send('Page.navigate', {url});
  for (let t = 0; t < 300 && !loaded; t++) await new Promise(r => setTimeout(r, 100));
  await new Promise(r => setTimeout(r, cfg.settle_ms ?? 2500));
  const r = await send('Runtime.evaluate', {expression: cfg.expression, returnByValue: true, awaitPromise: true});
  out[url] = r.result?.exceptionDetails ? {error: r.result.exceptionDetails.text} : r.result?.result?.value;
  const shot = (cfg.shots || {})[url];
  if (shot) { const s = await send('Page.captureScreenshot', {format: 'png'}); writeFileSync(shot, Buffer.from(s.result.data, 'base64')); }
}
console.log(JSON.stringify(out));
ws.close(); kill(); process.exit(0);
