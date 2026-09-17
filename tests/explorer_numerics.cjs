/* Independent fixtures for the exact JS shipped to Pages. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const m = require('../docs/explorer/explorer.js');
const near = (a,b,tol=1e-10) => assert.ok(Math.abs(a-b)<tol, `${a} != ${b}`);
assert.deepEqual(m.parseCSV('\uFEFFa,b\r\n"x,y","a""b"\r\n'), [{a:'x,y',b:'a"b'}]);
const p = Float64Array.from([100,110,NaN,121,133.1]);
const r = m.logReturns(p);
near(r[1],Math.log(1.1)); assert.ok(Number.isNaN(r[2])); assert.ok(Number.isNaN(r[3])); near(r[4],Math.log(1.1));
const path = m.wealthSeries(p,r);
near(path.wealth[0],100); near(path.wealth[4],121); assert.ok(Number.isNaN(path.wealth[3]));
near(m.wealthSeries([100,80,120],m.logReturns([100,80,120])).dd[1],-0.2);
const a = [0.01,0.03,NaN,-0.02,0.04], b = [0.02,0.06,0.1,-0.04,0.08];
const roll = m.rolling(a,b,3);
near(roll.beta[4],0.5); near(roll.corr[4],1); assert.equal(roll.count[4],2); assert.ok(Number.isNaN(roll.vol[4]));
assert.ok(Number.isNaN(roll.beta[1]));
const complete = m.rolling([0.01,0.02,0.03],[0.01,0.02,0.03],3);
near(complete.vol[2],0.01*Math.sqrt(252)); near(complete.sharpe[2],2*Math.sqrt(252));
assert.ok(Number.isNaN(m.rolling([0,0,0],[0,0,0],3).beta[2]));
// Future changes must not change a trailing estimate.
const before=m.rolling([1,2,3,4],[2,4,6,8],3), after=m.rolling([1,2,3,1000],[2,4,6,-1000],3);
near(before.beta[2],after.beta[2]);
assert.deepEqual(Array.from(m.ranks([3,1,1,5])),[3,1.5,1.5,4]);
near(m.correlation([1,100,2,NaN],[10,30,20,40],'spearman').value,1);
assert.equal(m.correlation(a,b).n,4);
const lagA=[1,4,2,8,3,7], lagB=[NaN,1,4,2,8,3]; near(m.pearson(...m.pairs(lagA,lagB,1)),1);
const months=m.monthlyReturns(['2024-01-31','2024-02-29','2024-03-28','2024-04-15'],[100,110,99,150]);
assert.equal(months.length,2);near(months[0][1],0.1);near(months[1][1],-0.1);
assert.equal(m.monthlyReturns(['2024-01-31','2024-02-01','2024-02-29','2024-03-01'],[100,NaN,110,112]).length,0);
near(m.normalQuantile(0.5),0,1e-6);near(m.normalQuantile(0.975),1.959964,1e-5);
const panel=m.prepare(fs.readFileSync('docs/data/growth_alpha_adj_close.csv','utf8'),fs.readFileSync('docs/data/growth_panel_history_coverage.csv','utf8'));
assert.equal(panel.tickers.length,25);assert.ok(!panel.tickers.includes('BIL'));
for (const t of panel.tickers) {
 const s=panel.data[t], c=panel.coverage[t], start=s.prices.findIndex(Number.isFinite), end=s.prices.findLastIndex(Number.isFinite);
 assert.equal(panel.dates[start],c.start);assert.equal(panel.dates[end],c.end);
 assert.equal(s.prices.filter(Number.isFinite).length,Number(c.n_obs));
 // All present data are contiguous; wealth must match normalized actual prices.
 near(s.wealth[end],100*s.prices[end]/s.prices[start],1e-7);
}
const voo=panel.data.VOO;
for(const beta of voo.rolls[63].beta) if(Number.isFinite(beta)) near(beta,1);
assert.ok(voo.diagnostic.acf[0][2]>Math.abs(voo.diagnostic.acf[0][1]));
assert.ok(Number(panel.coverage.QQQM.n_obs)<Number(panel.coverage.VOO.n_obs));
assert.equal(panel.coverage.QQQM.thin_lt5y,'False');
