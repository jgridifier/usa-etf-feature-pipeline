/* USA ETF Lab charts — Apache ECharts CDN. Loads JSON snapshots from docs/data/. */
(function () {
  'use strict';

  var PRIMARY = '#0052ff';
  var INK = '#0a0b0d';
  var BODY = '#5b616e';
  var UP = '#05b169';
  var DOWN = '#cf202f';
  var HAIR = '#dee1e6';
  var SOFT = '#f7f7f7';

  function dataUrl(name) {
    var base = document.body.getAttribute('data-base') || '';
    // Resolve relative to page: books/runs at docs root use data/; methods would use ../data/
    if (!base) {
      var scripts = document.getElementsByTagName('script');
      for (var i = 0; i < scripts.length; i++) {
        var src = scripts[i].src || '';
        if (src.indexOf('assets/app.js') !== -1) {
          base = src.replace(/assets\/app\.js.*$/, '');
          break;
        }
      }
    }
    return base + 'data/' + name;
  }

  function fetchJson(name) {
    return fetch(dataUrl(name), { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error('Failed to load ' + name + ' (' + r.status + ')');
      return r.json();
    });
  }

  function baseChartOption() {
    return {
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: BODY },
      grid: { left: 48, right: 24, top: 48, bottom: 48 },
      tooltip: { trigger: 'axis' },
      legend: { top: 8, textStyle: { color: BODY } },
      color: [PRIMARY, INK, UP, DOWN],
    };
  }

  function pct(x) {
    if (x == null || isNaN(x)) return '—';
    return (100 * x).toFixed(1) + '%';
  }
  function num(x, d) {
    if (x == null || isNaN(x)) return '—';
    return Number(x).toFixed(d == null ? 2 : d);
  }

  function initEquity(el, payload) {
    var chart = echarts.init(el);
    var opt = baseChartOption();
    opt.title = { text: 'Cumulative wealth (OOS)', left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: INK } };
    opt.xAxis = { type: 'category', data: payload.dates, axisLabel: { hideOverlap: true } };
    opt.yAxis = { type: 'value', scale: true, name: 'Wealth', nameTextStyle: { color: BODY } };
    opt.series = [
      { name: 'Vol-target (Book 2)', type: 'line', showSymbol: false, data: payload.equity.vol_target_option_a, lineStyle: { width: 2 } },
      { name: 'Static Option A', type: 'line', showSymbol: false, data: payload.equity.static_option_a, lineStyle: { width: 2 } },
    ];
    chart.setOption(opt);
    return chart;
  }

  function initDrawdown(el, payload) {
    var chart = echarts.init(el);
    var opt = baseChartOption();
    opt.title = {
      text: 'Drawdown · MaxDD vt ' + pct(payload.max_dd && payload.max_dd.vol_target_option_a) +
        ' vs A ' + pct(payload.max_dd && payload.max_dd.static_option_a),
      left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: INK },
    };
    opt.xAxis = { type: 'category', data: payload.dates, axisLabel: { hideOverlap: true } };
    opt.yAxis = {
      type: 'value',
      axisLabel: { formatter: function (v) { return (100 * v).toFixed(0) + '%'; } },
    };
    opt.tooltip = {
      trigger: 'axis',
      valueFormatter: function (v) { return pct(v); },
    };
    opt.series = [
      { name: 'Vol-target (Book 2)', type: 'line', showSymbol: false, areaStyle: { opacity: 0.08 }, data: payload.drawdown.vol_target_option_a },
      { name: 'Static Option A', type: 'line', showSymbol: false, areaStyle: { opacity: 0.05 }, data: payload.drawdown.static_option_a },
    ];
    chart.setOption(opt);
    return chart;
  }

  function initFt(el, payload) {
    var chart = echarts.init(el);
    var opt = baseChartOption();
    opt.title = { text: 'f_t and BIL residual weight', left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: INK } };
    opt.legend = { top: 8, data: ['f_t', 'w_BIL'] };
    opt.xAxis = { type: 'category', data: payload.dates, axisLabel: { hideOverlap: true } };
    opt.yAxis = [
      { type: 'value', name: 'f_t', min: 0, max: 1.05 },
      { type: 'value', name: 'w_BIL', min: 0, max: 1, axisLabel: { formatter: function (v) { return (100 * v).toFixed(0) + '%'; } } },
    ];
    opt.series = [
      { name: 'f_t', type: 'line', showSymbol: false, data: payload.f, yAxisIndex: 0 },
      { name: 'w_BIL', type: 'line', showSymbol: false, data: payload.w_BIL, yAxisIndex: 1, lineStyle: { type: 'dashed' } },
    ];
    chart.setOption(opt);
    return chart;
  }

  function initWeights(el, bookKey, payload) {
    var book = payload.books && payload.books[bookKey];
    if (!book) {
      el.innerHTML = '<div class="placeholder"><strong>No weights</strong> for ' + bookKey + '.</div>';
      return null;
    }
    var tickers = Object.keys(book.weights);
    var values = tickers.map(function (t) { return book.weights[t]; });
    var chart = echarts.init(el);
    var opt = baseChartOption();
    opt.grid = { left: 48, right: 16, top: 28, bottom: 32 };
    opt.tooltip = {
      trigger: 'axis',
      valueFormatter: function (v) { return pct(v); },
    };
    opt.xAxis = { type: 'category', data: tickers };
    opt.yAxis = { type: 'value', max: 1, axisLabel: { formatter: function (v) { return (100 * v).toFixed(0) + '%'; } } };
    opt.series = [{
      type: 'bar',
      data: values,
      barWidth: '48%',
      itemStyle: { color: PRIMARY, borderRadius: [8, 8, 0, 0] },
    }];
    if (book.asof) {
      opt.title = { text: 'as-of ' + String(book.asof).slice(0, 10) + (book.f != null ? ' · f=' + num(book.f) : ''), left: 0, top: 0, textStyle: { fontSize: 12, color: BODY, fontWeight: 500 } };
    }
    chart.setOption(opt);
    return chart;
  }

  function renderXsd(el, payload) {
    if (!payload) {
      el.innerHTML = '<div class="placeholder"><strong>No series yet</strong> — XSD diagnostics missing.</div>';
      return null;
    }
    if (payload.available && payload.dates && payload.dates.length) {
      var chart = echarts.init(el);
      var opt = baseChartOption();
      opt.title = { text: 'XSD ON/OFF timeline', left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: INK } };
      opt.xAxis = { type: 'category', data: payload.dates, axisLabel: { hideOverlap: true } };
      opt.yAxis = { type: 'value', min: 0, max: 1, interval: 1, axisLabel: { formatter: function (v) { return v ? 'ON' : 'OFF'; } } };
      opt.series = [{
        name: 'xsd_on',
        type: 'line',
        step: 'end',
        data: payload.xsd_on,
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
      }];
      chart.setOption(opt);
      return chart;
    }
    var snap = payload.snapshot;
    var status = 'unknown';
    var pill = 'warn';
    if (snap && snap.on === true) { status = 'ON'; pill = 'on'; }
    else if (snap && snap.on === false) { status = 'OFF'; pill = 'off'; }
    var date = snap && snap.date ? String(snap.date).slice(0, 10) : '—';
    el.innerHTML =
      '<div class="placeholder">' +
      '<p><span class="pill ' + pill + '">XSD ' + status + '</span> · snapshot ' + date + '</p>' +
      '<p><strong>No historical series yet.</strong> ' + (payload.note || '') + '</p>' +
      '<p class="metric-sub">Source: ' + (payload.source || 'strategy_diagnostics.csv') +
      ' · columns <code>on</code> / <code>rotate_on</code></p>' +
      '</div>';
    return null;
  }

  function renderComparison(host, payload) {
    if (!payload || !payload.rows || !payload.rows.length) {
      host.innerHTML = '<div class="placeholder">No comparison rows.</div>';
      return;
    }
    var head = ['Book', 'AnnReturn', 'AnnVol', 'MaxDD', 'Sharpe', 'NW t vs A', 'Stance'];
    var html = '<div class="table-scroll" tabindex="0" role="region" aria-label="Strategy comparison"><table><caption>Strategy comparison</caption><thead><tr>';
    head.forEach(function (h) { html += '<th scope="col">' + h + '</th>'; });
    html += '</tr></thead><tbody>';
    payload.rows.forEach(function (r) {
      var nw = r.NW_t_vs_option_a;
      var nwCell = nw == null ? '—' : num(nw);
      var ddClass = r.MaxDD < -0.2 ? 'down' : '';
      html += '<tr>' +
        '<td>' + r.label + '</td>' +
        '<td class="num">' + pct(r.AnnReturn) + '</td>' +
        '<td class="num">' + pct(r.AnnVol) + '</td>' +
        '<td class="num ' + ddClass + '">' + pct(r.MaxDD) + '</td>' +
        '<td class="num">' + num(r.Sharpe_rf0) + '</td>' +
        '<td class="num">' + nwCell + '</td>' +
        '<td>' + (r.stance || '') + '</td>' +
        '</tr>';
    });
    html += '</tbody></table></div>';
    host.innerHTML = html;
  }

  var charts = [];

  function boot() {
    if (typeof echarts === 'undefined') return;

    var equityEls = document.querySelectorAll('[data-chart="equity"]');
    var ddEls = document.querySelectorAll('[data-chart="drawdown"]');
    var ftEls = document.querySelectorAll('[data-chart="ft"]');
    var weightEls = document.querySelectorAll('[data-chart="weights"]');
    var xsdEls = document.querySelectorAll('[data-chart="xsd-timeline"]');
    var cmpHost = document.querySelector('[data-viz="comparison"]');

    var tasks = [];

    if (equityEls.length || ddEls.length) {
      tasks.push(fetchJson('viz_equity_drawdown.json').then(function (data) {
        equityEls.forEach(function (el) { charts.push(initEquity(el, data)); });
        ddEls.forEach(function (el) { charts.push(initDrawdown(el, data)); });
      }));
    }
    if (ftEls.length) {
      tasks.push(fetchJson('viz_ft_history.json').then(function (data) {
        ftEls.forEach(function (el) { charts.push(initFt(el, data)); });
      }));
    }
    if (weightEls.length) {
      tasks.push(fetchJson('viz_weights.json').then(function (data) {
        weightEls.forEach(function (el) {
          var c = initWeights(el, el.getAttribute('data-book'), data);
          if (c) charts.push(c);
        });
      }));
    }
    if (xsdEls.length) {
      tasks.push(fetchJson('viz_xsd_timeline.json').then(function (data) {
        xsdEls.forEach(function (el) {
          var c = renderXsd(el, data);
          if (c) charts.push(c);
        });
      }));
    }
    if (cmpHost) {
      tasks.push(fetchJson('viz_comparison.json').then(function (data) {
        renderComparison(cmpHost, data);
      }));
    }

    Promise.all(tasks).catch(function (err) {
      console.error(err);
    });

    window.addEventListener('resize', function () {
      charts.forEach(function (c) { if (c) c.resize(); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
