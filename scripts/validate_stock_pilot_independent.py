#!/usr/bin/env python3
"""Independently replay a preserved stock pilot, without project-code imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TOL = 2e-10


def require(ok, message):
    if not ok:
        raise ValueError(message)


def close(a, b, message):
    require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= TOL * max(1, abs(a), abs(b)), message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def analytic_rebalance(cash, units, opening, weights, bps):
    """Solve each linear interval of the absolute-notional fee equation."""
    names = set(units) | set(weights)
    old = {s: units.get(s, 0) * opening[s] for s in names}
    before = cash + sum(old.values())
    rate = bps / 10000
    breaks = sorted({0., before, *[old[s]/weights[s] for s in names if weights.get(s,0) and 0 < old[s]/weights[s] < before]})
    after = None
    for lower, upper in zip(breaks, breaks[1:]):
        midpoint = (lower+upper)/2
        signs = {s: 1 if weights.get(s,0)*midpoint >= old[s] else -1 for s in names}
        candidate = (before + rate*sum(signs[s]*old[s] for s in names))/(1+rate*sum(signs[s]*weights.get(s,0) for s in names))
        if lower - 1e-8 <= candidate <= upper + 1e-8:
            after = candidate
            break
    require(after is not None, 'analytic fee root missing')
    values = {s: w*after for s,w in weights.items() if w > 0}
    traded = sum(abs(values.get(s,0)-old[s]) for s in names)
    fee = rate*traded
    remainder = before-fee-sum(values.values())
    if abs(remainder) < before*1e-12:
        remainder = 0.
    require(remainder >= 0, 'independent negative cash')
    return remainder, {s:v/opening[s] for s,v in values.items()}, before, fee, traded


def calculate_decision(data, config, strategy, index):
    """Direct sample-variance calculation and independent capped allocation."""
    day = data['sessions'][index]
    weights = config['arms'][strategy]['signal_weights']
    scores, components, reasons = {}, {}, {}
    enabled = [n for n,w in zip(config['lookbacks'],weights) if w]
    for security in sorted(data['membership_by_day'][day]):
        metadata = data['security'][security]
        listed = metadata.get('listed_from')
        parts = [None] * len(weights)
        reason, total = None, 0.
        if listed is not None and listed > data['sessions'][index-max(enabled)]:
            reason = 'insufficient_listing_history'
        else:
            for component, (lookback, coefficient) in enumerate(zip(config['lookbacks'],weights)):
                if not coefficient:
                    continue
                start, end = index-lookback, index-config['skip']
                prices = [data['bars'][security][d]['signal_close'] for d in data['sessions'][start:end+1]]
                require(all(math.isfinite(p) and p>0 for p in prices), 'invalid required signal price')
                changes = [b/a-1 for a,b in zip(prices,prices[1:])]
                mean = sum(changes)/len(changes)
                sd = math.sqrt(sum((r-mean)**2 for r in changes)/(len(changes)-1))
                if sd == 0:
                    reason = 'zero_volatility'
                    continue
                parts[component] = (prices[-1]/prices[0]-1)/(sd*math.sqrt(config['annualization']))
                total += coefficient*parts[component]
            if reason is None and total <= 0:
                reason = 'nonpositive_score'
        scores[security] = total if reason is None else None
        components[security], reasons[security] = parts, reason
        require(math.isfinite(data['market_caps'][security][day]) and data['market_caps'][security][day]>0, 'missing or invalid exact-date market cap')
    ranked = sorted((s for s,v in scores.items() if v is not None), key=lambda s:(-scores[s],s))
    selected = ranked[:config['slots']]
    raw = {s:scores[s]*math.sqrt(data['market_caps'][s][day]) for s in selected}
    cap = config['cap']
    if len(raw)*cap <= 1:
        targets = {s:cap for s in raw}
    elif raw:
        # Solve sum(min(cap, lambda * raw_weight)) = 1 by monotone bisection,
        # independently of the engine's iterative cap-and-redistribute method.
        lo, hi = 0., max(1/v for v in raw.values())
        for _ in range(100):
            middle = (lo+hi)/2
            if sum(min(cap,middle*v) for v in raw.values()) > 1:
                hi = middle
            else:
                lo = middle
        targets = {s:min(cap,lo*v) for s,v in raw.items()}
    else:
        targets = {}
    return targets, scores, components, reasons, {s:i+1 for i,s in enumerate(ranked)}


def replay(data, config, run, cache):
    sessions = data['sessions']
    first, last = sessions.index(config['initial_signal']), sessions.index(config['report_end'])
    cash, units, pending = config['initial_cash'], {}, None
    strategy, bps = run['strategy_id'], run['cost_bps_per_side']
    benchmark = strategy in config['benchmarks']
    old_members = set(data['membership_by_day'][sessions[first]])
    rows, events = [], []
    actual_signals = {(r['decision_session'],r['security_id']):r for r in run['signals']}
    require(len(actual_signals)==len(run['signals']), 'duplicate decision record')
    signal_checks = 0
    for index in range(first,last+1):
        day = sessions[index]
        forced = set() if benchmark else set(units)-old_members
        if pending is not None or forced:
            target, decision_day = pending if pending is not None else (None,sessions[index-1])
            opening = {s:data['bars'][s][day]['adjusted_open'] for s in set(units)|set(target or {})}
            if target is not None:
                target = {s:w for s,w in target.items() if s not in forced}
                cash, units, before, fee, traded = analytic_rebalance(cash,units,opening,target,bps)
            else:
                before = cash+sum(n*opening[s] for s,n in units.items())
                traded = sum(units[s]*opening[s] for s in forced)
                fee = traded*bps/10000
                cash += traded-fee
                units = {s:n for s,n in units.items() if s not in forced}
            events.append((day,decision_day,before,fee,traded))
            pending = None
        values = {s:n*data['bars'][s][day]['adjusted_close'] for s,n in units.items()}
        nav = cash+sum(values.values())
        issuer_values = {}
        for s,value in values.items():
            issuer = data['security'].get(s,{}).get('issuer_id',s)
            issuer_values[issuer] = issuer_values.get(issuer,0)+value
        rows.append({'session':day,'nav':nav,'cash':cash,'positions':dict(units),
                     'max_security_weight':max(values.values(),default=0)/nav,
                     'max_issuer_weight':max(issuer_values.values(),default=0)/nav})
        month_end = index < last and day[:7]!=sessions[index+1][:7]
        scheduled = index==first or (not benchmark and month_end and (config['arms'][strategy]['frequency']=='monthly' or int(day[5:7]) in config['semiannual_months']))
        if scheduled and index<last:
            if benchmark:
                target = {strategy:1.}
            else:
                key = (strategy,index)
                if key not in cache:
                    cache[key] = calculate_decision(data,config,strategy,index)
                target,scores,components,reasons,ranks = cache[key]
                for s,score in scores.items():
                    record = actual_signals.pop((day,s))
                    for field,value in [('ticker',data['security'][s]['ticker']),('issuer_id',data['security'][s]['issuer_id']),('reason',reasons[s]),('rank',ranks.get(s)),('market_cap_date',day),('membership_observation_date',day),('listed_from',data['security'][s].get('listed_from'))]:
                        require(record[field]==value,f'{strategy}/{day}/{s}: {field} differs')
                    if score is None:
                        require(record['score'] is None,'invalid score exclusion')
                    else:
                        close(score,record['score'],'score differs')
                    for expected,actual in zip(components[s],record['components']):
                        if expected is None: require(actual is None,'disabled/invalid signal component differs')
                        else: close(expected,actual,'momentum component differs')
                    close(record['market_cap_usd'],data['market_caps'][s][day],'capitalization differs')
                    close(record['target_weight'],target.get(s,0),'capped target differs')
                    signal_checks += 1
            pending = dict(target),day
        old_members = set(data['membership_by_day'][day])
    require(not actual_signals,'unexpected signal rows')
    require(len(rows)==len(run['daily']),'daily count differs')
    errors = {'max_relative_nav_error':0.,'max_absolute_cash_error':0.,'max_relative_position_error':0.}
    for expected,actual in zip(rows,run['daily']):
        require(expected['session']==actual['session'],'daily date differs')
        close(expected['nav'],actual['nav'],'NAV differs')
        require(abs(expected['cash']-actual['cash']) <= TOL*expected['nav'],'cash differs beyond NAV-scaled rounding tolerance')
        close(expected['max_security_weight'],actual['max_security_weight'],'security weight differs')
        close(expected['max_issuer_weight'],actual['max_issuer_weight'],'issuer weight differs')
        require(set(expected['positions'])==set(actual['positions']),'held security IDs differ')
        for s,n in expected['positions'].items():
            close(n,actual['positions'][s],'adjusted units differ')
            errors['max_relative_position_error']=max(errors['max_relative_position_error'],abs(n-actual['positions'][s])/max(1,abs(n)))
        errors['max_relative_nav_error']=max(errors['max_relative_nav_error'],abs(expected['nav']-actual['nav'])/expected['nav'])
        errors['max_absolute_cash_error']=max(errors['max_absolute_cash_error'],abs(expected['cash']-actual['cash']))
    actual_events = {t['session']:t for t in run['trades']}
    by_day={row['session']:row for row in rows}
    require(len(actual_events)==len(run['trades']),'multiple unexpected same-session events')
    expected_events = [e for e in events if e[4]>1e-6]
    require(len(expected_events)==len(actual_events),'execution event count differs')
    order_count = 0
    for day,signal,before,fee,traded in expected_events:
        actual = actual_events[day]
        require(signal==actual['decision_session'] and sessions.index(day)==sessions.index(signal)+1,'next-session timing failed')
        for value,field in [(before,'pretrade_nav'),(before-fee,'posttrade_nav'),(fee,'cost'),(traded,'traded_notional'),(traded/before,'turnover')]:
            close(value,actual[field],f'execution {field} differs')
        for order in actual['orders']:
            s = order['security_id']
            price = data['bars'][s][day]['adjusted_open']
            close(price,order['adjusted_price'],'execution price differs')
            close(order['adjusted_units']*price,order['signed_notional'],'order notional differs')
            close(abs(order['adjusted_units']),order['quantity'],'order quantity differs')
            close(abs(order['signed_notional']),order['notional'],'absolute notional differs')
            close(order['notional']*bps/10000,order['cost'],'per-order fee differs')
            require(order['side']==('buy' if order['adjusted_units']>0 else 'sell'),'order side differs')
            order_count+=1
        previous=by_day[sessions[sessions.index(day)-1]]
        current=by_day[day]
        deltas={o['security_id']:o['adjusted_units'] for o in actual['orders']}
        require(len(deltas)==len(actual['orders']),'duplicate security orders')
        for security in set(previous['positions'])|set(current['positions'])|set(deltas):
            close(current['positions'].get(security,0)-previous['positions'].get(security,0),deltas.get(security,0),'order units do not reconcile held units')
        close(sum(o['notional'] for o in actual['orders']),actual['traded_notional'],'order notional sum differs')
        close(sum(o['cost'] for o in actual['orders']),actual['cost'],'order fee sum differs')
        expected_cash=previous['cash']-sum(o['signed_notional'] for o in actual['orders'])-actual['cost']
        require(abs(expected_cash-current['cash'])<=TOL*current['nav'],'orders do not reconcile cash')
    check_metrics(rows,events,run,config)
    if benchmark:
        initial=data['bars'][strategy][config['report_anchor']]['adjusted_close']
        terminal=data['bars'][strategy][config['report_end']]['adjusted_close']
        close(terminal/initial-1,run['metrics']['ytd2026']['total_return'],'benchmark hold identity differs')
    return {**errors,'run_id':run['run_id'],'daily_count':len(rows),'signal_record_count':signal_checks,'execution_event_count':len(expected_events),'order_count':order_count}


def check_metrics(rows,events,run,config):
    for name,start,end in [('year2025',config['initial_signal'],config['report_anchor']),('ytd2026',config['report_anchor'],config['report_end']),('full_period',config['initial_signal'],config['report_end'])]:
        selected=[r for r in rows if start<=r['session']<=end]
        fills=[r for r in events if start<r[0]<=end]
        peak,worst=selected[0]['nav'],0
        for row in selected:
            peak=max(peak,row['nav']);worst=min(worst,row['nav']/peak-1)
        expected={'start_nav':selected[0]['nav'],'end_nav':selected[-1]['nav'],'total_return':selected[-1]['nav']/selected[0]['nav']-1,'max_drawdown':worst,'transaction_cost':sum(r[3] for r in fills),'gross_traded_notional':sum(r[4] for r in fills),'two_sided_turnover':sum(r[4]/r[2] for r in fills),'mean_cash_weight':sum(r['cash']/r['nav'] for r in selected[1:])/(len(selected)-1)}
        for field,value in expected.items():close(value,run['metrics'][name][field],f'{name} metric {field} differs')
    close(run['metrics']['year2025']['end_nav'],run['metrics']['ytd2026']['start_nav'],'anchor reset')


def verify_sources(data,cfg,audit,args):
    raw_hashes={}
    paid=args.raw_dir/'sharadar-run1'
    manifest=read(paid/'manifest.json')
    require(digest(paid/'manifest.json')==audit['paid_manifest_sha256'],'paid manifest mismatch')
    freeze_path=ROOT/'configs/stock-pilot.design-freeze.json'
    require(manifest['config_sha256']==digest(freeze_path),'pre-acquisition frozen config mismatch')
    frozen=read(freeze_path)
    require({k:v for k,v in cfg.items() if k not in ('signal_price','definition_correction')}=={k:v for k,v in frozen.items() if k!='signal_price'},'computational config changed after acquisition')
    captured={}
    for capture in manifest['captures']:
        path=paid/capture['file'];require(digest(path)==capture['sha256'],'raw paid capture hash mismatch');raw_hashes['sharadar/'+path.name]=digest(path)
        table=read(path)['datatable'];columns=[c['name'] for c in table['columns']]
        captured.setdefault(capture['label'],[]).extend(dict(zip(columns,row)) for row in table['data'])
    def records(prefix):
        return [row for label,values in captured.items() if label.startswith(prefix) for row in values]
    for name,prefix in [('baseline-caps.json','baseline-caps-'),('baseline-metadata.json','metadata-'),('capitalizations.json','cohort-caps-'),('actions.json','cohort-actions')]:
        require(read(paid/name)==records(prefix),'derived paid records differ from hashed raw response')
    cohort=read(paid/'cohort.json')
    basecaps=read(paid/'baseline-caps.json')
    raw_metadata={r['ticker']:r for r in read(paid/'baseline-metadata.json')}
    require(len(raw_metadata)==len(read(paid/'baseline-metadata.json')),'duplicate raw metadata ticker')
    selected=sorted(basecaps,key=lambda r:(-r['marketcap'],r['ticker']))[:cfg['cohort']['size']]
    require([r['ticker'] for r in selected]==[r['ticker'] for r in cohort],'baseline cap rank differs')
    require([r['security_id'] for r in cohort]==data['cohort'],'normalized cohort differs')
    by_ticker={r['ticker']:r['security_id'] for r in cohort}
    for r in cohort:
        require(all(r[k]==raw_metadata[r['ticker']][k] for k in raw_metadata[r['ticker']]),'cohort metadata differs from raw record')
        require(r['security_id']==str(r['permaticker']),'security identifier differs from raw metadata')
        baseline=next(row for row in basecaps if row['ticker']==r['ticker'])
        require(baseline['date']==cfg['initial_signal'],'baseline uses wrong cap date')
        close(r['baseline_marketcap_usd'],baseline['marketcap']*1000000,'baseline capitalization differs')
        require(data['security'][r['security_id']]=={'ticker':r['ticker'],'issuer_id':r['security_id'],'listed_from':r['firstpricedate']},'security metadata differs')
    for r in read(paid/'capitalizations.json'):
        close(data['market_caps'][by_ticker[r['ticker']]][r['date']],r['marketcap']*1000000,'normalized historical cap differs')
    for item in audit['prices']:
        path=args.raw_dir/'yahoo-run1'/(item['symbol']+'.json');require(digest(path)==item['sha256'],'raw price capture mismatch');raw_hashes['yahoo/'+path.name]=digest(path)
        identifier=next((s for s,metadata in data['security'].items() if metadata['ticker'].replace('.','-')==item['symbol']),item['symbol'])
        source=read(path)['chart']['result'][0];quote=source['indicators']['quote'][0];adjusted=source['indicators']['adjclose'][0]['adjclose']
        observed=set()
        for i,timestamp in enumerate(source['timestamp']):
            day=datetime.fromtimestamp(timestamp,ZoneInfo('America/New_York')).date().isoformat()
            if day not in data['sessions']:continue
            require(day not in observed,'duplicate raw session');observed.add(day)
            if quote['close'][i] is None:
                require(item['symbol']=='FISV' and day=='2025-11-12','unexplained missing daily quote')
                continue
            actual=data['bars'][identifier][day]
            close(actual['signal_close'],quote['close'][i],'normalized signal price differs from raw')
            close(actual['adjusted_close'],adjusted[i],'normalized adjusted close differs from raw')
            close(actual['adjusted_open'],quote['open'][i]*adjusted[i]/quote['close'][i],'normalized adjusted open differs from raw')
        require(observed==set(data['sessions']),'raw calendar coverage differs')
    for label,expected in [('membership_snapshot',audit['membership_snapshot_sha256']),('membership_events',audit['membership_events_sha256'])]:
        found=None
        candidates=list((ROOT/'data/processed').rglob('*membership*.json'))+list((ROOT/'data/raw').rglob('*membership*.json'))
        for p in candidates:
            if digest(p)==expected:found=p;break
        require(found is not None,f'{label} raw source not found')
        raw_hashes[label]=expected
        table=read(found)['datatable'];fields=[c['name'] for c in table['columns']];records=[dict(zip(fields,row)) for row in table['data']]
        if label=='membership_snapshot':members={r['ticker'] for r in records}
        else:changes=sorted((r for r in records if cfg['initial_signal']<r['date']<=cfg['report_end']),key=lambda r:(r['date'],r['action'],r['ticker']))
    for day in data['sessions']:
        for event in [e for e in changes if e['date']==day]:
            if event['action']=='added':members.add(event['ticker'])
            elif event['action']=='removed':members.remove(event['ticker'])
        expected={by_ticker[s] for s in members if s in by_ticker}
        require(expected==set(data['membership_by_day'][day]),'normalized membership differs')
    for reconstruction in audit.get('sourced_price_reconstructions',[]):
        matches=[p for p in args.raw_dir.rglob('*.json') if digest(p)==reconstruction['source_sha256']]
        require(matches,'reconstruction raw source missing')
        raw_hashes['reconstruction/'+reconstruction['symbol']]=reconstruction['source_sha256']
        source=read(matches[0])['chart']['result'][0];quote=source['indicators']['quote'][0]
        selected=[i for i,t in enumerate(source['timestamp']) if datetime.fromtimestamp(t,ZoneInfo('America/New_York')).date().isoformat()==reconstruction['date'] and '09:30'<=datetime.fromtimestamp(t,ZoneInfo('America/New_York')).strftime('%H:%M')<'16:00']
        require(len(selected)==7,'reconstructed regular session is incomplete')
        require([source['timestamp'][i+1]-source['timestamp'][i] for i in selected[:-1]]==[3600]*6,'reconstructed hourly bars are not contiguous')
        identifier=by_ticker[reconstruction['symbol']];actual=data['bars'][identifier][reconstruction['date']]
        close(actual['adjusted_open'],quote['open'][selected[0]],'reconstructed opening price differs')
        close(actual['adjusted_close'],quote['close'][selected[-1]],'reconstructed close differs')
        close(actual['signal_close'],quote['close'][selected[-1]],'reconstructed signal price differs')
    return raw_hashes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,default=ROOT/'data/processed/stock-pilot/run2')
    p.add_argument('--config',type=Path,default=ROOT/'configs/stock-pilot.v1.json')
    p.add_argument('--raw-dir',type=Path,default=ROOT/'data/raw/stock-pilot')
    p.add_argument('--public-summary',type=Path,default=ROOT/'site/data/stock-pilot-validation.json')
    args=p.parse_args()
    data=read(args.run_dir/'normalized-inputs.json');cfg=read(args.config);result=read(args.run_dir/'results.json');audit=read(args.run_dir/'input-audit.json');summary=read(args.run_dir/'summary.json')
    require(cfg['formal_protocol_compliant'] is False and result['formal_protocol_compliant'] is False and summary['formal_protocol_compliant'] is False,'invalid formal-compliance claim')
    require(audit['passed'] and not audit['selection_used_future_price_coverage'] and audit['missing_data_replacements']==0,'input audit status invalid')
    require(data['sessions']==sorted(set(data['sessions'])) and data['sessions'][-1]==cfg['report_end'],'calendar boundaries invalid')
    import exchange_calendars as xc
    require(xc.__version__=='4.11.2','exchange calendar version differs')
    calendar=xc.get_calendar('XNYS',start=cfg['request_start'],end=cfg['report_end'])
    require(data['sessions']==[d.strftime('%Y-%m-%d') for d in calendar.sessions],'input sessions differ from exchange calendar')
    require(len(data['cohort'])==len(set(data['cohort']))==100,'cohort count invalid')
    require(len(result['runs'])==16 and len(result['benchmarks'])==8,'path count invalid')
    expected={(s,c) for s in [*cfg['arms'],*cfg['benchmarks']] for c in cfg['costs']}
    all_runs=result['runs']+result['benchmarks']
    require({(r['strategy_id'],r['cost_bps_per_side']) for r in all_runs}==expected,'incomplete matrix')
    for file,expected_hash in summary['metadata']['code_sha256'].items():require(digest(ROOT/file)==expected_hash,'frozen engine code differs')
    raw_hashes=verify_sources(data,cfg,audit,args)
    cache={};reports=[replay(data,cfg,run,cache) for run in all_runs]
    for run in all_runs:
        require(run['formal_protocol_compliant'] is False,'run overstates scope')
        target=next(r for r in summary['runs']+summary['benchmarks'] if r['run_id']==run['run_id'])
        require(target['metrics']==run['metrics'],'summary metrics differ')
    by_key={(r['strategy_id'],r['cost_bps_per_side']):r for r in all_runs}
    for row in result['comparisons']:
        values={s:by_key[(s,row['cost_bps_per_side'])]['metrics'][row['period']]['total_return'] for s in cfg['arms']}
        primary=100*(values['M12']-values['S12']);blend=100*(values['MMIX']-values['SMIX'])
        close(primary,row['primary_frequency_difference_pp'],'primary comparison differs');close(blend,row['replication_frequency_difference_pp'],'blend comparison differs');close(blend-primary,row['interaction_difference_pp'],'interaction differs')
    public_summary=ROOT/'site/data/stock-pilot-summary.json'
    require(digest(public_summary)==digest(args.run_dir/'summary.json'),'public summary differs')
    receipt={'schema_version':1,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,'data_track':cfg['data_track'],'formal_protocol_compliant':False,'scope':'independent_replay_of_fixed_baseline_issuer_stock_pilot','independent_run_count':len(reports),'compared_day_count':sum(r['daily_count'] for r in reports),'compared_signal_record_count':sum(r['signal_record_count'] for r in reports),'compared_order_count':sum(r['order_count'] for r in reports),'independent_decision_count':len(cache),'max_relative_nav_error':max(r['max_relative_nav_error'] for r in reports),'max_absolute_cash_error':max(r['max_absolute_cash_error'] for r in reports),'max_relative_position_error':max(r['max_relative_position_error'] for r in reports),'config_sha256':digest(args.config),'pre_acquisition_design_sha256':digest(ROOT/'configs/stock-pilot.design-freeze.json'),'audit_policy_sha256':digest(ROOT/'configs/stock-pilot-audit.v1.json'),'input_sha256':digest(args.run_dir/'normalized-inputs.json'),'output_sha256':digest(args.run_dir/'results.json'),'summary_sha256':digest(public_summary),'input_audit_sha256':digest(args.run_dir/'input-audit.json'),'engine_code_sha256':summary['metadata']['code_sha256'],'verifier_code_sha256':digest(__file__),'raw_source_hashes':raw_hashes,'checks':{'all_24_paths_independently_replayed':True,'all_signal_scores_ranks_and_capped_targets_recalculated':True,'baseline_ranking_metadata_and_dated_caps_match_sources':True,'dated_membership_matches_snapshot_and_events':True,'normalized_prices_and_reconstructed_quote_match_sources':True,'computational_design_unchanged_after_acquisition':True,'all_daily_nav_cash_positions_match':True,'all_orders_match_sourced_adjusted_open_and_fees':True,'execution_is_next_session':True,'metrics_and_paired_comparisons_match':True,'anchor_continues_existing_accounts':True,'source_input_output_code_hashes_bound':True,'formal_compliance_remains_false':True},'limitations':['Same preserved vendor inputs; not independent vendor-price verification.','Baseline issuer cohort, dated capitalization without certified availability vintage, and vendor-adjusted accounting remain pilot assumptions.','FISV reconstruction and spin-off cash/security entitlements remain explicitly qualified; no formal original-protocol acceptance.']}
    receipt['checks'].update({
        'exchange_calendar_has_exact_session_coverage': True,
        'order_quantities_and_cash_flows_reconcile_positions': True,
        'all_benchmark_hold_return_identities_match': True,
    })
    private={**receipt,'per_run':reports}
    (args.run_dir/'independent-validation.json').write_text(json.dumps(private,indent=2,sort_keys=True)+'\n')
    args.public_summary.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:receipt[k] for k in ['passed','independent_run_count','compared_day_count','compared_signal_record_count','compared_order_count','max_relative_nav_error','max_absolute_cash_error']},indent=2))


if __name__=='__main__':main()
