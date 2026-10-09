#!/usr/bin/env python3
"""Run the separately frozen sector ETF experiment from a preserved market snapshot."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.etf_pilot_data import acquire, load_and_audit
from pilot.engine import run_matrix


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def sha(content):
    return hashlib.sha256(content).hexdigest()


def write_csv(path, rows):
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('x', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key:json.dumps(value,sort_keys=True) if isinstance(value,(list,dict)) else value for key,value in row.items()} for row in rows)


def run(raw_dir, output_root, public_dir=None):
    config_path=ROOT/'configs/sector-etf-pilot.v1.json'
    config_bytes=config_path.read_bytes();config=json.loads(config_bytes)
    source_paths=[ROOT/'pilot/engine.py',ROOT/'pilot/__init__.py',Path(__file__),ROOT/'scripts/etf_pilot_data.py',ROOT/'spmo_lab/signals.py']
    source_hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in source_paths}
    if raw_dir is None:
        raw_dir=acquire(config)
    data,audit=load_and_audit(Path(raw_dir),config)
    if not audit['passed'] or data is None:
        raise RuntimeError('Market-data audit failed: '+json.dumps(audit.get('errors',[])))
    result=run_matrix(data,config)
    if config_path.read_bytes()!=config_bytes or any(sha((ROOT/name).read_bytes())!=digest for name,digest in source_hashes.items()):
        raise RuntimeError('Code or configuration changed during execution; rerun a stable version.')
    assert len(result['runs'])==56 and len(result['benchmarks'])==4
    assert len(result['comparisons']['full_period'])==48
    assert all(result['checks'].values()),result['checks']
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:12]
    directory=Path(output_root)/run_id;directory.mkdir(parents=True,exist_ok=False)
    (directory/'data-audit.json').write_bytes(encoded(audit))
    (directory/'input-data.json.gz').write_bytes(gzip.compress(encoded(data),mtime=0))
    for run in result['runs']+result['benchmarks']:
        (directory/(run['run_id']+'.json.gz')).write_bytes(gzip.compress(encoded(run),mtime=0))
    for period,rows in result['comparisons'].items():
        write_csv(directory/('comparisons-'+period+'.csv'),rows)
    metric_rows=[{'run_id':run['run_id'],'arm':run['arm'],'signal':run['signal'],'schedule':run['schedule'],
                 'phase':run['phase'],'cost_bps_per_side':run['cost_bps_per_side'],'metrics':{key:value for key,value in run['metrics'].items() if key!='annual'}}
                for run in result['runs']+result['benchmarks']]
    summary={'schema_version':1,'experiment_id':config['experiment_id'],'run_id':run_id,
             'generated_at_utc':datetime.now(timezone.utc).isoformat(),
             'status':'completed_with_caveats','data_track':config['data_track'],
             'market_pilot_executed':True,'original_stock_experiment_completed':False,
             'scope':config['scope'],'source':'Yahoo chart API; preserved adjusted-price snapshot',
             'config_sha256':sha(config_bytes),'code_sha256':source_hashes,
             'boundaries':result['boundaries'],'checks':result['checks'],'audit':audit,
             'run_count':56,'benchmark_run_count':4,'paired_comparison_count':48,
             'primary':result['primary'],'runs':metric_rows,
             'comparisons':{key:value for key,value in result['comparisons'].items() if key!='annual'},
             'primary_annual':[row for row in result['comparisons']['annual'] if row['signal']=='12-1' and row['phase']==[3,9] and row['cost_bps_per_side']==5],
             'limitations':config['limitations']}
    # Publish derived portfolio data only, never the vendor's ETF bars.
    selected_ids={'M12-5bps','S12-03-09-5bps','MMIX-5bps','SMIX-03-09-5bps','SPY-5bps'}
    summary['portfolio_paths']={}
    start=result['boundaries']['report_anchor_on_or_before']
    finish=result['boundaries']['full_year_end_on_or_before']
    for run in result['runs']+result['benchmarks']:
        if run['run_id'] not in selected_ids: continue
        period=[row for row in run['daily'] if start<=row['session']<=finish]
        anchor=period[0]['nav'];peak=anchor;points=[]
        for index,row in enumerate(period):
            peak=max(peak,row['nav'])
            if index==0 or index==len(period)-1 or row['session'][:7]!=period[index+1]['session'][:7]:
                points.append({'session':row['session'],'wealth':row['nav']/anchor,'drawdown':row['nav']/peak-1})
        summary['portfolio_paths'][run['run_id']]=points
    (directory/'summary.json').write_bytes(encoded(summary))
    manifest={'run_id':run_id,'raw_dir':str(Path(raw_dir).resolve()),'raw_manifest_sha256':sha((Path(raw_dir)/'manifest.json').read_bytes()),
              'config_sha256':sha(config_bytes),'code_sha256':source_hashes,
              'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'file_sha256':{p.name:sha(p.read_bytes()) for p in sorted(directory.iterdir()) if p.is_file()}}
    (directory/'manifest.json').write_bytes(encoded(manifest))
    if public_dir:
        public_dir=Path(public_dir);public_dir.mkdir(parents=True,exist_ok=True)
        (public_dir/'etf-pilot-summary.json').write_bytes(encoded(summary))
        for period in result['comparisons']:
            (public_dir/('etf-pilot-'+period+'.csv')).write_bytes((directory/('comparisons-'+period+'.csv')).read_bytes())
    return {'run_dir':str(directory),'raw_dir':str(raw_dir),'run_count':56,'benchmark_count':4,
            'checks_passed':len(result['checks']),'market_pilot_executed':True,'original_stock_experiment_completed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/generated/etf-pilot')
    parser.add_argument('--public-dir',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.raw_dir,args.output_dir,args.public_dir)))

if __name__=='__main__':main()
