// JSON options stay portable; browser-only number formatting is installed here.
(() => {
  if (globalThis.hubCharts) { globalThis.hubCharts.scan(); return; }
  const pending = new WeakSet();
  function scan() {
    document.querySelectorAll('[data-hub-chart]').forEach(element => {
      if (pending.has(element) || globalThis.echarts.getInstanceByDom(element)) return;
      pending.add(element);
      const ancestors = [];
      for (let parent = element.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') ancestors.push(parent);
      }
      let chart;
      function start() {
        if (ancestors.some(details => !details.open)) return;
        if (chart) { chart.resize(); return; }
        const source = document.getElementById(element.dataset.hubChart);
        const option = JSON.parse(source.textContent);
        const hints = option._hub || {};
        delete option._hub;
        const number = new Intl.NumberFormat('en-US', {
          style: hints.percent ? 'percent' : 'decimal',
          minimumFractionDigits: hints.decimals ?? 2,
          maximumFractionDigits: hints.decimals ?? 2,
        });
        const format = value => value == null || value === '-' ? '—' :
          (typeof value === 'number' ? number.format(value) : value);
        const month = value => {
          const index = Math.round(value);
          return `${Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, '0')}`;
        };
        option.tooltip = {...option.tooltip, valueFormatter: format};
        for (const key of ['xAxis', 'yAxis']) {
          for (const axis of [].concat(option[key] || [])) {
            if (axis.type !== 'category') axis.axisLabel = {...axis.axisLabel, formatter: format};
          }
        }
        if (hints.monthIndex) {
          option.xAxis.axisLabel.formatter = month;
          option.xAxis.minInterval = 12;
          option.tooltip.formatter = point => {
            const row = hints.table.rows[point.dataIndex];
            if (!row) return '';
            const node = document.createElement('div');
            node.textContent = `${row[0]}: ${row[1]} to ${row[2]}`;
            return node;
          };
        }
        chart = globalThis.echarts.init(element, 'hub', {renderer: 'svg'});
        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
        if (typeof ResizeObserver !== 'undefined') {
          const observer = new ResizeObserver(() => chart.resize());
          observer.observe(element);
        }
      }
      ancestors.forEach(details => details.addEventListener('toggle', start));
      start();
    });
  }
  globalThis.hubCharts = {scan};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan);
  else scan();
})();
