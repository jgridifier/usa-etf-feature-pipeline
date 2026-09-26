/* Static Growth-25 research explorer. Missing observations remain NaN internally. */
(function () {
  'use strict';
  const PRIMARY = '#1c2d6b', INK = '#1a1410', BODY = '#4a4238';
  const UP = '#1a5e33', DOWN = '#8b1a1a', HAIR = '#c4b89d', SOFT = '#ede8de';
  const EQUITIES = 'VOO,VTI,QQQ,QQQM,IJR,IWM,QUAL,USMV,VLUE,GSEW,IWP,IWO,IJK,IJT,VIOG,VXF,XSD,XBI,LOUP,GTEK,GINN,GVIP,BBC,VEA,EEM'.split(',');
  const finite = Number.isFinite, empty = n => new Float64Array(n).fill(NaN);
  const pct = x => finite(x) ? (100 * x).toFixed(2) + '%' : '—';
  const num = x => finite(x) ? x.toFixed(4) : '—';

  // RFC-style quoted cells, CRLF, and a possible UTF-8 BOM.
  function parseCSV(text) {
    const rows = []; let row = [], cell = '', quoted = false;
    text = text.replace(/^\uFEFF/, '');
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (c === '"') {
        if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
        else quoted = !quoted;
      } else if (!quoted && (c === ',' || c === '\n' || c === '\r')) {
        row.push(cell); cell = '';
        if (c !== ',') {
          if (row.some(v => v.trim())) rows.push(row);
          row = [];
          if (c === '\r' && text[i + 1] === '\n') i++;
        }
      } else cell += c;
    }
    if (quoted) throw new Error('Unclosed quoted CSV cell');
    row.push(cell);
    if (row.some(v => v.trim())) rows.push(row);
    if (!rows.length) throw new Error('Empty CSV');
    const header = rows.shift().map(x => x.trim());
    return rows.map(values => Object.fromEntries(header.map((key, i) => [key, (values[i] || '').trim()])));
  }
  function moments(values) {
    let n = 0, mean = 0, m2 = 0;
    for (const x of values) if (finite(x)) { n++; const d = x - mean; mean += d / n; m2 += d * (x - mean); }
    return { n, mean: n ? mean : NaN, sd: n > 1 ? Math.sqrt(Math.max(0, m2 / (n - 1))) : NaN };
  }
  function pairs(a, b, lag = 0, start = 0, end = a.length) {
    const x = [], y = [];
    for (let i = start; i < end; i++) {
      const j = i + lag;
      if (j >= start && j < end && finite(a[i]) && finite(b[j])) { x.push(a[i]); y.push(b[j]); }
    }
    return [x, y];
  }
  function pearson(x, y) {
    if (x.length < 2) return NaN;
    const mx = moments(x).mean, my = moments(y).mean;
    let xx = 0, yy = 0, xy = 0;
    for (let i = 0; i < x.length; i++) { const a = x[i] - mx, b = y[i] - my; xx += a*a; yy += b*b; xy += a*b; }
    return xx > 0 && yy > 0 ? Math.max(-1, Math.min(1, xy / Math.sqrt(xx * yy))) : NaN;
  }
  function ranks(x) {
    const order = Array.from(x, (_, i) => i).sort((a, b) => x[a] - x[b]), result = empty(x.length);
    for (let i = 0; i < order.length;) {
      let j = i + 1;
      while (j < order.length && x[order[j]] === x[order[i]]) j++;
      for (let k = i; k < j; k++) result[order[k]] = (i + j - 1) / 2 + 1;
      i = j;
    }
    return result;
  }
  function correlation(a, b, method = 'pearson', start = 0) {
    const [x, y] = pairs(a, b, 0, start);
    return { value: method === 'spearman' ? pearson(ranks(x), ranks(y)) : pearson(x, y), n: x.length };
  }
  function logReturns(prices) {
    const r = empty(prices.length);
    for (let i = 1; i < r.length; i++) if (prices[i] > 0 && prices[i-1] > 0) r[i] = Math.log(prices[i] / prices[i-1]);
    return r;
  }
  function riskFree(dates, bilPrices, tb3msText) {
    const rf = logReturns(bilPrices), source = Array(dates.length).fill(''), counts = new Map(), rates = new Map();
    dates.forEach(date=>{ const month = date.slice(0,7); counts.set(month,(counts.get(month)||0)+1); });
    let fallbackUnavailable = tb3msText == null;
    if (!fallbackUnavailable) try {
      const rows = parseCSV(tb3msText);
      if (!rows.length || !Object.hasOwn(rows[0],'observation_date') || !Object.hasOwn(rows[0],'TB3MS')) throw new Error('Invalid TB3MS CSV');
      rows.forEach(row=>{ const rate = row.TB3MS ? Number(row.TB3MS) : NaN; if (finite(rate) && rate > -1200) rates.set(row.observation_date.slice(0,7),rate); });
      fallbackUnavailable = !rates.size;
    } catch (_) { fallbackUnavailable = true; }
    const first = rf.findIndex(finite), boundary = first < 0 ? dates.length : first;
    dates.forEach((date,i)=>{
      if (finite(rf[i])) source[i] = 'BIL';
      else if (i < boundary && rates.has(date.slice(0,7))) {
        const month = date.slice(0,7);
        rf[i] = Math.log1p(rates.get(month)/1200)/counts.get(month); source[i] = 'TB3MS';
      }
    });
    return { rf, source, fallbackUnavailable };
  }
  function excessReturns(r, rf) {
    return Float64Array.from(r,(x,i)=>finite(x) && finite(rf[i]) ? x-rf[i] : NaN);
  }
  function excessStats(x, source) {
    const m = moments(x), fallback = x.reduce((n,v,i)=>n+Number(finite(v) && source[i] === 'TB3MS'),0);
    return { sharpe: m.sd > 0 ? Math.sqrt(252)*m.mean/m.sd : m.sd === 0 && m.mean === 0 ? 0 : NaN,
      fallbackShare: m.n ? fallback/m.n : NaN };
  }
  // O(n) trailing sufficient statistics; the window is dates, never compressed pairs.
  function rolling(a, b, window, zeroExcess = false) {
    const vol = empty(a.length), sharpe = empty(a.length), beta = empty(a.length), corr = empty(a.length), count = new Float64Array(a.length);
    let n = 0, sx = 0, sy = 0, xx = 0, yy = 0, xy = 0;
    function add(i, sign) {
      if (i < 0 || !finite(a[i]) || !finite(b[i])) return;
      const x = a[i], y = b[i]; n += sign; sx += sign*x; sy += sign*y; xx += sign*x*x; yy += sign*y*y; xy += sign*x*y;
    }
    for (let i = 0; i < a.length; i++) {
      add(i, 1); add(i-window, -1); count[i] = n;
      if (i < window-1 || n < 2) continue;
      const vx = Math.max(0, xx - sx*sx/n), vy = Math.max(0, yy - sy*sy/n), cov = xy - sx*sy/n;
      if (n === window) {
        const sd = Math.sqrt(vx/(n-1)); vol[i] = sd*Math.sqrt(252);
        if (sd > 0) sharpe[i] = Math.sqrt(252)*(sx/n)/sd;
        else if (zeroExcess && sx === 0) sharpe[i] = 0;
      }
      if (vy > 0) beta[i] = cov/vy;
      if (vx > 0 && vy > 0) corr[i] = Math.max(-1, Math.min(1, cov/Math.sqrt(vx*vy)));
    }
    return { vol, sharpe, beta, corr, count };
  }
  function wealthSeries(prices, returns) {
    const wealth = empty(prices.length), dd = empty(prices.length);
    let started = false, sum = 0, peak = 100;
    for (let i = 0; i < prices.length; i++) {
      if (!started && finite(prices[i])) { wealth[i] = 100; dd[i] = 0; started = true; }
      else if (finite(returns[i])) { sum += returns[i]; wealth[i] = 100*Math.exp(sum); peak = Math.max(peak, wealth[i]); dd[i] = wealth[i]/peak-1; }
    }
    return { wealth, dd };
  }
  function monthlyReturns(dates, wealth) {
    const ends = new Map();
    dates.forEach((date, i) => { ends.set(date.slice(0, 7), i); });
    const months = [...ends.keys()], result = [];
    // Exclude first partial month and final possibly incomplete month.
    for (let j = 1; j < months.length-1; j++) {
      const prev = ends.get(months[j-1]), end = ends.get(months[j]);
      let complete = true;
      for (let i = prev; i <= end; i++) if (!finite(wealth[i])) { complete = false; break; }
      if (complete) result.push([months[j], wealth[end]/wealth[prev]-1]);
    }
    return result;
  }
  // Inverse standard normal via monotone inversion of a normal-CDF approximation.
  function normalQuantile(p) {
    function cdf(z) {
      const t = 1/(1+0.2316419*Math.abs(z));
      const tail = Math.exp(-z*z/2)/Math.sqrt(2*Math.PI)*t*(0.319381530+t*(-0.356563782+t*(1.781477937+t*(-1.821255978+t*1.330274429))));
      return z >= 0 ? 1-tail : tail;
    }
    let lo = -9, hi = 9;
    for (let i = 0; i < 45; i++) { const mid = (lo+hi)/2; if (cdf(mid) < p) lo = mid; else hi = mid; }
    return (lo+hi)/2;
  }
  function diagnostics(r) {
    const valid = Array.from(r).filter(finite), m = moments(valid), abs = r.map(Math.abs);
    const acf = [], lag = Array.from({length: 40}, (_, i) => i+1);
    lag.forEach(k => acf.push([k, pearson(...pairs(r, r, k)), pearson(...pairs(abs, abs, k))]));
    const sorted = valid.slice().sort((a,b) => a-b), histogram = [], qq = [];
    if (valid.length) {
      const min = sorted[0], width = (sorted[sorted.length-1]-min || 0.01)/40, counts = Array(40).fill(0);
      valid.forEach(x => counts[Math.min(39, Math.floor((x-min)/width))]++);
      counts.forEach((n,i) => histogram.push([min+i*width, min+(i+1)*width, n]));
      if (m.sd > 0) for (let i = 0; i < 101; i++) {
        const p = (i+0.5)/101, at = p*(sorted.length-1), lower = Math.floor(at);
        const q = sorted[lower]+(at-lower)*(sorted[Math.min(lower+1, sorted.length-1)]-sorted[lower]);
        qq.push([normalQuantile(p), (q-m.mean)/m.sd]);
      }
    }
    const variance = valid.reduce((sum,x) => sum+(x-m.mean)**2, 0)/m.n;
    const skew = variance > 0 ? valid.reduce((sum,x) => sum+(x-m.mean)**3,0)/m.n/variance**1.5 : NaN;
    const kurt = variance > 0 ? valid.reduce((sum,x) => sum+(x-m.mean)**4,0)/m.n/variance**2-3 : NaN;
    return { acf, histogram, qq, skew, kurt, negative: m.n ? valid.filter(x=>x<0).length/m.n : NaN };
  }
  function prepare(priceText, coverageText, tb3msText) {
    const rows = parseCSV(priceText), coverage = Object.fromEntries(parseCSV(coverageText).map(row=>[row.ticker,row]));
    const dates = rows.map(row=>row.Date);
    if (dates.some((d,i)=>!/^\d{4}-\d{2}-\d{2}$/.test(d) || (i && d <= dates[i-1]))) throw new Error('Dates must be unique and ascending');
    const tickers = EQUITIES.filter(t=>coverage[t] && Object.hasOwn(rows[0],t));
    if (tickers.length !== 25) throw new Error('Expected all 25 equity tickers in prices and coverage');
    const risk = riskFree(dates,Float64Array.from(rows,row=>row.BIL && finite(Number(row.BIL)) && Number(row.BIL)>0 ? Number(row.BIL) : NaN),tb3msText);
    const data = {};
    tickers.forEach(t=>{
      const prices = Float64Array.from(rows, row=>row[t] && finite(Number(row[t])) && Number(row[t])>0 ? Number(row[t]) : NaN);
      const r = logReturns(prices), x = excessReturns(r,risk.rf), path = wealthSeries(prices,r), rolls = {}, excessRolls = {};
      [21,63,252].forEach(w=>{ rolls[w] = rolling(r,r,w); });
      [63,252].forEach(w=>{ excessRolls[w] = rolling(x,x,w,true); });
      data[t] = { prices, r, x, ...path, rolls, excessRolls, excess: excessStats(x,risk.source), diagnostic: diagnostics(r) };
    });
    return { dates, tickers, coverage, data, ...risk };
  }
  const math = { parseCSV, moments, pairs, pearson, ranks, correlation, logReturns, riskFree, excessReturns, excessStats, rolling, wealthSeries, monthlyReturns, normalQuantile, diagnostics, prepare };
  // Node entry point allows numerical regression tests without a browser/build system.
  if (typeof module !== 'undefined' && module.exports) { module.exports = math; return; }

  const $ = id => document.getElementById(id), charts = new Map(), heatCache = new Map(), pairCache = new Map();
  let panel, displayed, fallbackData = [], heatKey = '';
  const asData = a => Array.from(a, x=>finite(x) ? x : null);
  function draw(id, option) {
    if (!window.echarts) return;
    let chart = charts.get(id);
    if (!chart) { chart = echarts.init($('chart-'+id)); charts.set(id, chart); }
    chart.setOption({ animation: false, aria: { show: true, enabled: true }, color: [PRIMARY, UP, INK, DOWN],
      backgroundColor: '#fff', textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: BODY },
      grid: { left: 65, right: 25, top: 65, bottom: 60 },
      legend: { top: 0, type: 'scroll', textStyle: { color: BODY } },
      tooltip: { trigger: 'axis', confine: true },
      xAxis: { type: 'category', axisLabel: { hideOverlap: true } },
      yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: HAIR } } }, ...option }, true);
  }
  function lines(id, dates, series, percent = false, extra = {}) {
    draw(id, { xAxis: { type: 'category', data: dates, axisLabel: { hideOverlap: true } },
      yAxis: { type: 'value', scale: true, axisLabel: { formatter: percent ? v=>pct(v) : v=>v }, splitLine: { lineStyle: { color: HAIR } } },
      dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 5 }],
      series: series.map(([name, data, options])=>({ name, type: 'line', showSymbol: false, connectNulls: false, sampling: 'lttb', lineStyle: { width: 1.5 }, data: asData(data), ...options })), ...extra });
  }
  function pairRoll(ticker, peer) {
    const key = ticker+':'+peer;
    if (!pairCache.has(key)) {
      const a = panel.data[ticker].r, b = panel.data[peer].r;
      pairCache.set(key, {63: rolling(a,b,63), 252: rolling(a,b,252)});
    }
    return pairCache.get(key);
  }
  function table(title, headers, rows) {
    const region = document.createElement('div'); region.className = 'table-scroll'; region.tabIndex = 0; region.setAttribute('role','region'); region.setAttribute('aria-label',title);
    const table = document.createElement('table'), caption = table.createCaption(); caption.textContent = title;
    const head = table.createTHead().insertRow();
    headers.forEach(h=>{ const th = document.createElement('th'); th.scope = 'col'; th.textContent = h; head.append(th); });
    const body = table.createTBody();
    rows.forEach(row=>{ const tr = body.insertRow(); row.forEach(v=>{ tr.insertCell().textContent = typeof v === 'number' ? num(v) : v; }); });
    region.append(table); return region;
  }
  function updateFallback() {
    if (!$('fallback').open || !displayed) return;
    const { fields, dates } = displayed, names = Object.keys(fields);
    const seriesRows = dates.slice(-20).map((date,j)=>[date,...names.map(name=>fields[name][dates.length-20+j])]);
    $('fallback-tables').replaceChildren(table('Computed time series · last 20 dates', ['Date',...names],seriesRows), ...fallbackData.map(args=>table(...args)));
  }
  function renderHeat() {
    const method = $('method').value, window = $('heat-window').value, key = method+':'+window;
    if (!heatCache.has(key)) {
      const start = window === '63' ? Math.max(0,panel.dates.length-63) : 0, cells = [], rows = [];
      panel.tickers.forEach((a,i)=>panel.tickers.forEach((b,j)=>{
        const c = j < i ? rows[j*25+i] : [a,b,...Object.values(correlation(panel.data[a].r,panel.data[b].r,method,start))];
        rows.push([a,b,c[2],c[3]]); cells.push([i,j,finite(c[2]) ? c[2] : '-']);
      }));
      heatCache.set(key,{cells,rows});
    }
    const cached = heatCache.get(key);
    if (heatKey !== key) {
      draw('heat',{ grid: {left:65,right:30,top:45,bottom:110}, legend: {show:false},
        title: {text: method+' · '+(window==='63' ? '63d as-of '+panel.dates.at(-1) : 'full pairwise sample'), textStyle:{fontSize:12,color:BODY}},
        xAxis: {type:'category',data:panel.tickers,axisLabel:{rotate:60,interval:0}}, yAxis:{type:'category',data:panel.tickers,axisLabel:{interval:0}},
        visualMap:{min:-1,max:1,calculable:true,orient:'horizontal',left:'center',bottom:0,inRange:{color:[DOWN,SOFT,PRIMARY]}},
        tooltip:{trigger:'item',confine:true,formatter:p=>{const row=cached.rows[p.data[0]*25+p.data[1]];return row[0]+' / '+row[1]+'<br>corr: '+num(row[2])+' · n='+row[3];}},
        series:[{type:'heatmap',data:cached.cells,emphasis:{itemStyle:{borderColor:INK,borderWidth:1}}}] });
      heatKey = key;
    }
    return ['Growth-25 '+method+' · '+(window==='63'?'63d as-of '+panel.dates.at(-1):'full sample'), ['Ticker','Peer','Correlation','Overlap n'],cached.rows];
  }
  function render() {
    const ticker = $('ticker').value.trim().toUpperCase();
    if (!panel.tickers.includes(ticker)) { $('ticker').setCustomValidity('Choose a Growth-25 equity ticker.'); $('ticker').reportValidity(); return; }
    $('ticker').setCustomValidity(''); $('ticker').value = ticker;
    const proxy = $('market').value, peer = $('peer').value, method = $('method').value;
    const s = panel.data[ticker], coverage = panel.coverage[ticker], market = pairRoll(ticker,proxy), peerRoll = pairRoll(ticker,peer);
    const first = s.prices.findIndex(finite), last = s.prices.findLastIndex(finite), dates = panel.dates.slice(first,last+1), cut = a=>a.slice(first,last+1);
    const count = s.prices.reduce((n,p)=>n+Number(finite(p)),0), m = moments(s.r), diag = s.diagnostic;
    const years = Number(coverage.years), thin = /^(true|1|yes)$/i.test(coverage.thin_lt5y) || years < 5;
    $('sample').replaceChildren();
    [ticker, panel.dates[first]+' → '+panel.dates[last], 'n_obs '+count, 'years '+years.toFixed(2)].forEach(text=>{const span=document.createElement('span');span.textContent=text;$('sample').append(span);});
    if (thin) { const badge=document.createElement('span');badge.className='badge thin';badge.textContent='Thin history · <5y';$('sample').append(badge); }
    const months = monthlyReturns(panel.dates,s.wealth).sort((a,b)=>a[1]-b[1]);
    const monthText = row=>row ? row[0]+' · '+pct(row[1]) : '—';
    const lastWealth = Array.from(s.wealth).findLast(finite);
    const summary = [ ['AnnReturn (compounded; 252/n_obs)',pct((lastWealth/100)**(252/count)-1)], ['AnnVol (daily log returns)',pct(m.sd*Math.sqrt(252))],
      ['MaxDD',pct(Math.min(...s.dd.filter(finite)))], ['Sharpe (excess of BIL; TB3MS before BIL)',num(s.excess.sharpe)],
      ['rf source: TB3MS fallback share',pct(s.excess.fallbackShare)], ['Sharpe_rf0 — legacy (rf = 0)',num(m.sd>0 ? Math.sqrt(252)*m.mean/m.sd : NaN)],
      ['Best month (month-end)',monthText(months.at(-1))],['Worst month (month-end)',monthText(months[0])],['Start / end',panel.dates[first]+' / '+panel.dates[last]],
      ['n_obs (valid closes) / valid daily returns',count+' / '+m.n],['Skewness (moment)',num(diag.skew)],['Excess kurtosis (moment)',num(diag.kurt)],['Hit rate r < 0',pct(diag.negative)] ];
    $('stats').replaceChildren(); summary.forEach(([k,v])=>{const tr=document.createElement('tr'), th=document.createElement('th'),td=document.createElement('td');th.scope='row';th.textContent=k;td.textContent=v;tr.append(th,td);$('stats').append(tr);});
    lines('price',dates,[['Adjusted close',cut(s.prices)],['Wealth (100)',cut(s.wealth),{yAxisIndex:1}]],false,{ yAxis:[{type:'value',name:'Adj close',scale:true},{type:'value',name:'Wealth',scale:true}],grid:{left:65,right:65,top:65,bottom:60} });
    lines('drawdown',dates,[['Drawdown',cut(s.dd),{areaStyle:{opacity:0.1},itemStyle:{color:DOWN}}]],true);
    lines('vol',dates,[21,63,252].map(w=>['σ̂('+w+')',cut(s.rolls[w].vol)]),true);
    lines('sharpe',dates,[...[63,252].map(w=>['Sharpe ex-BIL('+w+')',cut(s.excessRolls[w].sharpe)]), ...[63,252].map(w=>['legacy rf=0 ('+w+')',cut(s.rolls[w].sharpe),{lineStyle:{type:'dashed',width:1}}])]);
    lines('market',dates,[... [63,252].map(w=>['β('+w+') vs '+proxy,cut(market[w].beta)]), ...[63,252].map(w=>['corr('+w+') vs '+proxy,cut(market[w].corr),{lineStyle:{type:'dashed',width:1.5}}])]);
    lines('peer',dates,[63,252].map(w=>['corr('+w+') vs '+peer,cut(peerRoll[w].corr)]),false,{yAxis:{type:'value',min:-1,max:1}});
    draw('hist',{xAxis:{type:'category',name:'Log return',data:diag.histogram.map(row=>pct((row[0]+row[1])/2)),axisLabel:{hideOverlap:true}},yAxis:{type:'value',name:'Count'},series:[{type:'bar',name:'Daily log returns',data:diag.histogram.map(row=>row[2]),barCategoryGap:0}]});
    draw('qq',{xAxis:{type:'value',name:'Normal quantile',nameLocation:'middle',nameGap:28},yAxis:{type:'value',name:'Standardized return'},tooltip:{trigger:'item'},series:[{type:'scatter',name:'Empirical quantiles',data:diag.qq,symbolSize:5},{type:'line',name:'Normal reference',data:[[-3,-3],[3,3]],showSymbol:false,lineStyle:{color:INK,type:'dashed'}}]});
    draw('acf',{xAxis:{type:'category',name:'Lag',data:diag.acf.map(row=>row[0])},yAxis:{type:'value',min:-1,max:1},series:[1,2].map((col)=>({name:col===1?'ACF(r)':'ACF(|r|)',type:'bar',data:diag.acf.map(row=>finite(row[col])?row[col]:null)}))});
    const leadLag = Array.from({length:11},(_,i)=>{const k=i-5,[a,b]=pairs(s.r,panel.data[peer].r,k);return [k,pearson(a,b),a.length];});
    draw('lag',{xAxis:{type:'category',name:'k',data:leadLag.map(row=>row[0])},yAxis:{type:'value',min:-1,max:1},series:[{name:ticker+' vs '+peer+' at t+k',type:'bar',data:asData(leadLag.map(row=>row[1]))}]});
    const [a,b] = pairs(s.r,panel.data[peer].r), scatter=a.map((x,i)=>[x,b[i]]);
    draw('scatter',{xAxis:{type:'value',name:ticker+' log r',axisLabel:{formatter:pct}},yAxis:{type:'value',name:peer+' log r',axisLabel:{formatter:pct}},tooltip:{trigger:'item'},series:[{name:'Overlapping returns · n='+a.length,type:'scatter',symbolSize:3,itemStyle:{opacity:0.35},data:scatter,large:true}]});
    const correlations=panel.tickers.map(t=>{const c=correlation(s.r,panel.data[t].r,method);return [t,c.value,c.n];});
    draw('panel',{grid:{left:55,right:25,top:35,bottom:35},xAxis:{type:'value',min:-1,max:1},yAxis:{type:'category',data:panel.tickers,inverse:true,axisLabel:{interval:0}},series:[{name:method+' vs '+ticker,type:'bar',data:asData(correlations.map(row=>row[1]))}]});
    const fields={adj_close:cut(s.prices),log_return:cut(s.r),rf_log_return:cut(panel.rf),rf_is_tb3ms:cut(Float64Array.from(panel.source,v=>v ? Number(v==='TB3MS') : NaN)),wealth_100:cut(s.wealth),drawdown:cut(s.dd)};
    [21,63,252].forEach(w=>{fields['vol_'+w]=cut(s.rolls[w].vol);});
    [63,252].forEach(w=>{fields['sharpe_rf0_'+w]=cut(s.rolls[w].sharpe);fields['sharpe_exbil_'+w]=cut(s.excessRolls[w].sharpe);fields['beta_'+proxy+'_'+w]=cut(market[w].beta);fields['corr_'+proxy+'_'+w]=cut(market[w].corr);fields['market_overlap_'+w]=cut(market[w].count);fields['peer_corr_'+peer+'_'+w]=cut(peerRoll[w].corr);fields['peer_overlap_'+w]=cut(peerRoll[w].count);});
    displayed={ticker,proxy,peer,fields,dates};
    fallbackData=[['Return histogram',['Bin start','Bin end','Count'],diag.histogram],['Normal QQ',['Normal quantile','Standardized return'],diag.qq],['ACF',['Lag','ACF(r)','ACF(|r|)'],diag.acf],['Lead–lag vs '+peer,['Lag k','Correlation','Overlap n'],leadLag],['Scatter vs '+peer,[ticker+' log return',peer+' log return'],scatter],['Panel '+method,['Ticker','Correlation','Overlap n'],correlations],renderHeat()];
    updateFallback();
    $('status').textContent=window.echarts ? ticker+' · market '+proxy+' · peer '+peer+' · '+method+' panel correlation.' : 'Chart library unavailable. Computed statistics, data tables, and CSV export are available.';
    if (panel.fallbackUnavailable) $('status').textContent+=' TB3MS fallback was unavailable; pre-BIL excess values are blank.';
  }
  async function init() {
    try {
      const texts=await Promise.all(['../data/growth_alpha_adj_close.csv','../data/growth_panel_history_coverage.csv','../data/fred_tb3ms.csv'].map(async (url,i)=>{try {const response=await fetch(url);if(!response.ok)throw new Error(url+' ('+response.status+')');return await response.text();} catch(error) {if(i===2)return null;throw error;}}));
      panel=prepare(...texts);
      panel.tickers.forEach(t=>{const option=document.createElement('option');option.value=t;$('tickers').append(option);const peer=document.createElement('option');peer.value=t;peer.textContent=t;$('peer').append(peer);});
      $('peer').value='QQQM';
      $('controls').querySelectorAll('input,select,button').forEach(el=>{el.disabled=false;});
      $('controls').addEventListener('submit',event=>{event.preventDefault();render();});
      $('controls').addEventListener('change',render);
      $('ticker').addEventListener('input',()=>{$('ticker').setCustomValidity('');});
      $('fallback').addEventListener('toggle',updateFallback);
      $('export').addEventListener('click',()=>{
        if (!displayed) return;
        const {ticker,proxy,peer,dates,fields}=displayed, names=Object.keys(fields);
        const rows=[['Date','ticker','market_proxy','peer',...names].join(','),...dates.map((date,i)=>[date,ticker,proxy,peer,...names.map(name=>finite(fields[name][i])?fields[name][i]:'')].join(','))];
        const url=URL.createObjectURL(new Blob([rows.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'})), link=document.createElement('a');
        link.href=url;link.download=ticker+'_time_series.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });
      render();
      if (typeof ResizeObserver !== 'undefined') {
        const observer=new ResizeObserver(()=>charts.forEach(chart=>chart.resize()));
        document.querySelectorAll('.explorer-grid .chart').forEach(el=>observer.observe(el));
      } else window.addEventListener('resize',()=>charts.forEach(chart=>chart.resize()));
    } catch(error) { $('status').textContent='Unable to load explorer: '+error.message+'. Reload to retry; source CSV links remain available.'; }
  }
  init();
}());
