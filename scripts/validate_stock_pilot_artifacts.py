#!/usr/bin/env python3
"""Validate public stock-pilot outputs and replay provenance without private data."""
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    base=ROOT/'site/data'
    summary_path=base/'stock-pilot-summary.json'
    summary=json.loads(summary_path.read_text())
    nav=json.loads((base/'stock-pilot-nav.json').read_text())
    replay=json.loads((base/'stock-pilot-validation.json').read_text())
    sensitivity=json.loads((base/'stock-pilot-sensitivity.json').read_text())
    config_path=ROOT/'configs/stock-pilot.v1.json'
    config=json.loads(config_path.read_text())
    for obj in (summary,nav,replay,sensitivity):
        require(obj['data_track']=='baseline_issuer_stock_pilot' and obj['formal_protocol_compliant'] is False,'Stock pilot scope mismatch')
    require(len(summary['runs'])==16 and len(summary['benchmarks'])==8,'Missing a strategy/cost path')
    expected={(s,c) for s in [*config['arms'],*config['benchmarks']] for c in config['costs']}
    runs=summary['runs']+summary['benchmarks']
    require({(r['strategy_id'],r['cost_bps_per_side']) for r in runs}==expected,'Invalid strategy/cost matrix')
    paths={s['run_id']:s['points'] for s in nav['series']}
    require(len(paths)==24,'Missing or duplicate portfolio path')
    windows={'year2025':(config['initial_signal'],config['report_anchor']),
             'ytd2026':(config['report_anchor'],config['report_end']),
             'full_period':(config['initial_signal'],config['report_end'])}
    for run in runs:
        points=paths[run['run_id']]
        require([p['date'] for p in points]==sorted({p['date'] for p in points}),'Portfolio dates are not unique and increasing')
        require(all(isinstance(p['value'],(int,float)) and math.isfinite(p['value']) and p['value']>0 for p in points),'Invalid portfolio NAV')
        for period,(start,end) in windows.items():
            selected=[p for p in points if start<=p['date']<=end]
            require(selected[0]['date']==start and selected[-1]['date']==end,'Missing metric endpoint')
            m=run['metrics'][period]
            total=selected[-1]['value']/selected[0]['value']-1
            high=selected[0]['value'];worst=0
            for point in selected:
                high=max(high,point['value']);worst=min(worst,point['value']/high-1)
            require(abs(m['total_return']-total)<1e-11 and abs(m['max_drawdown']-worst)<1e-11,'Metric differs from published portfolio path')
    require(replay['passed'] and all(replay['checks'].values()),'Independent replay did not pass')
    require(replay['independent_run_count']==24 and replay['compared_day_count']==10560 and replay['compared_signal_record_count']==21600,'Incomplete independent replay')
    require(replay['summary_sha256']==digest(summary_path),'Independent replay belongs to another result')
    require(replay['config_sha256']==digest(config_path)==sensitivity['config_sha256'],'Configuration provenance mismatch')
    require(replay['input_sha256']==sensitivity['normalized_inputs_sha256'] and replay['output_sha256']==sensitivity['original_results_sha256'],'Sensitivity belongs to another run')
    require(replay['pre_acquisition_design_sha256']==digest(ROOT/'configs/stock-pilot.design-freeze.json'),'Design-freeze hash mismatch')
    require(replay['audit_policy_sha256']==digest(ROOT/'configs/stock-pilot-audit.v1.json'),'Audit policy hash mismatch')
    for file,expected_hash in replay['engine_code_sha256'].items():
        require(digest(ROOT/file)==expected_hash,'Run code changed after validation: '+file)
    require(digest(ROOT/'scripts/validate_stock_pilot_independent.py')==replay['verifier_code_sha256'],'Independent verifier changed')
    require(all(re.fullmatch('[0-9a-f]{64}',value) for value in replay['raw_source_hashes'].values()),'Invalid source hash')
    require(summary['metadata']['cohort_size']==100 and summary['metadata']['selected_count']==20,'Unexpected cohort/portfolio scope')
    audit=summary['metadata']['dataset_audit']
    require(audit['price_rows']==72522 and audit['capitalization_rows']==44000 and audit['missing_data_replacements']==0,'Unexpected data coverage')
    require(len(audit['sourced_price_reconstructions'])==1 and audit['sourced_price_reconstructions'][0]['symbol']=='FISV','Missing reconstruction disclosure')
    require([s['reconstructed_close_change'] for s in sensitivity['scenarios']]==[-.01,.01],'Incomplete repair sensitivity')
    require(all(s['strategy_paths']==16 and s['paths_with_changed_targets']==0 and s['max_relative_nav_change']==0 for s in sensitivity['scenarios']),'Repair sensitivity finding changed')
    print('PASS: 24 stock-pilot paths, 72 metric windows, independent replay hashes, reconstruction sensitivity and explicit scope.')


if __name__=='__main__':
    main()
