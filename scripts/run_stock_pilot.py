#!/usr/bin/env python3
"""Audit private stock inputs, run the frozen issuer pilot, export aggregates."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ingest_diagnostic import inspect_payload, request_spec
from stock_pilot.engine import run_matrix


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def rows(path):
    dt=read(path)['datatable']
    fields=[c['name'] for c in dt['columns']]
    return [dict(zip(fields,r)) for r in dt['data']]


def reconstruct_fisv(observations, error_codes, repair_file, calendar, actions):
    target='2025-11-12'
    indices=[i for i,row in enumerate(observations) if row['session_date']==target]
    if len(indices)!=1 or repair_file is None:
        raise ValueError('FISV daily gap requires the explicit sourced reconstruction')
    i=indices[0]
    expected={f'row_{i}:missing_or_invalid_{field}' for field in ('open','high','low','close','volume','adjclose')}
    if set(error_codes)!=expected or any(observations[i][f] is not None for f in ('open','high','low','close','volume','adjclose')):
        raise ValueError('FISV reconstruction cannot repair any other source errors')
    receipts_path=repair_file.parent/'receipts.json'
    receipts=read(receipts_path)
    candidates=[r for r in receipts if r.get('probe')=='FISV-60m']
    if len(candidates)!=1:
        raise ValueError('Missing unique intraday acquisition receipt')
    receipt=candidates[0]
    if (receipt.get('http_status')!=200 or receipt.get('file')!=repair_file.name
            or receipt.get('sha256')!=digest(repair_file) or receipt.get('bytes')!=repair_file.stat().st_size
            or not receipt.get('url','').startswith('https://query1.finance.yahoo.com/v8/finance/chart/FISV?')
            or 'interval=60m' not in receipt['url'] or 'includePrePost=false' not in receipt['url']):
        raise ValueError('Intraday file differs from the captured request receipt')
    document=read(repair_file)
    series=document['chart']['result'][0]
    if series['meta']['symbol']!='FISV' or series['meta']['currency']!='USD' or series['meta']['dataGranularity']!='1h':
        raise ValueError('Unexpected intraday reconstruction source')
    quote=series['indicators']['quote'][0]
    opening=int(calendar.session_open(target).timestamp())
    closing=int(calendar.session_close(target).timestamp())
    wanted=list(range(opening,closing,3600))
    selected=[j for j,t in enumerate(series['timestamp']) if opening<=t<closing]
    if [series['timestamp'][j] for j in selected]!=wanted:
        raise ValueError('Intraday reconstruction lacks the complete regular session')
    for j in selected:
        if any(not isinstance(quote[f][j],(int,float)) or not math.isfinite(quote[f][j]) or quote[f][j]<=0 for f in ('open','high','low','close')):
            raise ValueError('Invalid intraday price')
        if not quote['low'][j]<=min(quote['open'][j],quote['close'][j])<=max(quote['open'][j],quote['close'][j])<=quote['high'][j]:
            raise ValueError('Intraday OHLC bounds failed')
    ratios=[r['adjclose']/r['close'] for r in observations if r['close'] is not None]
    if not ratios or any(abs(value-1)>1e-12 for value in ratios):
        raise ValueError('Reconstruction requires verified unit adjustment ratio')
    economic=[r for r in actions if r['ticker']=='FISV' and r['date']==target and r['action'] in ('split','dividend','spinoff','spinoffdividend')]
    if economic:
        raise ValueError('Economic action prevents the unit-factor reconstruction')
    replacement={'open':quote['open'][selected[0]],'high':max(quote['high'][j] for j in selected),
                 'low':min(quote['low'][j] for j in selected),'close':quote['close'][selected[-1]],
                 'adjclose':quote['close'][selected[-1]]}
    observations[i].update(replacement)
    return {'symbol':'FISV','date':target,'hourly_bars':len(selected),
        'source_sha256':digest(repair_file),'quarantined_out_of_session_rows':len(series['timestamp'])-len(selected),
        'acquisition_receipts_sha256':digest(receipts_path),
        'adjustment_factor':1,'official_closing_auction_verified':False,
        'original_daily_null_row_preserved':True,'volume_not_used':True}


def audit_inputs(config, sharadar, yahoo, membership_snapshot, membership_events, repair_file=None):
    import exchange_calendars as xc
    if xc.__version__!='4.11.2':
        raise ValueError('Expected exchange_calendars 4.11.2')
    source=read(sharadar/'manifest.json')
    freeze_path=ROOT/'configs/stock-pilot.design-freeze.json'
    freeze=read(freeze_path)
    if source['config_sha256']!=digest(freeze_path):
        raise ValueError('Original design freeze does not match paid-data capture')
    # The source audit corrected one descriptive label after discovering that
    # Yahoo Close also embeds spin-off adjustments. No numeric rule changed.
    computational={k:v for k,v in config.items() if k not in ('signal_price','definition_correction')}
    frozen_computational={k:v for k,v in freeze.items() if k!='signal_price'}
    if computational!=frozen_computational:
        raise ValueError('Computational rules differ from the pre-acquisition freeze')
    extracted={}
    for item in source['captures']:
        path=sharadar/item['file']
        if path.is_symlink() or digest(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('Paid response integrity check failed')
        document=read(path)
        table=document['datatable']
        fields=[c['name'] for c in table['columns']]
        if len(fields)!=len(set(fields)) or any(len(row)!=len(fields) for row in table['data']):
            raise ValueError('Malformed paid response columns')
        if len(table['data'])!=item['rows']:
            raise ValueError('Paid response row count differs from receipt')
        extracted.setdefault(item['label'],[]).extend(dict(zip(fields,row)) for row in table['data'])
        if bool(document.get('meta',{}).get('next_cursor_id'))!=item['has_next_page']:
            raise ValueError('Paid response pagination differs from receipt')
    def captured(prefix):
        return [r for label,records in extracted.items() if label.startswith(prefix) for r in records]
    cohort=read(sharadar/'cohort.json')
    basecaps=captured('baseline-caps-')
    metadata=captured('metadata-')
    for name,records in [('baseline-caps.json',basecaps),('baseline-metadata.json',metadata),
                         ('capitalizations.json',captured('cohort-caps-')),('actions.json',captured('cohort-actions'))]:
        if read(sharadar/name)!=records:
            raise ValueError('Derived paid input differs from hashed source responses')
    initial_rows=rows(membership_snapshot)
    initial_tickers={r['ticker'] for r in initial_rows}
    if len(initial_tickers)!=len(initial_rows) or {r['ticker'] for r in metadata}!=initial_tickers:
        raise ValueError('Baseline metadata must cover the complete historical membership snapshot')
    known_classes={'GOOG':'GOOGL','FOX':'FOXA','NWS':'NWSA'}
    missing_caps=initial_tickers-{r['ticker'] for r in basecaps}
    if any(known_classes.get(t) not in {r['ticker'] for r in basecaps} for t in missing_caps):
        raise ValueError('Unexplained baseline market-cap gap')
    if len({r['ticker'] for r in basecaps})!=len(basecaps) or any(r['ticker'] not in initial_tickers or r['date']!=config['cohort']['baseline'] or not isinstance(r['marketcap'],(int,float)) or not math.isfinite(r['marketcap']) or r['marketcap']<=0 for r in basecaps):
        raise ValueError('Invalid, duplicate or off-baseline cap source')
    cap_lookup={r['ticker']:r for r in basecaps}
    expected=sorted(basecaps,key=lambda r:(-r['marketcap'],r['ticker']))[:config['cohort']['size']]
    if [r['ticker'] for r in expected]!=[r['ticker'] for r in cohort]:
        raise ValueError('Cohort differs from baseline ranking; no replacements permitted')
    if len({r['security_id'] for r in cohort})!=len(cohort):
        raise ValueError('Duplicate cohort security identifiers')
    if any(r['baseline_marketcap_usd']!=cap_lookup[r['ticker']]['marketcap']*1_000_000 for r in cohort):
        raise ValueError('Cohort baseline cap differs from source')
    source_meta={r['ticker']:r for r in metadata}
    if len(source_meta)!=len(metadata):
        raise ValueError('Duplicate baseline security metadata')
    for rank,row in enumerate(cohort,1):
        expected_record={**source_meta[row['ticker']], 'security_id':str(source_meta[row['ticker']]['permaticker']),
                         'baseline_rank':rank,'baseline_marketcap_usd':cap_lookup[row['ticker']]['marketcap']*1_000_000}
        if row!=expected_record:
            raise ValueError('Cohort identity or listing metadata differs from captured source')
    calendar=xc.get_calendar('XNYS',start=config['request_start'],end=config['report_end'])
    sessions=[d.strftime('%Y-%m-%d') for d in calendar.sessions]
    expected_dates=set(sessions)
    current=set(initial_tickers)
    if any(r['date']!=config['initial_signal'] or r['action']!='historical' for r in rows(membership_snapshot)):
        raise ValueError('Invalid initial membership snapshot')
    events=sorted([r for r in rows(membership_events) if config['initial_signal']<r['date']<=config['report_end']],key=lambda r:(r['date'],r['action'],r['ticker']))
    by_ticker={r['ticker']:r for r in cohort}
    membership={}
    pointer=0
    for day in sessions:
        while pointer<len(events) and events[pointer]['date']<=day:
            event=events[pointer]
            if event['action']=='added':
                if event['ticker'] in current:
                    raise ValueError('Membership adds an existing member')
                current.add(event['ticker'])
            elif event['action']=='removed':
                if event['ticker'] not in current:
                    raise ValueError('Membership removes a nonmember')
                current.remove(event['ticker'])
            pointer+=1
        membership[day]=sorted(by_ticker[t]['security_id'] for t in current if t in by_ticker)
    caps={r['security_id']:{} for r in cohort}
    for row in read(sharadar/'capitalizations.json'):
        security=by_ticker[row['ticker']]['security_id']
        if row['date'] in caps[security] or not isinstance(row['marketcap'],(int,float)) or not math.isfinite(row['marketcap']) or row['marketcap']<=0:
            raise ValueError('Duplicate or invalid cap observation')
        caps[security][row['date']]=row['marketcap']*1_000_000
    cap_dates={day for day in sessions if day>=config['initial_signal']}
    if any(set(values)!=cap_dates for values in caps.values()):
        raise ValueError('Historical capitalization has missing or extra sessions')
    security={r['security_id']:{'ticker':r['ticker'],'issuer_id':r['security_id'],'listed_from':r['firstpricedate']} for r in cohort}
    symbols={r['ticker'].replace('.','-'):r['security_id'] for r in cohort}
    symbols.update({b:b for b in config['benchmarks']})
    actions=captured('cohort-actions')
    bars={}
    price_audits=[]
    extremes=[]
    repairs=[]
    for symbol,identifier in sorted(symbols.items()):
        record=read(yahoo/(symbol+'.capture.json'))
        path=yahoo/(symbol+'.json')
        if path.is_symlink() or digest(path)!=record['sha256']:
            raise ValueError(f'{symbol}: price capture failed integrity checks')
        spec=request_spec([symbol],config['request_start'],config['report_end'])
        if record['request']!=spec:
            raise ValueError('Price request identity mismatch')
        report,observations,event_rows,_=inspect_payload(path.read_bytes(),symbol,spec)
        original_errors=list(report['errors'])
        if report['errors'] and symbol=='FISV':
            repairs.append(reconstruct_fisv(observations,report['errors'],repair_file,calendar,actions))
        elif report['errors'] or record.get('status')!='passed':
            raise ValueError(f'{symbol}: invalid price source')
        seen={r['session_date'] for r in observations}
        if seen!=expected_dates:
            # This frozen cohort is fully listed at the warmup start. Missing
            # dates are not silently reclassified as IPO or liquidity gaps.
            raise ValueError(f'{symbol}: incomplete common-session price coverage')
        values={}
        previous=None
        for row in observations:
            ratio=row['adjclose']/row['close']
            values[row['session_date']]={'signal_close':row['close'],
                'adjusted_open':row['open']*ratio,'adjusted_close':row['adjclose']}
            if previous is not None and abs(row['adjclose']/previous-1)>.5:
                extremes.append({'symbol':symbol,'date':row['session_date']})
            previous=row['adjclose']
        bars[identifier]=values
        price_audits.append({'symbol':symbol,'rows':len(observations),'sha256':digest(path),
            'original_parser_error_count':len(original_errors),'sourced_reconstructions':int(bool(original_errors)),
            'missing_sessions':0,'extra_sessions':0,
            'first_date':min(seen),'last_date':max(seen),'event_counts':report['event_counts']})
    if extremes:
        raise ValueError('Adjusted return exceeds 50%; independent event audit required: '+str(extremes))
    terminal=[r for r in actions if r['action'] in ('delisted','acquisitioncash','acquisitionstock','mergerfrom')]
    if terminal:
        raise ValueError('Frozen cohort has terminal actions requiring separate settlement validation')
    audit={'passed':True,'scope':'fixed_baseline_issuer_stock_pilot_only','formal_protocol_compliant':False,
        'cohort_size':len(cohort),'initial_membership_size':len(rows(membership_snapshot)),
        'baseline_cap_records':len(basecaps),'baseline_metadata_records':len(metadata),
        'secondary_classes_excluded':read(sharadar/'secondary-classes.json'),
        'price_symbols':len(symbols),'stock_price_series':len(cohort),'benchmark_price_series':len(config['benchmarks']),
        'common_sessions':len(sessions),'price_rows':sum(x['rows'] for x in price_audits),
        'missing_price_sessions':0,'capitalization_rows':sum(len(v) for v in caps.values()),
        'membership_changes_in_holding_period':len(events),
        'cohort_membership_removals':sum(r['action']=='removed' and r['ticker'] in by_ticker for r in events),
        'actions':len(actions),'action_types':dict(Counter(r['action'] for r in actions)),
        'terminal_actions':len(terminal),'large_adjusted_returns':extremes,
        'sourced_price_reconstructions':repairs,
        'exchange_calendar':{'name':'XNYS','version':xc.__version__},'prices':price_audits,
        'paid_manifest_sha256':digest(sharadar/'manifest.json'),
        'membership_snapshot_sha256':digest(membership_snapshot),'membership_events_sha256':digest(membership_events),
        'selection_used_future_price_coverage':False,'missing_data_replacements':0,
        'all_source_prices_are_vendor_proxies':True,'historical_vintages_verified':False,
        'cash_payment_and_spinoff_entitlements_reconstructed':False}
    data={'sessions':sessions,'cohort':[r['security_id'] for r in cohort],
        'security':security,'bars':bars,'market_caps':caps,'membership_by_day':membership,
        'universe_exclusions':[]}
    return data,audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sharadar-dir',type=Path,required=True)
    parser.add_argument('--yahoo-dir',type=Path,required=True)
    parser.add_argument('--membership-snapshot',type=Path,required=True)
    parser.add_argument('--membership-events',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--publish-dir',type=Path)
    parser.add_argument('--fisv-intraday-source',type=Path)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    config=read(ROOT/'configs/stock-pilot.v1.json')
    data,audit=audit_inputs(config,args.sharadar_dir,args.yahoo_dir,args.membership_snapshot,args.membership_events,args.fisv_intraday_source)
    write(args.output_dir/'normalized-inputs.json',data)
    write(args.output_dir/'input-audit.json',audit)
    result=run_matrix(data,config)
    if not all(result['checks'].values()):
        raise ValueError('An engine accounting check failed')
    write(args.output_dir/'results.json',result)
    summary=result['summary']
    summary['metadata']={
        'title':'A fixed-cohort stock experiment','cohort_size':len(data['cohort']),
        'selected_count':config['slots'],'date_start':config['initial_signal'],
        'report_anchor':config['report_anchor'],'end':config['report_end'],
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'config_sha256':digest(ROOT/'configs/stock-pilot.v1.json'),
        'pre_acquisition_design_sha256':digest(ROOT/'configs/stock-pilot.design-freeze.json'),
        'audit_policy_sha256':digest(ROOT/'configs/stock-pilot-audit.v1.json'),
        'code_sha256':{p:digest(ROOT/p) for p in ['stock_pilot/engine.py','scripts/run_stock_pilot.py','spmo_lab/signals.py','pilot/engine.py']},
        'limitations':[
            'Fixed 100 largest baseline issuers, selecting 20; not the original 75-stock historical-universe experiment.',
            'Cohort selected with 2024-12-31 capitalization before future price coverage or portfolio returns were inspected; no replacements.',
            'Historical DAILY issuer capitalization is a downloaded snapshot, not a certified point-in-time vintage.',
            'One Sharadar fundamental share-class representative per issuer; no issuer cap duplicated across share classes.',
            'Membership effective dates are treated as known by that close; original announcement timestamps are not verified.',
            'Yahoo Close contains corporate-action adjustments, including composite spin-off ratios; the signal is not a verified split-only series.',
            'Adjusted OHLC supplies a vendor-price portfolio proxy, not verified raw-share total returns or payment-date cash accounting.',
            'Spin-off adjustment and entitlement completeness are not independently validated.',
            'One FISV daily-null row is reconstructed from seven observed hourly bars; the official closing auction is not independently verified.',
            'The short 2025–2026 window cannot establish long-run superiority or an investable capacity claim.'
        ],
        'dataset_audit':{k:v for k,v in audit.items() if k!='prices'},
    }
    nav={'data_track':config['data_track'],'formal_protocol_compliant':False,'series':[
        {'run_id':run['run_id'],'strategy_id':run['strategy_id'],'cost_bps_per_side':run['cost_bps_per_side'],
         'points':[{'date':row['session'],'value':100*row['nav']/run['daily'][0]['nav']} for row in run['daily']]}
        for run in result['runs']+result['benchmarks']]}
    write(args.output_dir/'summary.json',summary)
    write(args.output_dir/'nav.json',nav)
    if args.publish_dir:
        args.publish_dir.mkdir(parents=True,exist_ok=True)
        for name,value in [('stock-pilot-summary.json',summary),('stock-pilot-nav.json',nav)]:
            # Public export contains derived portfolio values and aggregate
            # coverage, never source quotes, caps, credentials or account data.
            (args.publish_dir/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'private_results':str(args.output_dir),'cohort':len(data['cohort']),
        'strategy_runs':len(result['runs']),'benchmark_runs':len(result['benchmarks']),
        'checks':result['checks'],'comparisons':result['comparisons']},indent=2))


if __name__=='__main__':
    main()
