import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source=readFileSync(new URL('../site/validation.js',import.meta.url),'utf8');
const published=JSON.parse(readFileSync(new URL('../site/data/validation-study-summary.json',import.meta.url),'utf8'));
class Element {
  constructor(tag=''){this.tagName=tag;this.textContent='';this.value='';this.disabled=false;this.children=[];this.listeners=new Map();}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes.flatMap(n=>n.tagName==='#fragment'?n.children:[n]);}
  addEventListener(type,listener){this.listeners.set(type,[...(this.listeners.get(type)||[]),listener]);}
  change(value){this.value=String(value);for(const listener of this.listeners.get('change')||[])listener();}
}
async function start(mutate=()=>{},fail=false,stall=false){
  const data=structuredClone(published);mutate(data);
  const nodes=new Map(['validation-signal','validation-cost','validation-rows','validation-caption','validation-data-status'].map(i=>[i,new Element()]));
  nodes.get('validation-signal').value='12-1';nodes.get('validation-cost').value='5';
  await vm.runInNewContext(source,{document:{getElementById:i=>nodes.get(i),createElement:t=>new Element(t),createDocumentFragment:()=>new Element('#fragment')},
    AbortController,clearTimeout,
    setTimeout:stall?callback=>{queueMicrotask(callback);return 0;}:setTimeout,
    fetch:async(_,options)=>{if(fail)throw Error('Unavailable');if(stall)return new Promise((resolve,reject)=>{if(options.signal.aborted)reject(Error('Aborted'));else options.signal.addEventListener('abort',()=>reject(Error('Aborted')));});return{ok:true,json:async()=>data};}});
  return nodes;
}
function unavailable(nodes){assert.equal(nodes.get('validation-signal').disabled,true);assert.equal(nodes.get('validation-cost').disabled,true);assert.match(nodes.get('validation-data-status').textContent,/could not be verified/);}
test('all eight scenarios render six phases plus the tranche',async()=>{
  const nodes=await start();assert.equal(nodes.get('validation-cost').disabled,false);
  for(const signal of ['12-1','mixed'])for(const cost of [0,5,10,25]){
    nodes.get('validation-signal').change(signal);nodes.get('validation-cost').change(cost);
    assert.equal(nodes.get('validation-rows').children.length,7);
    assert.equal(nodes.get('validation-rows').children[6].children[0].textContent,'Six-sleeve tranche');
    assert.match(nodes.get('validation-caption').textContent,new RegExp(`${cost} bps`));
  }
});
test('network failure fails closed',async()=>unavailable(await start(()=>{},true)));
test('stalled request times out and fails closed',async()=>unavailable(await start(()=>{},false,true)));
test('missing tranche fails closed',async()=>unavailable(await start(s=>s.runs=s.runs.filter(r=>r.run_id!=='T12-5bps'))));
test('stale protocol fails closed',async()=>unavailable(await start(s=>s.source_hashes.protocol_sha256='0'.repeat(64))));
test('duplicate calendar cell fails closed',async()=>unavailable(await start(s=>s.calendar_comparisons[1]=s.calendar_comparisons[0])));
test('wrong reported CAGR difference fails closed',async()=>unavailable(await start(s=>s.primary_intervals[0].cagr_difference_pp+=1)));
test('nonfinite risk fails closed',async()=>unavailable(await start(s=>s.runs[0].monthly_risk.beta_to_SPY_excess_returns=NaN)));
