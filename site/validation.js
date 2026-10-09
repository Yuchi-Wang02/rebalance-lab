'use strict';

// Enhance a complete static report with saved scenarios. Never calculate a strategy in the browser.
(async () => {
  const signal = document.getElementById('validation-signal');
  const cost = document.getElementById('validation-cost');
  const body = document.getElementById('validation-rows');
  const caption = document.getElementById('validation-caption');
  const state = document.getElementById('validation-data-status');
  const assert = (v) => { if (!v) throw new Error('Saved result does not match this study.'); };
  const finite = (v) => typeof v === 'number' && Number.isFinite(v);
  const near = (a,b) => Math.abs(a-b) < 1e-8;
  let accounts;
  function unavailable() {
    signal.disabled = true; cost.disabled = true;
    const tr = document.createElement('tr'); const td = document.createElement('td');
    td.colSpan = 4; td.textContent = 'Saved scenarios unavailable.'; tr.append(td); body.replaceChildren(tr);
    caption.textContent = 'Interactive results unavailable';
    state.textContent = 'The complete saved result could not be verified. The static primary tables and figures remain available; download the CSV to inspect other scenarios.';
  }
  function validate(s) {
    assert(s?.experiment_id === 'sector-etf-validation-v1' && s.status === 'computed_and_separately_reconciled');
    assert(s.months === 300 && s.account_count === 108 && s.derived_tranche_count === 8);
    assert(s.protocol?.report_anchor === '2000-12-29' && s.protocol?.primary_end === '2025-12-31');
    assert(s.source_hashes?.protocol_sha256 === 'df649c91c94861a7e765ac1810bef44d60f02de275bf9df1ae90132188b57366');
    assert(s.validation?.passed === true && s.validation.imports_project_calculation_code === false);
    assert(Array.isArray(s.runs) && s.runs.length === 116);
    const map = new Map();
    for (const r of s.runs) {
      assert(!map.has(r.run_id));
      const q = r.metrics?.full_period;
      assert(q && finite(q.cagr) && q.cagr > -1 && finite(q.max_drawdown) && q.max_drawdown > -1 && q.max_drawdown <= 0);
      assert(q.start_session === '2000-12-29' && q.end_session === '2025-12-31' && q.annualization_years === 25);
      assert(near(q.cagr, Math.pow(1+q.total_return,1/25)-1));
      const risk = r.monthly_risk;
      assert(risk?.months === 300 && ['sharpe_monthly_annualized','tracking_error_monthly_annualized','beta_to_SPY_excess_returns'].every(k=>finite(risk[k])));
      map.set(r.run_id,r);
    }
    assert(Array.isArray(s.calendar_comparisons) && s.calendar_comparisons.length === 48);
    const seen = new Set();
    for (const r of s.calendar_comparisons) {
      assert(['12-1','mixed'].includes(r.signal) && [0,5,10,25].includes(r.cost_bps_per_side));
      assert(Array.isArray(r.phase) && r.phase.length===2 && Number.isInteger(r.phase[0]) && r.phase[0]>=1 && r.phase[0]<=6 && r.phase[1]===r.phase[0]+6);
      const key = `${r.signal}|${r.cost_bps_per_side}|${r.phase[0]}`; assert(!seen.has(key));seen.add(key);
      assert(map.has(r.high_run_id) && map.has(r.low_run_id));
      const prefix = r.signal === '12-1' ? '12' : 'MIX';
      assert(r.high_run_id===`M${prefix}-${r.cost_bps_per_side}bps` && r.low_run_id===`S${prefix}-${String(r.phase[0]).padStart(2,'0')}-${String(r.phase[1]).padStart(2,'0')}-${r.cost_bps_per_side}bps`);
      assert(near(r.cagr_difference_pp,100*(map.get(r.high_run_id).metrics.full_period.cagr-map.get(r.low_run_id).metrics.full_period.cagr)));
    }
    for (const prefix of ['12','MIX']) for (const c of [0,5,10,25]) assert(map.has(`T${prefix}-${c}bps`));
    assert(Array.isArray(s.primary_intervals) && s.primary_intervals.length===6);
    for (const r of s.primary_intervals) {
      assert(map.has(r.high_run_id) && map.has(r.low_run_id) && r.months===300 && r.repetitions===10000);
      assert(Array.isArray(r.ci95_difference_pp) && r.ci95_difference_pp.length===2 && r.ci95_difference_pp.every(finite) && r.ci95_difference_pp[0]<=r.ci95_difference_pp[1]);
      assert(near(r.cagr_difference_pp,100*(map.get(r.high_run_id).metrics.full_period.cagr-map.get(r.low_run_id).metrics.full_period.cagr)));
    }
    return map;
  }
  function render() {
    assert(['12-1','mixed'].includes(signal.value) && ['0','5','10','25'].includes(cost.value));
    const prefix=signal.value==='12-1'?'12':'MIX'; const c=Number(cost.value);
    const monthly=accounts.get(`M${prefix}-${c}bps`).metrics.full_period.cagr;
    const fragment=document.createDocumentFragment();
    const names=['Jan / Jul','Feb / Aug','Mar / Sep · reference','Apr / Oct','May / Nov','Jun / Dec'];
    const ids=names.map((_,j)=>`S${prefix}-${String(j+1).padStart(2,'0')}-${String(j+7).padStart(2,'0')}-${c}bps`);
    ids.push(`T${prefix}-${c}bps`); names.push('Six-sleeve tranche');
    ids.forEach((i,j)=>{
      const q=accounts.get(i).metrics.full_period;const tr=document.createElement('tr');if(j===2)tr.className='v-primary';
      const delta=100*(monthly-q.cagr);
      for (const [k,value] of [names[j],`${(q.cagr*100).toFixed(2)}%`,`${delta>=0?'+':''}${delta.toFixed(2)} pp`,`${(q.max_drawdown*100).toFixed(2)}%`].entries()) {
        const td=document.createElement(k===0?'th':'td');if(k===0)td.scope='row';td.textContent=value;tr.append(td);
      }fragment.append(tr);
    });body.replaceChildren(fragment);
    caption.textContent=`${signal.value==='12-1'?'12–1':'Blended'} · ${c} bps per side · monthly CAGR ${(100*monthly).toFixed(2)}% · 2001–2025`;
    state.textContent='Complete saved matrix verified. Controls change this scenario table only; the primary figures, risk table and intervals retain 12–1 at 5 bps.';
  }
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),10000);
  try {
    const response=await fetch('data/validation-study-summary.json',{cache:'no-store',signal:controller.signal});assert(response.ok);
    accounts=validate(await response.json());render();signal.disabled=false;cost.disabled=false;
    for (const control of [signal,cost]) control.addEventListener('change',()=>{try{render();}catch{unavailable();}});
  }catch{unavailable();}finally{clearTimeout(timeout);}
})();
