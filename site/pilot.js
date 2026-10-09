'use strict';
(async()=>{
 const body=document.getElementById('phase-rows');
 const state=document.getElementById('pilot-data-status');
 try{
  const response=await fetch('data/etf-pilot-summary.json');
  if(!response.ok)throw new Error('Summary unavailable');
  const data=await response.json();
  if(data.market_pilot_executed!==true||data.original_stock_experiment_completed!==false||data.comparisons?.full_period?.length!==48)throw new Error('Invalid scope');
  function render(){
   const signal=document.getElementById('pilot-signal').value;
   const cost=Number(document.getElementById('pilot-cost').value);
   const rows=data.comparisons.full_period.filter(x=>x.signal===signal&&x.cost_bps_per_side===cost);
   if(rows.length!==6||rows.some(x=>![x.monthly_cagr,x.semiannual_cagr,x.cagr_difference_pp,x.max_drawdown_difference_pp].every(Number.isFinite)))throw new Error('Incomplete scenarios');
   const fragment=document.createDocumentFragment();
   for(const row of rows){
    const tr=document.createElement('tr');
    const primary=row.phase[0]===3;
    if(primary)tr.className='phase-primary';
    const phase=row.phase.map(x=>new Intl.DateTimeFormat('en',{month:'short',timeZone:'UTC'}).format(new Date(Date.UTC(2000,x-1,1)))).join(' / ')+(primary?' · primary':'');
    for(const value of [phase,`${(100*row.monthly_cagr).toFixed(2)}%`,`${(100*row.semiannual_cagr).toFixed(2)}%`,`${row.cagr_difference_pp>=0?'+':''}${row.cagr_difference_pp.toFixed(2)} pp`,`${row.max_drawdown_difference_pp>=0?'+':''}${row.max_drawdown_difference_pp.toFixed(2)} pp`]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
    fragment.append(tr);
   }
   body.replaceChildren(fragment);document.getElementById('phase-caption').textContent=`Six semiannual phases · ${signal==='12-1'?'12–1 signal':'blended signal'} · ${cost} bps per side`;
   state.textContent='Positive CAGR difference favors monthly selection. Positive drawdown difference means the monthly drawdown is less negative.';
  }
  document.getElementById('pilot-signal').addEventListener('change',render);document.getElementById('pilot-cost').addEventListener('change',render);render();
 }catch{state.textContent='The saved comparison table could not be loaded. Use the downloadable CSV and static figures; no missing values are inferred.';}
})();
