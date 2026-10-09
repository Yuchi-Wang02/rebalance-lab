"""Independently reconcile a preserved ETF pilot run without project imports.

The verifier recomputes signals and portfolio ledgers and uses a piecewise
analytic fee solution, rather than the engine's bisection. It validates a
preserved vendor snapshot; it does not independently certify vendor prices.
"""
import argparse
import bisect
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fee_target(cash, units, openings, selected, slots, bps):
    old = {s: u * openings[s] for s, u in units.items()}
    names = set(old) | set(selected)
    weights = {s: (1 / slots if s in selected else 0) for s in names}
    before = cash + sum(old.values())
    rate = bps / 10000
    points = sorted({0.0, before, *[old.get(s, 0) / w for s, w in weights.items() if w and 0 < old.get(s, 0) / w < before]})
    after = None
    for lower, upper in zip(points, points[1:]):
        midpoint = (lower + upper) / 2
        signs = {s: (1 if weights[s] * midpoint >= old.get(s, 0) else -1) for s in names}
        candidate = (before + rate * sum(signs[s] * old.get(s, 0) for s in names)) / (1 + rate * sum(signs[s] * weights[s] for s in names))
        if lower - 1e-8 <= candidate <= upper + 1e-8:
            after = candidate
            break
    require(after is not None, 'independent fee equation has no solution')
    values = {s: after / slots for s in selected}
    traded = sum(abs(values.get(s, 0) - old.get(s, 0)) for s in names)
    fee = rate * traded
    require(abs(before - fee - after) < 1e-7 * max(1, before), 'independent fee equation does not reconcile')
    remaining = before - fee - sum(values.values())
    if abs(remaining) < 1e-9 * before:
        remaining = 0.0
    return remaining, {s: values[s] / openings[s] for s in selected}, fee, traded / before


def scores_at(index, data, cfg, arm):
    end = index - cfg['signal']['skip']
    scores = {}
    for symbol in cfg['universe']:
        score = 0
        valid = True
        for lookback, coeff in zip(cfg['signal']['lookbacks'], cfg['arms'][arm]):
            if coeff == 0:
                continue
            start = index - lookback
            values = data['adjusted_close'][symbol]
            changes = [values[i] / values[i - 1] - 1 for i in range(start + 1, end + 1)]
            mean = sum(changes) / len(changes)
            sd = math.sqrt(sum((r - mean) ** 2 for r in changes) / (len(changes) - 1))
            if sd == 0:
                valid = False
                break
            score += coeff * (values[end] / values[start] - 1) / (sd * math.sqrt(cfg['signal']['annualization']))
        if valid and score > 0:
            scores[symbol] = score
    selected = sorted(scores, key=lambda symbol: (-scores[symbol], symbol))[:cfg['slots']]
    return selected


def replay(data, cfg, arm, phase, bps, benchmark=False):
    dates = data['sessions']
    initial = bisect.bisect_right(dates, cfg['initial_signal_on_or_before']) - 1
    end = bisect.bisect_right(dates, cfg['case_end_on_or_before']) - 1
    cash, units, pending = cfg['initial_cash'], {}, None
    rows, trades, decisions = [], [], []
    for i in range(initial, end + 1):
        if pending is not None:
            signal_date, selected = pending
            openings = {s: data['adjusted_open'][s][i] for s in set(units) | set(selected)}
            cash, units, fee, turnover = fee_target(cash, units, openings, selected, 1 if benchmark else cfg['slots'], bps)
            trades.append((dates[i], signal_date, fee, turnover))
            pending = None
        nav = cash + sum(n * data['adjusted_close'][s][i] for s, n in units.items())
        rows.append((dates[i], nav, cash, dict(units)))
        month_end = i < end and dates[i][:7] != dates[i + 1][:7]
        if i < end and (i == initial or (not benchmark and month_end and (phase is None or int(dates[i][5:7]) in phase))):
            selected = [cfg['benchmark']] if benchmark else scores_at(i, data, cfg, arm)
            decisions.append((dates[i], selected))
            pending = dates[i], selected
    return rows, trades, decisions


def verify(data, cfg, results):
    reports = []
    expected = {(arm, None, cost) for arm in ('M12', 'MMIX') for cost in cfg['cost_bps_per_side_scenarios']}
    expected.update((arm, tuple(phase), cost) for arm in ('S12', 'SMIX') for phase in cfg['phase_pairs'] for cost in cfg['cost_bps_per_side_scenarios'])
    actual = {(run['arm'], tuple(run['phase']) if run['phase'] else None, run['cost_bps_per_side']) for run in results['runs']}
    require(actual == expected and len(results['runs']) == len(expected), 'strategy matrix is missing or repeats paths')
    require(len(results['benchmarks']) == 4 and {run['cost_bps_per_side'] for run in results['benchmarks']} == set(cfg['cost_bps_per_side_scenarios']), 'benchmark matrix is incomplete')
    for run in results['runs'] + results['benchmarks']:
        benchmark = run['signal'] == 'benchmark'
        arm = 'M12' if run['signal'] == '12-1' else 'MMIX'
        rows, trades, decisions = replay(data, cfg, arm, run['phase'], run['cost_bps_per_side'], benchmark)
        require(len(rows) == len(run['daily']), f"{run['run_id']}: daily row count differs")
        largest_relative_nav_error = 0
        largest_absolute_cash_error = 0
        for row, actual in zip(rows, run['daily']):
            require(row[0] == actual['session'], f"{run['run_id']}: session differs")
            error = abs(row[1] - actual['nav']) / row[1]
            largest_relative_nav_error = max(largest_relative_nav_error, error)
            cash_error = abs(row[2] - actual['cash'])
            largest_absolute_cash_error = max(largest_absolute_cash_error, cash_error)
            require(error < 2e-10, f"{run['run_id']}/{row[0]}: daily NAV differs")
            require(cash_error < max(1, row[1]) * 2e-10, f"{run['run_id']}/{row[0]}: cash differs")
            require(set(row[3]) == set(actual['positions']), f"{run['run_id']}/{row[0]}: held symbols differ")
            for symbol in row[3]:
                require(abs(row[3][symbol] - actual['positions'][symbol]) < max(1, row[3][symbol]) * 2e-10, f"{run['run_id']}/{row[0]}/{symbol}: units differ")
        require(len(trades) == len(run['trades']), f"{run['run_id']}: trade count differs")
        for (fill, decision, fee, turnover), actual in zip(trades, run['trades']):
            require(fill == actual['session'] and decision == actual['decision_session'], f"{run['run_id']}: trade timing differs")
            require(abs(fee - actual['cost']) < max(1, actual['pretrade_nav']) * 2e-10, f"{run['run_id']}/{fill}: fees differ")
            require(abs(turnover - actual['turnover']) < 2e-10, f"{run['run_id']}/{fill}: turnover differs")
        require(len(decisions) == len(run['signals']), f"{run['run_id']}: signal count differs")
        require(all(d == x['decision_session'] and selected == x['selected'] for (d, selected), x in zip(decisions, run['signals'])), f"{run['run_id']}: selected symbols differ")
        check_metrics(run, rows, trades)
        reports.append({'run_id': run['run_id'], 'daily_rows': len(rows), 'max_relative_nav_error': largest_relative_nav_error, 'max_absolute_cash_error': largest_absolute_cash_error})
    anchor = results['boundaries']['report_anchor_on_or_before']
    end = results['boundaries']['full_year_end_on_or_before']
    dates = data['sessions']
    a, e = dates.index(anchor), dates.index(end)
    spy_ratio = data['adjusted_close'][cfg['benchmark']][e] / data['adjusted_close'][cfg['benchmark']][a]
    spy_runs = results['benchmarks']
    for run in spy_runs:
        require(abs(run['metrics']['full_period']['total_return'] - (spy_ratio - 1)) < 1e-12, 'SPY buy-and-hold identity differs')
    return {'independent_replay': True, 'imports_project_code': False, 'independent_run_count': len(reports), 'compared_day_count': sum(row['daily_rows'] for row in reports), 'max_relative_nav_error': max(row['max_relative_nav_error'] for row in reports), 'max_absolute_cash_error': max(row['max_absolute_cash_error'] for row in reports), 'runs': reports}


def check_metrics(run, daily, trades):
    def check_period(metric, years):
        rows = [row for row in daily if metric['start_session'] <= row[0] <= metric['end_session']]
        events = [row for row in trades if metric['start_session'] < row[0] <= metric['end_session']]
        navs = [row[1] for row in rows]
        growth = navs[-1] / navs[0]
        peak, worst = navs[0], 0
        for nav in navs:
            peak = max(nav, peak)
            worst = min(worst, nav / peak - 1)
        expected = {'total_return': growth - 1, 'max_drawdown': worst, 'two_sided_turnover': sum(row[3] for row in events), 'transaction_cost': sum(row[2] for row in events), 'mean_cash_weight': sum(row[2] / row[1] for row in rows[1:]) / (len(rows) - 1)}
        if years is not None:
            expected['cagr'] = growth ** (1 / years) - 1
            expected['annualized_two_sided_turnover'] = expected['two_sided_turnover'] / years
        else:
            require(metric['cagr'] is None and metric['annualized_two_sided_turnover'] is None and metric['annualized_volatility'] is None, f"{run['run_id']}: partial-year performance annualized")
        for field, value in expected.items():
            require(abs(metric[field] - value) <= max(1, abs(value)) * 2e-10, f"{run['run_id']}/{metric['start_session']}/{field}: metric differs")
        require(metric['rebalance_count'] == len(events) and metric['session_count'] == len(rows) - 1, f"{run['run_id']}: period counts differ")

    check_period(run['metrics']['full_period'], 25)
    check_period(run['metrics']['ytd2026'], None)
    require(set(run['metrics']['annual']) == {str(year) for year in range(2001, 2026)}, f"{run['run_id']}: annual series incomplete")
    for year, metric in run['metrics']['annual'].items():
        check_period(metric, 1)
    require(run['metrics']['full_period']['end_nav'] == run['metrics']['ytd2026']['start_nav'], f"{run['run_id']}: account reset at 2026 boundary")


def check_public_statistics(summary, results):
    by_id = {run['run_id']: run for run in results['runs'] + results['benchmarks']}
    require({row['run_id'] for row in summary['runs']} == set(by_id), 'public run matrix differs')
    for row in summary['runs']:
        actual = by_id[row['run_id']]
        for period in ('full_period', 'ytd2026'):
            require(row['metrics'][period] == actual['metrics'][period], 'public per-path metrics differ')

    def check_comparison(row, period, year=None):
        a = by_id[row['monthly_run_id']]['metrics'][period]
        b = by_id[row['semiannual_run_id']]['metrics'][period]
        if year is not None:
            a, b = a[str(year)], b[str(year)]
        expected = {
            'net_return_difference_pp': 100 * (a['total_return'] - b['total_return']),
            'cagr_difference_pp': 100 * (a['cagr'] - b['cagr']) if a['cagr'] is not None else None,
            'max_drawdown_difference_pp': 100 * (a['max_drawdown'] - b['max_drawdown']),
            'extra_two_sided_turnover': a['two_sided_turnover'] - b['two_sided_turnover'],
        }
        for field, value in expected.items():
            require(row[field] == value, f'public comparison differs: {field}')

    for period, comparisons in summary['comparisons'].items():
        require(len(comparisons) == 48, 'public comparison matrix is incomplete')
        for row in comparisons:
            check_comparison(row, period)
        primary = summary['primary'][period]
        check_comparison(primary, period)
        require(primary['monthly_run_id'] == 'M12-5bps' and primary['semiannual_run_id'] == 'S12-03-09-5bps', 'primary comparison changed')
    require({row['year'] for row in summary['primary_annual']} == set(range(2001, 2026)), 'public primary annual series incomplete')
    for row in summary['primary_annual']:
        check_comparison(row, 'annual', row['year'])
    for run_id, points in summary['portfolio_paths'].items():
        run = by_id[run_id]
        anchor = run['metrics']['full_period']['start_session']
        daily = [row for row in run['daily'] if row['session'] >= anchor]
        peak = initial = daily[0]['nav']
        expected = {}
        for row in daily:
            peak = max(peak, row['nav'])
            expected[row['session']] = (row['nav'] / initial, row['nav'] / peak - 1)
        for point in points:
            wealth, drawdown = expected[point['session']]
            require(abs(point['wealth'] - wealth) < 1e-12 and abs(point['drawdown'] - drawdown) < 1e-12, 'public wealth or drawdown path differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True, help='Preserved private run directory')
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/sector-etf-pilot.v1.json')
    parser.add_argument('--summary', type=Path, default=ROOT / 'site/data/etf-pilot-summary.json')
    parser.add_argument('--public-summary', type=Path, default=ROOT / 'site/data/etf-pilot-validation.json')
    parser.add_argument('--private-report', type=Path, help='Optional complete per-path check receipt')
    args = parser.parse_args()
    manifest_path = args.run_dir / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    require(digest(args.config) == manifest['config_sha256'], 'configuration hash mismatch')
    require(digest(args.summary) == digest(args.run_dir / 'summary.json'), 'published summary differs from preserved run')
    for name, expected in manifest['file_sha256'].items():
        require(digest(args.run_dir / name) == expected, f'preserved file hash mismatch: {name}')
    for name, expected in manifest['code_sha256'].items():
        require(digest(ROOT / name) == expected, f'engine code hash mismatch: {name}')
    raw_dir = Path(manifest['raw_dir'])
    raw_manifest = json.loads((raw_dir / 'manifest.json').read_text())
    require(digest(raw_dir / 'manifest.json') == manifest['raw_manifest_sha256'], 'raw manifest hash mismatch')
    for capture in raw_manifest['captures']:
        require(digest(raw_dir / capture['file']) == capture['sha256'], f"raw capture hash mismatch: {capture['file']}")
    summary = json.loads(args.summary.read_text())
    require(summary['run_id'] == manifest['run_id'] and summary['audit']['passed'] and not summary['original_stock_experiment_completed'], 'summary scope or audit status is invalid')
    cfg = json.loads(args.config.read_text())
    data = json.loads(gzip.decompress((args.run_dir / 'input-data.json.gz').read_bytes()))
    paths = [json.loads(gzip.decompress(path.read_bytes())) for path in sorted(args.run_dir.glob('*.json.gz')) if path.name != 'input-data.json.gz']
    results = dict(summary)
    results['runs'] = [run for run in paths if run['signal'] != 'benchmark']
    results['benchmarks'] = [run for run in paths if run['signal'] == 'benchmark']
    result = verify(data, cfg, results)
    check_public_statistics(summary, results)
    full_report = dict(result)
    del result['runs']
    receipt = {
        'schema_version': 1,
        'run_id': summary['run_id'],
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': True,
        'scope': 'independent_accounting_replay_of_preserved_vendor_snapshot',
        'original_stock_experiment_completed': False,
        'summary_sha256': digest(args.summary),
        'config_sha256': digest(args.config),
        'run_manifest_sha256': digest(manifest_path),
        'input_data_gzip_sha256': digest(args.run_dir / 'input-data.json.gz'),
        'raw_manifest_sha256': manifest['raw_manifest_sha256'],
        'engine_code_sha256': manifest['code_sha256'],
        'verifier_code_sha256': digest(__file__),
        **result,
        'checks': {
            'all_expected_paths_present': True,
            'preserved_raw_input_result_and_code_hashes_match': True,
            'independent_momentum_selection_matches': True,
            'independent_analytic_fee_solution_matches': True,
            'every_daily_nav_cash_and_holding_matches': True,
            'every_signal_and_next_open_trade_matches': True,
            'full_year_ytd_and_annual_metrics_match': True,
            'published_metrics_comparisons_and_plot_points_match': True,
            'partial_year_not_annualized': True,
            'spy_hold_identity_all_costs': True,
        },
        'limitations': ['This is an independent implementation check using the same vendor input snapshot, not an independent price source.', 'It does not validate executable fills, payment-date dividend accounting or the original stock protocol.'],
    }
    args.public_summary.parent.mkdir(parents=True, exist_ok=True)
    args.public_summary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    if args.private_report:
        args.private_report.parent.mkdir(parents=True, exist_ok=True)
        args.private_report.write_text(json.dumps({**receipt, 'runs': full_report['runs']}, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
