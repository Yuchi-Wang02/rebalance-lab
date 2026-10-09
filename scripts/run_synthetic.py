#!/usr/bin/env python3
"""Run all 16 protocol paths on fictional data and publish an engineering receipt."""

import argparse
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

from spmo_lab.simulation import run_matrix
from spmo_lab.synthetic import make_fixture


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False,
                       default=lambda v: v.isoformat()) + "\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_csv(path, rows, context):
    combined = [{**context, **r} for r in rows]
    fields = list(dict.fromkeys(k for r in combined for k in r)) or list(context)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in combined:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def engineering_checks(results, config):
    expected = {(a, c) for a in config["arms"] for c in config["common"]["cost_bps_per_side_scenarios"]}
    checks = {
        "all_16_arm_cost_combinations": len(results) == 16 and {(r["strategy_id"], r["cost_bps"]) for r in results} == expected,
        "synthetic_labels_only": all(r["data_track"] == "synthetic" for r in results),
        "cash_never_negative": all(row["cash"] >= -1e-8 for r in results for row in r["daily"]),
        "all_fills_have_positive_quantity_and_price": all(t["quantity"] > 0 and t["price"] > 0 for r in results for t in r["trades"]),
        "fees_match_executed_notional": all(abs(t["cost"] - t["notional"] * r["cost_bps"] / 10000) < 1e-8
                                            for r in results for t in r["trades"]),
        "initial_fill_after_initial_signal": all(r["trades"] and min(t["session"] for t in r["trades"]) > config["period"]["initial_signal_close"] for r in results),
        "scheduled_fills_after_decision": all(t.get("decision_session") and t["decision_session"] < t["session"]
                                              for r in results for t in r["trades"] if t["reason"] == "scheduled_rebalance"),
        "anchor_and_end_snapshots_retained": all(set(r["snapshots"]) == {config["period"]["report_anchor_close"], config["period"]["report_end_close"]} for r in results),
        "report_cost_excludes_burn_in": all(abs(r["metrics"]["reporting_cost"] - sum(t["cost"] for t in r["trades"]
                                                  if config["period"]["report_anchor_close"] < t["session"] <= config["period"]["report_end_close"])) < 1e-8 for r in results),
    }
    if not all(checks.values()):
        raise ValueError("Synthetic engineering checks failed: " + ", ".join(k for k, v in checks.items() if not v))
    return checks


def run(output_dir, public_summary=None):
    code_files = [Path(__file__), *sorted((ROOT / "spmo_lab").glob("*.py"))]
    code_hashes = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in code_files}
    config_bytes = (ROOT / "configs/experiment.v1.json").read_bytes()
    config = json.loads(config_bytes)
    data = make_fixture(config)
    fixture_hash = sha(encoded(asdict(data)))
    results = run_matrix(data, config)
    checks = engineering_checks(results, config)
    if any(sha((ROOT / name).read_bytes()) != digest for name, digest in code_hashes.items()):
        raise ValueError("Engine code changed during execution; rerun a stable version.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    directory = output_dir / run_id
    directory.mkdir(parents=True, exist_ok=False)
    identities = []
    for result in results:
        identity = f"{run_id}-{result['strategy_id']}-{result['cost_bps']}bps"
        identities.append(identity)
        target = directory / f"{result['strategy_id']}-{result['cost_bps']}bps"
        target.mkdir()
        context = {"run_id": identity, "strategy_id": result["strategy_id"],
                   "cost_bps": result["cost_bps"], "data_track": "synthetic"}
        (target / "result.json").write_bytes(encoded({**context, **result}))
        for field in ("daily", "trades", "signals", "corporate_actions", "exceptions"):
            write_csv(target / (field + ".csv"), result[field], context)
    contrasts = []
    for cost in config["common"]["cost_bps_per_side_scenarios"]:
        returns = {r["strategy_id"]: r["metrics"]["net_total_return"] for r in results if r["cost_bps"] == cost}
        primary, replication = returns["M12"] - returns["S12"], returns["MMIX"] - returns["SMIX"]
        contrasts.append({"data_track": "synthetic", "cost_bps": cost,
                          "primary_percentage_points": 100 * primary,
                          "replication_percentage_points": 100 * replication,
                          "interaction_percentage_points": 100 * (replication - primary)})
    (directory / "synthetic_contrasts.json").write_bytes(encoded(contrasts))
    manifest = {"schema_version": 1, "run_id": run_id, "data_track": "synthetic",
                "fixture_description": "Fictional securities, prices, events and weekday calendar with artificial closures",
                "calendar_is_verified_exchange_calendar": False, "fixture_sha256": fixture_hash,
                "config_sha256": sha(config_bytes), "code_sha256": code_hashes,
                "run_count": len(results), "run_ids": identities, "checks": checks,
                "market_backtest_executed": False, "research_ready": False,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "file_sha256": {str(p.relative_to(directory)): sha(p.read_bytes())
                                for p in sorted(directory.rglob("*")) if p.is_file()}}
    receipt = {key: manifest[key] for key in ("schema_version", "run_id", "data_track", "fixture_sha256",
               "config_sha256", "code_sha256", "run_count", "checks", "market_backtest_executed",
               "research_ready", "generated_at_utc", "calendar_is_verified_exchange_calendar")}
    receipt.update(engine_status="synthetic_prototype", formal_engine_accepted=False,
                   strategy_ids=list(config["arms"]), cost_bps=config["common"]["cost_bps_per_side_scenarios"],
                   limitations=["No audited market-data adapter", "Corporate-action availability is synthetic",
                                "Merger, spinoff and delisting settlements unsupported", "ETF reference reconciliation pending"])
    (directory / "engineering_receipt.json").write_bytes(encoded(receipt))
    manifest["file_sha256"]["engineering_receipt.json"] = sha((directory / "engineering_receipt.json").read_bytes())
    (directory / "run_manifest.json").write_bytes(encoded(manifest))
    if public_summary:
        public_summary.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=public_summary.parent, prefix=".engine-status-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encoded(receipt))
            temporary.replace(public_summary)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {"run_dir": str(directory), "run_count": len(results), "checks_passed": len(checks),
            "data_track": "synthetic", "market_backtest_executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/generated/synthetic")
    parser.add_argument("--public-summary", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.output_dir, args.public_summary)
    except (ValueError, OSError, KeyError) as error:
        print(f"FAIL: synthetic experiment stopped: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
