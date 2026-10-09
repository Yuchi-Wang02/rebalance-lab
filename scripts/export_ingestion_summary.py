#!/usr/bin/env python3
"""Export aggregate diagnostics after checking a saved run and its offline replay."""

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PUBLIC_WARNINGS = {
    "exchange_calendar_coverage_unverified",
    "vendor_OHLC_adjustments_and_raw_execution_prices_unverified",
    "adjclose_kept_separate_no_total_returns_derived",
    "vendor_action_dates_are_not_verified_dividend_payment_dates",
    "historical_membership_market_caps_and_point_in_time_integrity_unverified",
    "request_includes_current_or_future_date_possible_partial_bars",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_verified(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    hashes = manifest["derived_file_sha256"]
    if "quality_report.json" not in hashes:
        raise ValueError("Missing quality report hash")
    for name, expected in hashes.items():
        path = directory / name
        if Path(name).name != name or path.is_symlink() or sha256(path) != expected:
            raise ValueError("Derived output hash mismatch or unsafe path")
    quality = json.loads((directory / "quality_report.json").read_text())
    if manifest["research_ready"] is not False or quality["research_ready"] is not False:
        raise ValueError("Diagnostic cannot declare research readiness")
    return manifest, quality


def export_summary(processed_dir, replay_dir):
    original, quality = read_verified(processed_dir)
    replay, replay_quality = read_verified(replay_dir)
    if (original["mode"] != "live" or replay["mode"] != "offline_replay"
            or original["provider"] != "yahoo_chart" or replay["provider"] != "yahoo_chart"
            or original["request"] != replay["request"]
            or original["script_sha256"] != replay["script_sha256"]
            or original["raw_manifest_sha256"] != replay["source_raw_manifest_sha256"]
            or original["derived_file_sha256"] != replay["derived_file_sha256"]
            or quality != replay_quality):
        raise ValueError("Replay does not reproduce the selected source run")
    capture_hashes = lambda m: [(c["symbol"], c["sha256"], c["byte_count"]) for c in m["captures"]]
    if capture_hashes(original) != capture_hashes(replay):
        raise ValueError("Replay raw captures do not match the source")
    spec = original["request"]
    if spec["symbols"] != ["SPMO", "SPY"]:
        raise ValueError("The public experiment summary requires SPMO and SPY")
    if (quality["exchange_calendar_coverage"] != "unverified"
            or quality["vendor_OHLC_adjustments"] != "unverified"):
        raise ValueError("Diagnostic cannot certify calendar or adjustment semantics")
    if (not isinstance(quality["warnings"], list)
            or any(not isinstance(w, str) or w not in PUBLIC_WARNINGS for w in quality["warnings"])):
        raise ValueError("Only known public warning codes may be exported")
    captures = {c["symbol"]: c for c in original["captures"]}
    reports = {r["symbol"]: r for r in quality["symbols"]}
    if set(captures) != set(spec["symbols"]) or set(reports) != set(spec["symbols"]):
        raise ValueError("Cannot export incomplete captures; keep the prior public summary")
    symbols = []
    for symbol in spec["symbols"]:
        report, capture = reports[symbol], captures[symbol]
        bounds = report["actual_date_bounds"] or {}
        symbols.append({
            "symbol": symbol, "observed_start": bounds.get("first"),
            "observed_end": bounds.get("last"), "rows": report["row_count"],
            "complete_ohlc_rows": report["complete_ohlc_rows"],
            "missing_ohlc_rows": report["missing_ohlc_rows"],
            "invalid_ohlc_rows": report["invalid_ohlc_rows"],
            "error_count": len(report["errors"]), "warning_count": len(report["warnings"]),
            "raw_sha256": capture["sha256"], "retrieved_at_utc": capture["retrieved_at"],
        })
    return {
        "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": original["run_id"], "replay_run_id": replay["run_id"],
        "source_script_sha256": original["script_sha256"],
        "quality_report_sha256": original["derived_file_sha256"]["quality_report.json"],
        "requested_start": spec["start"], "requested_end": spec["end_inclusive"],
        "diagnostic_passed": quality["diagnostic_passed"], "research_ready": False,
        "calendar_coverage": "not_verified", "price_adjustment_semantics": "not_verified",
        "cache_replay_verified": True, "symbols": symbols,
        "cross_symbol_dates_agree": quality["symbol_session_agreement"],
        "global_error_count": len(quality["errors"]),
        "warnings": quality["warnings"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--replay-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    temporary = None
    try:
        summary = export_summary(args.processed_dir, args.replay_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(summary, indent=2, allow_nan=False) + "\n"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent,
                                         prefix=".ingestion-summary-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(args.output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("FAIL: summary not exported; check complete source/replay manifests and output hashes.")
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("PASS: exported aggregate diagnostics with verified offline reproduction; research_ready=false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
