#!/usr/bin/env python3
"""Validate all six fixed semiannual calendar phases on fictional data only."""

import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spmo_lab.simulation import run_calendar_matrix, validate_calendar_sensitivity
from spmo_lab.synthetic import make_fixture


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False,
                       default=lambda item: item.isoformat()) + "\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_csv(path, rows, context=None):
    combined = [{**(context or {}), **row} for row in rows]
    fields = list(dict.fromkeys(key for row in combined for key in row)) or list(context or {})
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in combined:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def engineering_checks(matrix, config, sensitivity):
    controls, slow_runs, table = (matrix[key] for key in ("monthly_controls", "phase_runs", "phase_table"))
    results = controls + slow_runs
    phases = {tuple(pair) for pair in sensitivity["phase_pairs"]}
    costs = set(sensitivity["cost_bps_per_side_scenarios"])
    expected_controls = {(comparison["monthly_control"], cost)
                         for comparison in sensitivity["comparisons"] for cost in costs}
    expected_slow = {(comparison["semiannual"], cost, phase)
                     for comparison in sensitivity["comparisons"] for cost in costs for phase in phases}
    control_ids = {result["strategy_run_id"] for result in controls}
    slow_ids = {result["strategy_run_id"] for result in slow_runs}
    control_uses = Counter(row["monthly_control_id"] for row in table)
    checks = {
        "exactly_8_reused_monthly_controls": len(controls) == 8 and
            {(result["strategy_id"], result["cost_bps"]) for result in controls} == expected_controls,
        "exactly_48_semiannual_phase_runs": len(slow_runs) == 48 and
            {(result["strategy_id"], result["cost_bps"], tuple(result["calendar_phase"]))
             for result in slow_runs} == expected_slow,
        "exactly_56_unique_runs": len(results) == 56 and
            len({result["strategy_run_id"] for result in results}) == 56,
        "all_48_paired_contrasts_retained": len(table) == 48 and
            {(row["semiannual_strategy"], row["cost_bps"], tuple(row["calendar_phase"]))
             for row in table} == expected_slow,
        "each_monthly_control_reused_for_six_phases": set(control_uses) == control_ids and
            set(control_uses.values()) == {6},
        "each_phase_run_has_one_contrast": Counter(row["semiannual_run_id"] for row in table) ==
            Counter({identity: 1 for identity in slow_ids}),
        "exactly_8_primary_reference_rows": sum(row["is_primary_reference_phase"] for row in table) == 8 and
            all(row["is_primary_reference_phase"] == (row["calendar_phase"] == [3, 9]) for row in table),
        "synthetic_supplementary_labels_only": all(result["data_track"] == "synthetic" and
            result["experiment_track"] == "calendar_phase_sensitivity" for result in results),
        "monthly_controls_have_no_phase_override": all(result["calendar_phase"] is None for result in controls),
        "only_fixed_semiannual_signal_months": all(
            record["decision_session"] == config["period"]["initial_signal_close"] or
            int(record["decision_session"][5:7]) in result["calendar_phase"]
            for result in slow_runs for record in result["signals"]),
        "cash_initialization_and_no_negative_cash": all(
            result["daily"][0]["session"] == config["period"]["initial_signal_close"] and
            result["daily"][0]["nav"] == 1_000_000 and
            all(row["cash"] >= -1e-8 for row in result["daily"]) for result in results),
        "scheduled_fills_after_decision": all(
            trade.get("decision_session") and trade["decision_session"] < trade["session"]
            for result in results for trade in result["trades"] if trade["reason"] == "scheduled_rebalance"),
        "fees_match_executed_notional": all(
            abs(trade["cost"] - trade["notional"] * result["cost_bps"] / 10000) < 1e-8
            for result in results for trade in result["trades"]),
        "reporting_boundaries_and_burn_in_preserved": all(
            set(result["snapshots"]) == {config["period"]["report_anchor_close"], config["period"]["report_end_close"]} and
            abs(result["metrics"]["reporting_cost"] - sum(trade["cost"] for trade in result["trades"]
                if config["period"]["report_anchor_close"] < trade["session"] <= config["period"]["report_end_close"])) < 1e-8
            for result in results),
    }
    if not all(checks.values()):
        raise ValueError("Calendar sensitivity checks failed: " + ", ".join(key for key, value in checks.items() if not value))
    return checks


def public_receipt(manifest, sensitivity):
    """Return an explicit metadata whitelist: synthetic performance stays private."""
    keys = ("schema_version", "run_id", "data_track", "experiment_track", "generated_at_utc",
            "fixture_sha256", "primary_config_sha256", "sensitivity_config_sha256", "code_sha256",
            "monthly_control_count", "semiannual_run_count", "unique_run_count", "paired_contrast_count",
            "checks", "market_backtest_executed", "research_ready", "calendar_is_verified_exchange_calendar")
    receipt = {key: manifest[key] for key in keys}
    receipt.update(
        status="synthetic_validation_only", primary_reference_phase=sensitivity["primary_reference_phase"],
        phase_pairs=sensitivity["phase_pairs"],
        cost_bps_per_side_scenarios=sensitivity["cost_bps_per_side_scenarios"],
        inference_scope=sensitivity["inference_scope"], report_all_phases=True, promote_best_phase=False,
        limitations=["Fictional securities and prices only", "Fictional calendar is not an exchange calendar",
                     "No audited market-data adapter", "No independent replication or best-phase selection"])
    return receipt


def run(output_dir, public_summary=None):
    code_files = [Path(__file__), *sorted((ROOT / "spmo_lab").glob("*.py"))]
    code_hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in code_files}
    primary_bytes = (ROOT / "configs/experiment.v1.json").read_bytes()
    sensitivity_bytes = (ROOT / "configs/calendar-sensitivity.v1.json").read_bytes()
    primary, sensitivity = json.loads(primary_bytes), json.loads(sensitivity_bytes)
    primary_hash = sha(primary_bytes)
    validate_calendar_sensitivity(primary, sensitivity, primary_hash)
    data = make_fixture(primary)
    fixture_hash = sha(encoded(asdict(data)))
    matrix = run_calendar_matrix(data, primary, sensitivity, primary_config_sha256=primary_hash)
    checks = engineering_checks(matrix, primary, sensitivity)
    if (any(sha((ROOT / name).read_bytes()) != digest for name, digest in code_hashes.items()) or
            (ROOT / "configs/experiment.v1.json").read_bytes() != primary_bytes or
            (ROOT / "configs/calendar-sensitivity.v1.json").read_bytes() != sensitivity_bytes):
        raise ValueError("Code or configuration changed during execution; rerun a stable version.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    directory = output_dir / run_id
    directory.mkdir(parents=True, exist_ok=False)
    identities = []
    for result in matrix["monthly_controls"] + matrix["phase_runs"]:
        identity = f"{run_id}-{result['strategy_run_id']}"
        identities.append(identity)
        target = directory / result["strategy_run_id"]
        target.mkdir()
        context = {"run_id": identity, "strategy_run_id": result["strategy_run_id"],
                   "strategy_id": result["strategy_id"], "cost_bps": result["cost_bps"],
                   "data_track": "synthetic", "experiment_track": "calendar_phase_sensitivity",
                   "calendar_phase": result["calendar_phase"], "run_role": result["run_role"]}
        (target / "result.json").write_bytes(encoded({**context, **result}))
        for field in ("daily", "trades", "signals", "corporate_actions", "exceptions"):
            write_csv(target / (field + ".csv"), result[field], context)
    # Link both sides of each contrast to globally distinct artifact run IDs.
    table = [{**row, "monthly_control_id": f"{run_id}-{row['monthly_control_id']}",
              "semiannual_run_id": f"{run_id}-{row['semiannual_run_id']}"} for row in matrix["phase_table"]]
    (directory / "phase_table.json").write_bytes(encoded(table))
    write_csv(directory / "phase_table.csv", table)
    manifest = {
        "schema_version": 1, "run_id": run_id, "data_track": "synthetic",
        "experiment_track": "calendar_phase_sensitivity", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": fixture_hash, "primary_config_sha256": primary_hash,
        "sensitivity_config_sha256": sha(sensitivity_bytes), "code_sha256": code_hashes,
        "monthly_control_count": len(matrix["monthly_controls"]), "semiannual_run_count": len(matrix["phase_runs"]),
        "unique_run_count": len(identities), "paired_contrast_count": len(table), "run_ids": identities,
        "checks": checks, "calendar_is_verified_exchange_calendar": False,
        "market_backtest_executed": False, "research_ready": False,
        "file_sha256": {str(path.relative_to(directory)): sha(path.read_bytes())
                        for path in sorted(directory.rglob("*")) if path.is_file()},
    }
    receipt = public_receipt(manifest, sensitivity)
    (directory / "engineering_receipt.json").write_bytes(encoded(receipt))
    manifest["file_sha256"]["engineering_receipt.json"] = sha((directory / "engineering_receipt.json").read_bytes())
    (directory / "run_manifest.json").write_bytes(encoded(manifest))
    if public_summary:
        public_summary.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=public_summary.parent, prefix=".calendar-status-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded(receipt))
            temporary.replace(public_summary)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {"run_dir": str(directory), "monthly_control_count": len(matrix["monthly_controls"]),
            "semiannual_run_count": len(matrix["phase_runs"]), "unique_run_count": len(identities),
            "paired_contrast_count": len(table), "checks_passed": len(checks), "data_track": "synthetic",
            "experiment_track": "calendar_phase_sensitivity", "market_backtest_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/generated/calendar-sensitivity")
    parser.add_argument("--public-summary", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.output_dir, args.public_summary)
    except (ValueError, OSError, KeyError) as error:
        print(f"FAIL: calendar sensitivity stopped: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
