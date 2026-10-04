// A tiny DOM double checks lazy lifecycle and JSON formatting without dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../docs/assets/hub-charts.js'), 'utf8');
const outer = {tagName: 'DETAILS', open: false, parentElement: null, listeners: [],
  addEventListener(type, callback) { assert.equal(type, 'toggle'); this.listeners.push(callback); }};
const inner = {...outer, listeners: [], parentElement: outer};
const element = {parentElement: inner, dataset: {hubChart: 'fixture'}};
let count = 0, resizes = 0, observed = 0, option;
const listeners = [];
const context = vm.createContext({Intl,
  document: {readyState: 'complete', querySelectorAll: () => [element],
    getElementById: () => ({textContent: JSON.stringify({
      _hub: {percent: true, decimals: 2}, tooltip: {triggerOn: 'mousemove|click'},
      xAxis: {type: 'category'}, yAxis: {type: 'value'}, series: [],
    })})},
  window: {addEventListener: (event, callback) => listeners.push(callback)},
  ResizeObserver: class { constructor(callback) { this.callback = callback; }
    observe(target) { assert.equal(target, element); observed++; this.callback(); } },
  echarts: {getInstanceByDom: () => count > 0,
    init(target, theme, config) {
      assert.equal(target, element); assert.equal(theme, 'hub'); assert.equal(config.renderer, 'svg');
      count++; return {setOption: value => { option = value; }, resize: () => resizes++};
    }},
});
vm.runInContext(source, context);
vm.runInContext(source, context);
assert.equal(count, 0);
assert.equal(inner.listeners.length, 1);
inner.open = true; inner.listeners[0](); assert.equal(count, 0);
outer.open = true; outer.listeners[0](); assert.equal(count, 1);
assert(!('_hub' in option));
assert.equal(option.tooltip.valueFormatter(0.125), '12.50%');
assert.equal(option.tooltip.valueFormatter(null), '—');
assert.equal(option.tooltip.triggerOn, 'mousemove|click');
assert.equal(option.yAxis.axisLabel.formatter(0.1), '10.00%');
assert.equal(observed, 1);
listeners[0](); inner.listeners[0](); vm.runInContext(source, context);
assert.equal(count, 1); assert.equal(resizes, 3);
console.log('Hub chart runtime: lazy init, formatting, resize and idempotence passed');
