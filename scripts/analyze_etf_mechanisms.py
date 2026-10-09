#!/usr/bin/env python3
"""Analyze a verified run under the frozen mechanism protocol."""
import argparse
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
import numpy as np
from pilot.mechanism_analysis import paired_inference, bootstrap_intervals, state_diagnostics, factor_diagnostics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_gzip(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def json_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def window_metrics(run, first_year, last_year):
    days = run["daily"]
    start = max(d["session"] for d in days if int(d["session"][:4]) < first_year)
    end = max(d["session"] for d in days if int(d["session"][:4]) <= last_year)
    rows = [d for d in days if start <= d["session"] <= end]
    navs = [d["nav"] for d in rows]
    peak, worst = navs[0], 0.0
    for nav in navs:
        peak = max(peak, nav); worst = min(worst, nav / peak - 1)
    trades = [t for t in run["trades"] if start < t["session"] <= end]
    return {"start_session": start, "end_session": end, "total_return": navs[-1] / navs[0] - 1,
            "max_drawdown": worst, "two_sided_turnover": math.fsum(t["turnover"] for t in trades),
            "transaction_cost_over_window_anchor_nav": math.fsum(t["cost"] for t in trades) / navs[0],
            "mean_cash_weight": math.fsum(d["cash_weight"] for d in rows[1:]) / (len(rows) - 1)}


def monthly_states(data, month_sessions, anchor, protocol):
    sessions = data["sessions"]; index = {s: i for i, s in enumerate(sessions)}
    closes = np.asarray(data["adjusted_close"]["SPY"], dtype=float)
    prior = [anchor, *month_sessions[:-1]]
    rows = []
    for month_end, previous in zip(month_sessions, prior):
        i = index[previous]
        spec = protocol["states"]
        trend = closes[i - spec["trend"]["skip"]] / closes[i - spec["trend"]["lookback"]] - 1
        count = spec["volatility"]["daily_returns"]
        prices = closes[i - count:i + 1]
        returns = prices[1:] / prices[:-1] - 1
        vol = np.std(returns, ddof=spec["volatility"]["ddof"]) * math.sqrt(spec["volatility"]["annualization"])
        rows.append({"month": month_end[:7], "known_at_session": previous, "spy_12_1_return": float(trend),
                     "spy_63d_annualized_volatility": float(vol), "trend_state": int(trend > 0),
                     "volatility_state": int(vol > spec["volatility"]["threshold"])})
    return rows


def analyze(run_dir, factor_dir, validation_path, output_dir):
    run_dir, factor_dir, output_dir = map(Path, (run_dir, factor_dir, output_dir))
    summary = json.loads((run_dir / "summary.json").read_bytes())
    protocol = json.loads((run_dir / "protocol.json").read_bytes())
    validation = json.loads(Path(validation_path).read_bytes())
    if not validation.get("passed") or validation["run_id"] != summary["run_id"] or validation["run_manifest_sha256"] != sha(run_dir / "manifest.json"):
        raise ValueError("independent replay does not validate this run")
    if sha(ROOT / "configs/sector-etf-mechanisms.v1.json") != summary["protocol_sha256"]:
        raise ValueError("fixed protocol differs")
    factor_manifest = json.loads((factor_dir / "manifest.json").read_bytes())
    if sha(factor_dir / "factors-2001-2025.csv") != factor_manifest["normalized_sha256"]:
        raise ValueError("factor normalization hash mismatch")
    for record in factor_manifest["captures"]:
        if sha(factor_dir / record["file"]) != record["sha256"]:
            raise ValueError("factor source bytes changed")
    with (run_dir / "monthly-returns.csv").open(newline="", encoding="utf-8") as stream:
        monthly = list(csv.DictReader(stream))
    expected_months = [f"{year}-{month:02d}" for year in range(2001, 2026) for month in range(1, 13)]
    accounts = {}
    for row in monthly:
        accounts.setdefault(row["run_id"], []).append(row)
    for rows in accounts.values():
        if [r["month"] for r in rows] != expected_months:
            raise ValueError("portfolio months missing, duplicated or misordered")
    primary_ids = summary["primary_run_ids"]
    values = np.column_stack([[float(r["simple_return"]) for r in accounts[primary_ids[p]]] for p in ("A", "B", "C")])
    paths = {p: read_gzip(run_dir / (primary_ids[p] + ".json.gz")) for p in ("A", "B", "C")}
    for j, policy in enumerate(("A", "B", "C")):
        observed = np.prod(1 + values[:, j]) - 1
        if abs(observed - paths[policy]["metrics"]["full_period"]["total_return"]) > 1e-10:
            raise ValueError("monthly returns do not reconcile to full period")
    logs = np.log1p(values)
    if not np.allclose(logs[:, 2] - logs[:, 0], (logs[:, 1] - logs[:, 0]) + (logs[:, 2] - logs[:, 1]), rtol=0, atol=1e-14):
        raise ValueError("monthly growth contrasts do not telescope")
    spec = protocol["inference"]
    inference = paired_inference(values, spec["hac_lags"])
    bootstrap = [row for length in [spec["bootstrap_expected_block_length"], *spec["bootstrap_block_sensitivity"]]
                 for row in bootstrap_intervals(values, spec["bootstrap_repetitions"], length, spec["bootstrap_seed"])]
    data = read_gzip(run_dir / "input-data.json.gz")
    state_rows = monthly_states(data, [r["session"] for r in accounts[primary_ids["A"]]],
                                summary["boundaries"]["report_anchor_on_or_before"], protocol)
    states = {"trend": [r["trend_state"] for r in state_rows], "volatility": [r["volatility_state"] for r in state_rows]}
    state_results = state_diagnostics(values, states, spec["hac_lags"], protocol["states"]["minimum_state_months"])
    stress = []
    for window in protocol["stress_windows"]:
        metrics = {p: window_metrics(paths[p], window["start_year"], window["end_year"]) for p in ("A", "B", "C")}
        contrasts = {name: math.log((1 + metrics[high]["total_return"]) / (1 + metrics[low]["total_return"]))
                     for name, high, low in (("C-A", "C", "A"), ("B-A", "B", "A"), ("C-B", "C", "B"))}
        stress.append({**window, "metrics": metrics, "log_growth_contrasts": contrasts})
    with (factor_dir / "factors-2001-2025.csv").open(newline="", encoding="utf-8") as stream:
        factors = list(csv.DictReader(stream))
    if [r["month"] for r in factors] != expected_months:
        raise ValueError("factor months do not exactly match portfolio months")
    factor_values = [[float(r[name]) for name in protocol["factor_diagnostic"]["factors"]] for r in factors]
    exposure = factor_diagnostics(values, factor_values, [float(r["RF"]) for r in factors], spec["hac_lags"])
    result = {"schema_version": 1, "run_id": summary["run_id"], "experiment_id": protocol["experiment_id"],
              "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "analyzed_after_independent_replay",
              "months": 300, "primary_run_ids": primary_ids,
              "primary_metrics": {p: paths[p]["metrics"]["full_period"] for p in paths},
              "primary_inference": inference, "bootstrap": bootstrap,
              "state_definitions": protocol["states"], "state_results": state_results, "stress_windows": stress,
              "factor_diagnostic": exposure, "factor_provenance": factor_manifest,
              "protocol_sha256": summary["protocol_sha256"], "run_manifest_sha256": sha(run_dir / "manifest.json"),
              "validation_sha256": sha(validation_path), "monthly_input_sha256": sha(run_dir / "monthly-returns.csv"),
              "factor_manifest_sha256": sha(factor_dir / "manifest.json"),
              "analysis_code_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), ROOT / "pilot/mechanism_analysis.py"]},
              "checks": {"exact_300_month_join": True, "monthly_returns_match_terminal_wealth": True,
                         "monthly_growth_telescope": True, "states_use_prior_month_end": True,
                         "factor_coefficients_reconcile": True, "independent_replay_precedes_analysis": True},
              "limitations": protocol["limitations"]}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "analysis.json").write_bytes(json_bytes(result))
    with (output_dir / "market-states.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(state_rows[0])); writer.writeheader(); writer.writerows(state_rows)
    result_files = {p.name: sha(p) for p in output_dir.iterdir() if p.is_file()}
    (output_dir / "manifest.json").write_bytes(json_bytes({"run_id": summary["run_id"], "file_sha256": result_files,
                                                         "analysis_code_sha256": result["analysis_code_sha256"]}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--factor-dir", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run_dir, args.factor_dir, args.validation, args.output_dir)
    print(json.dumps({"run_id": result["run_id"], "primary_inference": result["primary_inference"],
                      "state_results": result["state_results"], "output_dir": str(args.output_dir)}, sort_keys=True))
