#!/usr/bin/env python3
"""Independent state-machine replay, with no production engine imports.

The reused legacy verifier supplies independently written scores, analytic
fees and metric checks. B timing/target logic is implemented here separately.
This validates calculations on one vendor snapshot, not vendor price truth.
"""
import argparse
import bisect
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_etf_pilot_independent import fee_target, scores_at, replay, check_metrics, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay_b(data, cfg, arm, phase, bps):
    dates = data["sessions"]
    initial = bisect.bisect_right(dates, cfg["initial_signal_on_or_before"]) - 1
    end = bisect.bisect_right(dates, cfg["case_end_on_or_before"]) - 1
    cash, units, pending = cfg["initial_cash"], {}, None
    selected, origin = [], None
    rows, trades, decisions = [], [], []
    for i in range(initial, end + 1):
        if pending is not None:
            decision, target_origin, names, refreshed = pending
            opening = {s: data["adjusted_open"][s][i] for s in set(units) | set(names)}
            old_value = {s: n * opening[s] for s, n in units.items()}
            cash, units, fee, turnover = fee_target(cash, units, opening, names, cfg["slots"], bps)
            partition = {key: 0.0 for key in ("entry", "exit", "resize")}
            for symbol in set(old_value) | set(units):
                new_value = units.get(symbol, 0) * opening[symbol]
                category = "entry" if symbol not in old_value else ("exit" if symbol not in names else "resize")
                partition[category] += abs(new_value - old_value.get(symbol, 0))
            trades.append({"session": dates[i], "decision_session": decision, "target_origin_session": target_origin,
                           "target_refreshed": refreshed, "cost": fee, "turnover": turnover, "partition": partition})
            pending = None
        nav = cash + sum(n * data["adjusted_close"][s][i] for s, n in units.items())
        rows.append((dates[i], nav, cash, dict(units)))
        month_end = i < end and dates[i][:7] != dates[i + 1][:7]
        if i < end and (i == initial or month_end):
            refreshed = i == initial or int(dates[i][5:7]) in phase
            if refreshed:
                selected = scores_at(i, data, cfg, arm)
                origin = dates[i]
            decisions.append((dates[i], list(selected), origin, refreshed))
            pending = dates[i], origin, list(selected), refreshed
    return rows, trades, decisions


def compare_path(run, rows, trades, decisions):
    require(len(rows) == len(run["daily"]), f"{run['run_id']}: daily count")
    nav_error, cash_error, unit_error = 0.0, 0.0, 0.0
    for row, actual in zip(rows, run["daily"]):
        require(row[0] == actual["session"], "daily dates differ")
        rel = abs(row[1] - actual["nav"]) / row[1]
        nav_error = max(nav_error, rel)
        cash_error = max(cash_error, abs(row[2] - actual["cash"]))
        require(rel < 2e-10 and abs(row[2] - actual["cash"]) < max(1, row[1]) * 2e-10, "account state differs")
        require(set(row[3]) == set(actual["positions"]), "held names differ")
        for symbol, units in row[3].items():
            rel_units = abs(units - actual["positions"][symbol]) / max(1, abs(units))
            unit_error = max(unit_error, rel_units)
            require(rel_units < 2e-10, "held units differ")
    require(len(trades) == len(run["trades"]), "trade count differs")
    tuples = []
    for independent, actual in zip(trades, run["trades"]):
        if isinstance(independent, tuple):
            fill, decision, fee, turnover = independent
        else:
            fill, decision, fee, turnover = [independent[k] for k in ("session", "decision_session", "cost", "turnover")]
            require(independent["target_origin_session"] == actual["target_origin_session"] and independent["target_refreshed"] == actual["target_refreshed"], "B target provenance differs")
            for category, notional in independent["partition"].items():
                require(abs(notional - actual["notional_by_category"][category]) <= max(1, actual["pretrade_nav"]) * 2e-10, "order category differs")
        require(fill == actual["session"] and decision == actual["decision_session"], "trade timing differs")
        require(abs(fee - actual["cost"]) < max(1, actual["pretrade_nav"]) * 2e-10 and abs(turnover - actual["turnover"]) < 2e-10, "fee/turnover differs")
        tuples.append((fill, decision, fee, turnover))
    require(len(decisions) == len(run["signals"]), "decision count differs")
    for independent, actual in zip(decisions, run["signals"]):
        require(independent[0] == actual["decision_session"] and independent[1] == actual["selected"], "selected target differs")
        if len(independent) == 4:
            require(independent[2] == actual["target_origin_session"] and independent[3] == actual["target_refreshed"], "frozen target history differs")
            require(actual["target_weights"] == {s: 1 / 3 for s in independent[1]}, "frozen weights differ")
            require(abs(actual["cash_target_weight"] - (1 - len(independent[1]) / 3)) < 1e-12, "cash target differs")
    check_metrics(run, rows, tuples)
    return {"run_id": run["run_id"], "policy": run.get("policy", "SPY"), "daily_rows": len(rows),
            "max_relative_nav_error": nav_error, "max_absolute_cash_error": cash_error, "max_relative_unit_error": unit_error}


def verify(run_dir, protocol_path):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_bytes())
    require(digest(protocol_path) == manifest["protocol_sha256"], "protocol hash differs")
    for name, expected in manifest["file_sha256"].items():
        require(digest(run_dir / name) == expected, f"artifact hash differs: {name}")
    for name, expected in manifest["code_sha256"].items():
        require(digest(ROOT / name) == expected, f"production source changed: {name}")
    protocol = json.loads(Path(protocol_path).read_bytes())
    cfg = json.loads((ROOT / protocol["legacy_config"]).read_bytes())
    require(digest(ROOT / protocol["legacy_config"]) == protocol["legacy_config_sha256"], "legacy config differs")
    data = json.loads(gzip.decompress((run_dir / "input-data.json.gz").read_bytes()))
    paths = [json.loads(gzip.decompress(p.read_bytes())) for p in sorted(run_dir.glob("*.json.gz")) if p.name != "input-data.json.gz"]
    require(len(paths) == 108, "account matrix size differs")
    require(len({p["run_id"] for p in paths}) == 108, "duplicate account IDs")
    expected = {(policy, signal, tuple(phase), cost) for policy in ("A", "B") for signal in ("12-1", "mixed") for phase in cfg["phase_pairs"] for cost in cfg["cost_bps_per_side_scenarios"]}
    expected.update(("C", signal, None, cost) for signal in ("12-1", "mixed") for cost in cfg["cost_bps_per_side_scenarios"])
    actual = {(p["policy"], p["signal"], tuple(p["phase"]) if p["phase"] else None, p["cost_bps_per_side"]) for p in paths if p["signal"] != "benchmark"}
    require(actual == expected, "strategy matrix coverage differs")
    reports = []
    for run in paths:
        arm = "M12" if run["signal"] == "12-1" else "MMIX"
        if run.get("policy") == "B":
            rows, trades, decisions = replay_b(data, cfg, arm, run["phase"], run["cost_bps_per_side"])
        else:
            rows, trades, decisions = replay(data, cfg, arm, run["phase"], run["cost_bps_per_side"], run["signal"] == "benchmark")
        reports.append(compare_path(run, rows, trades, decisions))
    by_id = {r["run_id"]: r for r in paths}
    rows_checked = 0
    for period, expected_count in (("full_period", 144), ("ytd2026", 144), ("annual", 3600)):
        with (run_dir / f"comparisons-{period}.csv").open(newline="", encoding="utf-8") as f:
            comparisons = list(csv.DictReader(f))
        require(len(comparisons) == expected_count, "comparison count differs")
        keys = set()
        for row in comparisons:
            high, low = by_id[row["high_run_id"]], by_id[row["low_run_id"]]
            a, b = high["metrics"][period], low["metrics"][period]
            if period == "annual":
                a, b = a[row["year"]], b[row["year"]]
            require(high["policy"] + "-" + low["policy"] == row["contrast"], "contrast binding differs")
            key = (row["contrast"], row["signal"], row["phase"], row["cost_bps_per_side"], row.get("year"))
            require(key not in keys, "duplicate comparison")
            keys.add(key)
            delta = math.log((1 + a["total_return"]) / (1 + b["total_return"]))
            require(abs(float(row["log_growth_difference"]) - delta) < 1e-12, "growth contrast differs")
            require(abs(float(row["net_return_difference_pp"]) - 100 * (a["total_return"] - b["total_return"])) < 1e-10, "return contrast differs")
            if a["cagr"] is None:
                require(row["cagr_difference_pp"] == "", "partial-year CAGR present")
            else:
                require(abs(float(row["cagr_difference_pp"]) - 100 * (a["cagr"] - b["cagr"])) < 1e-12, "CAGR contrast differs")
            rows_checked += 1
    receipt = {"schema_version": 1, "run_id": manifest["run_id"], "passed": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "imports_production_engine": False,
        "scope": "independent_state_machine_and_analytic_fee_replay_on_preserved_vendor_snapshot",
        "independent_account_count": len(reports), "compared_day_count": sum(r["daily_rows"] for r in reports),
        "compared_comparison_rows": rows_checked, "max_relative_nav_error": max(r["max_relative_nav_error"] for r in reports),
        "max_absolute_cash_error": max(r["max_absolute_cash_error"] for r in reports),
        "protocol_sha256": manifest["protocol_sha256"], "run_manifest_sha256": digest(run_dir / "manifest.json"),
        "input_data_gzip_sha256": digest(run_dir / "input-data.json.gz"),
        "verifier_code_sha256": digest(__file__), "legacy_verifier_sha256": digest(ROOT / "scripts/validate_etf_pilot_independent.py"),
        "checks": {"all_108_accounts_replayed": True, "independent_target_selection": True,
                   "B_targets_frozen_between_refreshes": True, "next_open_fills_and_single_reset": True,
                   "every_daily_nav_cash_and_holding": True, "full_annual_YTD_metrics": True,
                   "order_notional_partition": True, "complete_paired_comparisons": True},
        "limitations": ["Same vendor price input, not an independent data source.", "Does not establish achievable fills, capacity, dividend payment ledgers or real-time vintages."],
        "runs": reports}
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs/sector-etf-mechanisms.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.run_dir, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "runs"}, sort_keys=True))


if __name__ == "__main__":
    main()
