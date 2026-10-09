#!/usr/bin/env python3
"""Stress the sole sourced price reconstruction without changing the base run."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from stock_pilot.engine import run_matrix


def main():
    directory=Path(sys.argv[1])
    inputs_path=directory/'normalized-inputs.json'
    result_path=directory/'results.json'
    data=json.loads(inputs_path.read_text())
    baseline=json.loads(result_path.read_text())
    config=json.loads((ROOT/'configs/stock-pilot.v1.json').read_text())
    identifier=next(k for k,v in data['security'].items() if v['ticker']=='FISV')
    target='2025-11-12'
    base_runs={r['run_id']:r for r in baseline['runs']}
    scenarios=[]
    for change in (-.01,.01):
        variant=deepcopy(data)
        for field in ('signal_close','adjusted_close'):
            variant['bars'][identifier][target][field]*=1+change
        changed=run_matrix(variant,config)
        max_nav=max(abs(row['nav']/base['nav']-1) for r in changed['runs'] for row,base in zip(r['daily'],base_runs[r['run_id']]['daily']))
        different_targets=sum(any(a['target_weight']!=b['target_weight'] for a,b in zip(r['signals'],base_runs[r['run_id']]['signals'])) for r in changed['runs'])
        scenarios.append({'reconstructed_close_change':change,'strategy_paths':len(changed['runs']),
                          'max_relative_nav_change':max_nav,'paths_with_changed_targets':different_targets})
    events=[]
    for ticker,day in [('HON','2025-10-30'),('CMCSA','2026-01-05'),('HON','2026-06-29'),('SPGI','2026-07-01')]:
        security=next(k for k,v in data['security'].items() if v['ticker']==ticker)
        held=[r['run_id'] for r in baseline['runs'] if any(row['session']==day and security in row['positions'] for row in r['daily'])]
        events.append({'ticker':ticker,'date':day,'paths_holding_at_event_close':held,
                       'entitlement_model':'vendor_adjusted_proxy_not_independently_verified'})
    result={'schema_version':1,'data_track':'baseline_issuer_stock_pilot','formal_protocol_compliant':False,
        'config_sha256':hashlib.sha256((ROOT/'configs/stock-pilot.v1.json').read_bytes()).hexdigest(),
        'normalized_inputs_sha256':hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
        'original_results_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
        'method':'Change only reconstructed FISV signal/adjusted close by +/-1%; keep its observed opening price unchanged; rerun all16 strategy/cost paths.',
        'not_a_confidence_interval':True,'scenarios':scenarios,'spin_off_exposure':events,
        'fisv_paths_holding_on_reconstruction_date':[r['run_id'] for r in baseline['runs'] if any(row['session']==target and identifier in row['positions'] for row in r['daily'])]}
    with (directory/'sensitivity.json').open('x') as stream:
        json.dump(result,stream,indent=2)
    (ROOT/'site/data/stock-pilot-sensitivity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
