#!/usr/bin/env python3
"""Offline checks for the published real-market pilot, not a fresh market acquisition."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check():
 s=json.loads((ROOT/'site/data/etf-pilot-summary.json').read_text())
 v=json.loads((ROOT/'site/data/etf-pilot-validation.json').read_text())
 cfg=json.loads((ROOT/'configs/sector-etf-pilot.v1.json').read_text())
 assert s['market_pilot_executed'] is True and s['original_stock_experiment_completed'] is False
 assert s['run_count']==56 and s['benchmark_run_count']==4 and len(s['runs'])==60
 assert s['audit']['passed'] and not s['audit']['errors'] and all(s['checks'].values())
 assert v['passed'] and v['independent_run_count']==60 and v['imports_project_code'] is False and all(v['checks'].values())
 assert v['summary_sha256']==sha(ROOT/'site/data/etf-pilot-summary.json')
 assert s['config_sha256']==v['config_sha256']==sha(ROOT/'configs/sector-etf-pilot.v1.json')
 assert v['verifier_code_sha256']==sha(ROOT/'scripts/validate_etf_pilot_independent.py')
 for name,digest in s['code_sha256'].items():assert sha(ROOT/name)==digest,name
 assert s['code_sha256']==v['engine_code_sha256']
 ids={r['run_id'] for r in s['runs']};assert len(ids)==60
 for run in s['runs']:
  full=run['metrics']['full_period'];ytd=run['metrics']['ytd2026']
  assert full['annualization_years']==25 and math.isclose(full['cagr'],(1+full['total_return'])**(1/25)-1,abs_tol=1e-12)
  assert full['end_nav']==ytd['start_nav'] and ytd['cagr'] is None and ytd['annualized_two_sided_turnover'] is None
  assert all(math.isfinite(full[key]) for key in ['cagr','max_drawdown','total_return','mean_cash_weight'])
  assert 0<=full['mean_cash_weight']<=1 and -1<full['max_drawdown']<=0
 expected={(sig,tuple(phase),cost) for sig in ['12-1','mixed'] for phase in cfg['phase_pairs'] for cost in cfg['cost_bps_per_side_scenarios']}
 for period in ['full_period','ytd2026']:
  rows=s['comparisons'][period];assert len(rows)==48
  assert {(x['signal'],tuple(x['phase']),x['cost_bps_per_side']) for x in rows}==expected
  for row in rows:
   assert row['monthly_run_id'] in ids and row['semiannual_run_id'] in ids
   assert math.isclose(row['net_return_difference_pp'],100*(row['monthly_total_return']-row['semiannual_total_return']),abs_tol=1e-10)
  with (ROOT/f'site/data/etf-pilot-{period}.csv').open() as f: saved=list(csv.DictReader(f))
  assert len(saved)==48
  for actual,ref in zip(saved,rows):
   for key,value in ref.items():
    if isinstance(value,list):assert json.loads(actual[key])==value
    elif isinstance(value,(int,float)):assert math.isclose(float(actual[key]),value,abs_tol=1e-12)
    elif value is None:assert actual[key]==''
    else:assert actual[key]==value
 with (ROOT/'site/data/etf-pilot-annual.csv').open() as f: annual=list(csv.DictReader(f))
 assert len(annual)==1200
 assert {(r['signal'],tuple(json.loads(r['phase'])),float(r['cost_bps_per_side']),int(r['year'])) for r in annual}=={(*row,year) for row in expected for year in range(2001,2026)}
 for identity,points in s['portfolio_paths'].items():
  run=next(r for r in s['runs'] if r['run_id']==identity)
  assert points[0]['wealth']==1 and math.isclose(points[-1]['wealth'],1+run['metrics']['full_period']['total_return'],abs_tol=1e-12)
 assert len(s['primary_annual'])==25
 print('PASS: 60 published paths, 48 phase/cost comparisons, 1,200 annual rows, scope flags and independent-replay provenance.')
 return True
if __name__=='__main__':check()
