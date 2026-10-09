#!/usr/bin/env python3
"""Run the frozen three-policy extension from a preserved input, offline."""
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
from pilot.rebalance_mechanisms import run_policy_matrix


def encoded(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_gzip(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def identity_check(actual, expected):
    """Compare the complete original payload, not only headline metrics."""
    errors = {"max_absolute_numeric_error": 0.0, "max_relative_numeric_error": 0.0, "numeric_values_compared": 0}
    def walk(a, b, path="root"):
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a) != set(b):
                raise ValueError(f"legacy identity keys differ: {path}")
            for key in a:
                walk(a[key], b[key], f"{path}/{key}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                raise ValueError(f"legacy identity length differs: {path}")
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{path}/{i}")
        elif isinstance(a, (float, int)) and not isinstance(a, bool) and isinstance(b, (float, int)) and not isinstance(b, bool):
            absolute = abs(a - b)
            relative = absolute / max(1, abs(b))
            errors["max_absolute_numeric_error"] = max(errors["max_absolute_numeric_error"], absolute)
            errors["max_relative_numeric_error"] = max(errors["max_relative_numeric_error"], relative)
            errors["numeric_values_compared"] += 1
            if relative > 2e-10:
                raise ValueError(f"legacy identity number differs: {path}")
        elif a != b:
            raise ValueError(f"legacy identity value differs: {path}")
    walk(actual, expected)
    return errors


def month_rows(run):
    metric = run["metrics"]["full_period"]
    days = [d for d in run["daily"] if metric["start_session"] <= d["session"] <= metric["end_session"]]
    points = [days[0]] + [d for i, d in enumerate(days[1:], 1) if i == len(days) - 1 or d["session"][:7] != days[i + 1]["session"][:7]]
    rows = []
    for old, new in zip(points, points[1:]):
        ratio = new["nav"] / old["nav"]
        rows.append({"month": new["session"][:7], "session": new["session"], "run_id": run["run_id"],
                     "policy": run.get("policy", "SPY"), "signal": run["signal"], "phase": run["phase"],
                     "cost_bps_per_side": run["cost_bps_per_side"],
                     "simple_return": ratio - 1, "log_return": __import__("math").log(ratio),
                     "wealth": new["nav"] / days[0]["nav"], "cash_weight": new["cash_weight"]})
    return rows


def run(input_run_dir, output_root, protocol_path):
    input_run_dir = Path(input_run_dir).resolve()
    protocol_path = Path(protocol_path).resolve()
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    config_path = ROOT / protocol["legacy_config"]
    if sha(config_path) != protocol["legacy_config_sha256"]:
        raise ValueError("legacy config is not the frozen input")
    manifest = json.loads((input_run_dir / "manifest.json").read_bytes())
    if manifest["run_id"] != protocol["input_run_id"]:
        raise ValueError("input run differs from prespecified snapshot")
    if sha(input_run_dir / "input-data.json.gz") != protocol["input_data_gzip_sha256"]:
        raise ValueError("normalized input hash mismatch")
    for name, expected in manifest["file_sha256"].items():
        if sha(input_run_dir / name) != expected:
            raise ValueError(f"preserved legacy artifact changed: {name}")
    for name, expected in manifest["code_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"frozen legacy source changed: {name}")
    sources = [Path(__file__), ROOT / "pilot/rebalance_mechanisms.py", ROOT / "pilot/engine.py", ROOT / "spmo_lab/signals.py"]
    source_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    data = read_gzip(input_run_dir / "input-data.json.gz")
    config = json.loads(config_path.read_bytes())
    result = run_policy_matrix(data, config, protocol)
    legacy_reports = []
    for old in result["legacy_result"]["runs"] + result["legacy_result"]["benchmarks"]:
        expected = read_gzip(input_run_dir / (old["run_id"] + ".json.gz"))
        legacy_reports.append({"run_id": old["run_id"], **identity_check(old, expected)})
    del result["legacy_result"]
    if protocol_path.read_bytes() != protocol_bytes or any(sha(ROOT / p) != h for p, h in source_hashes.items()):
        raise ValueError("protocol or implementation changed during execution")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "protocol.json").write_bytes(protocol_bytes)
    (output / "input-data.json.gz").write_bytes((input_run_dir / "input-data.json.gz").read_bytes())
    (output / "legacy-identity.json").write_bytes(encoded({"passed": True, "run_count": len(legacy_reports),
        "max_relative_numeric_error": max(r["max_relative_numeric_error"] for r in legacy_reports), "runs": legacy_reports}))
    all_runs = result["runs"] + result["benchmarks"]
    for path in all_runs:
        (output / (path["run_id"] + ".json.gz")).write_bytes(gzip.compress(encoded(path), mtime=0))
    for period, rows in result["comparisons"].items():
        write_csv(output / f"comparisons-{period}.csv", rows)
    monthly = [row for path in all_runs for row in month_rows(path)]
    if any(len(month_rows(path)) != protocol["expected_month_count"] for path in all_runs):
        raise ValueError("monthly analysis window is incomplete")
    write_csv(output / "monthly-returns.csv", monthly)
    summary = {
        "schema_version": 1, "experiment_id": protocol["experiment_id"], "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "computed_pending_independent_replay_and_analysis", "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "input_run_id": manifest["run_id"], "input_data_gzip_sha256": protocol["input_data_gzip_sha256"],
        "legacy_config_sha256": protocol["legacy_config_sha256"], "code_sha256": source_hashes,
        "strategy_run_count": len(result["runs"]), "benchmark_run_count": len(result["benchmarks"]),
        "boundaries": result["boundaries"], "primary_run_ids": result["primary_run_ids"],
        "checks": result["checks"], "legacy_identity_passed": True,
        "runs": [{key: value for key, value in path.items() if key not in ("daily", "trades", "signals", "target_refreshes")} for path in all_runs],
        "comparisons": {period: rows for period, rows in result["comparisons"].items() if period != "annual"},
        "limitations": protocol["limitations"],
    }
    (output / "summary.json").write_bytes(encoded(summary))
    run_manifest = {"schema_version": 1, "run_id": run_id, "input_run_id": manifest["run_id"],
        "input_manifest_sha256": sha(input_run_dir / "manifest.json"),
        "protocol_sha256": summary["protocol_sha256"], "code_sha256": source_hashes,
        "git_commit_at_execution": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "file_sha256": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}}
    (output / "manifest.json").write_bytes(encoded(run_manifest))
    return {"run_dir": str(output), "strategy_accounts": len(result["runs"]), "benchmark_accounts": len(result["benchmarks"]),
            "legacy_paths_reconciled": len(legacy_reports), "max_legacy_relative_error": max(r["max_relative_numeric_error"] for r in legacy_reports)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/generated/etf-mechanisms")
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs/sector-etf-mechanisms.v1.json")
    args = parser.parse_args()
    print(json.dumps(run(args.input_run_dir, args.output_dir, args.protocol), sort_keys=True))


if __name__ == "__main__":
    main()
