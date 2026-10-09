#!/usr/bin/env python3
"""Capture and audit adjusted Yahoo series for the separately frozen ETF pilot.

This module never computes performance. Network acquisition preserves vendor
bytes; offline replay verifies them before deriving adjusted-price proxies.
"""

import argparse
import hashlib
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ingest_diagnostic import (  # noqa: E402
    DiagnosticError, MAX_BYTES, digest, fetch_bytes, inspect_payload,
    read_json, request_spec, request_url, retrieval_date,
)

CONFIG_PATH = ROOT / "configs" / "sector-etf-pilot.v1.json"
EXPECTED_CALENDAR_VERSION = "4.11.2"
WARNINGS = [
    "vendor_adjusted_total_return_proxy_not_raw_share_accounting",
    "adjustment_and_corporate_action_completeness_not_independently_verified",
    "adjusted_open_is_vendor_open_times_adjclose_over_close",
    "no_separate_dividend_cash_credit_in_adjusted_unit_accounting",
    "original_stock_protocol_not_completed_by_this_pilot",
]


def _json_write(path, obj):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _config_bytes(config):
    """Use the exact frozen file bytes; reject an in-memory override."""
    content = CONFIG_PATH.read_bytes()
    if read_json(content) != config:
        raise DiagnosticError("pilot_config_differs_from_frozen_file")
    return content


def _symbols(config):
    symbols = config.get("universe", []) + [config.get("benchmark")]
    if len(symbols) != 10 or len(set(symbols)) != 10:
        raise DiagnosticError("pilot_requires_nine_distinct_etfs_and_one_benchmark")
    for symbol in symbols:
        request_spec([symbol], config["request_start"], config["request_end"])
    return symbols


def acquire(config, data_root=ROOT / "data"):
    """Sequentially capture each symbol, returning its immutable raw directory.

    Each individual request obeys the existing one-or-two-symbol contract.
    A failed capture is preserved in the manifest and will fail replay audit.
    """
    config_sha = digest(_config_bytes(config))
    symbols = _symbols(config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    raw_dir = Path(data_root).resolve() / "raw" / "sector-etf-pilot" / run_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1, "provider": "yahoo_chart", "run_id": run_id,
        "experiment_id": config["experiment_id"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config_sha,
        "acquisition_script_sha256": digest(Path(__file__).read_bytes()),
        "request_source_sha256": digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()),
        "symbols": symbols, "captures": [], "failures": [],
        "license_note": "Private research capture; raw vendor data is not cleared for redistribution.",
    }
    for symbol in symbols:
        spec = request_spec([symbol], config["request_start"], config["request_end"])
        try:
            url = request_url(symbol, spec)
            status, body = fetch_bytes(url)
            retrieved_at = datetime.now(timezone.utc).isoformat()
            path = raw_dir / (symbol + ".json")
            with path.open("xb") as stream:
                stream.write(body)
            path.chmod(0o444)
            manifest["captures"].append({
                "symbol": symbol, "file": path.name, "request": spec,
                "request_url": url, "http_status": status,
                "retrieved_at": retrieved_at, "sha256": digest(body),
                "byte_count": len(body),
            })
        except DiagnosticError as error:
            manifest["failures"].append({"symbol": symbol, "code": str(error)})
    _json_write(raw_dir / "manifest.json", manifest)
    (raw_dir / "manifest.json").chmod(0o444)
    return raw_dir


def load_and_audit(raw_dir, config):
    """Return (data, audit); data is None whenever any blocking check fails.

    Success data contains ISO sessions and symbol-to-float-list mappings named
    adjusted_open and adjusted_close. Callers must require audit['passed'].
    """
    raw_dir = Path(raw_dir).resolve()
    config_sha = digest(_config_bytes(config))
    symbols = _symbols(config)
    audit = {
        "schema_version": 1, "experiment_id": config["experiment_id"],
        "data_track": config["data_track"], "passed": False,
        "original_stock_protocol_completed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": config_sha, "raw_snapshot_id": raw_dir.name,
        "audit_script_sha256": digest(Path(__file__).read_bytes()),
        "request_source_sha256": digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()),
        "price_convention": "vendor_adjusted_total_return_proxy",
        "adjusted_open_formula": config["adjusted_open_formula"],
        "warnings": list(WARNINGS), "errors": [], "symbols": {},
        "large_adjustment_jump_threshold": 0.05,
        "adjusted_daily_return_block_threshold": 0.50,
        "exchange_calendar": {"name": "XNYS", "expected_version": EXPECTED_CALENDAR_VERSION},
    }
    errors = audit["errors"]
    parsed = {}
    manifest_path = raw_dir / "manifest.json"
    try:
        if manifest_path.is_symlink():
            raise DiagnosticError("symlink_manifest_rejected")
        manifest_bytes = manifest_path.read_bytes()
        manifest = read_json(manifest_bytes)
        audit["raw_manifest_sha256"] = digest(manifest_bytes)
        if (manifest.get("schema_version") != 1 or manifest.get("provider") != "yahoo_chart"
                or manifest.get("experiment_id") != config["experiment_id"]
                or manifest.get("config_sha256") != config_sha
                or manifest.get("symbols") != symbols):
            raise DiagnosticError("manifest_config_or_schema_mismatch")
        if manifest.get("request_source_sha256") != audit["request_source_sha256"]:
            raise DiagnosticError("capture_request_source_changed")
        if manifest.get("acquisition_script_sha256") != audit["audit_script_sha256"]:
            raise DiagnosticError("capture_acquisition_source_changed")
        retrieval_date(manifest.get("created_at_utc"))
        captures = manifest.get("captures")
        if not isinstance(captures, list) or [c.get("symbol") for c in captures] != symbols:
            raise DiagnosticError("missing_duplicate_or_out_of_order_capture")
        if manifest.get("failures") != []:
            raise DiagnosticError("capture_failures_recorded")
        for capture in captures:
            symbol = capture["symbol"]
            spec = request_spec([symbol], config["request_start"], config["request_end"])
            path = raw_dir / (symbol + ".json")
            if (capture.get("file") != path.name or path.is_symlink()
                    or capture.get("request") != spec or capture.get("http_status") != 200
                    or capture.get("request_url") != request_url(symbol, spec)):
                raise DiagnosticError("capture_request_or_path_mismatch_" + symbol)
            if retrieval_date(capture.get("retrieved_at")) <= config["request_end"]:
                raise DiagnosticError("capture_before_requested_end_finalized_" + symbol)
            body = path.read_bytes()
            if (len(body) > MAX_BYTES or len(body) != capture.get("byte_count")
                    or digest(body) != capture.get("sha256")):
                raise DiagnosticError("capture_hash_or_size_mismatch_" + symbol)
            report, rows, event_rows, _ = inspect_payload(body, symbol, spec)
            audit["symbols"][symbol] = {
                "capture_sha256": digest(body), "retrieved_at": capture["retrieved_at"],
                "row_count": report["row_count"], "actual_date_bounds": report["actual_date_bounds"],
                "metadata": report["metadata"], "per_field_missingness": report["per_field_missingness"],
                "complete_ohlc_rows": report["complete_ohlc_rows"],
                "incomplete_ohlc_rows": report["incomplete_ohlc_rows"],
                "event_counts": report["event_counts"],
                "event_date_semantics": "vendor_ex_event_dates_not_verified_cash_payment_dates",
                "parser_errors": report["errors"],
            }
            errors.extend(symbol + ":" + code for code in report["errors"])
            if not report["errors"] and rows:
                parsed[symbol] = (rows, event_rows)
    except (DiagnosticError, OSError, ValueError, TypeError, KeyError) as error:
        errors.append(str(error) if isinstance(error, DiagnosticError) else "manifest_or_capture_read_failure")
        return None, audit

    try:
        import exchange_calendars as xcals
        audit["exchange_calendar"]["version"] = xcals.__version__
        if xcals.__version__ != EXPECTED_CALENDAR_VERSION:
            raise DiagnosticError("exchange_calendar_version_mismatch")
        calendar = xcals.get_calendar("XNYS", start=config["request_start"], end=config["request_end"])
        expected = [session.strftime("%Y-%m-%d") for session in calendar.sessions]
        expected_set = set(expected)
        audit["exchange_calendar"].update({"requested_start": config["request_start"],
                                           "requested_end": config["request_end"],
                                           "requested_session_count": len(expected)})
    except (ImportError, DiagnosticError, ValueError, TypeError) as error:
        errors.append(str(error) if isinstance(error, DiagnosticError) else "exchange_calendar_unavailable")
        return None, audit
    if len(parsed) != len(symbols):
        errors.append("one_or_more_symbols_failed_vendor_parse")
        return None, audit

    common_first = max(parsed[symbol][0][0]["session_date"] for symbol in config["universe"])
    common_sessions = [day for day in expected if common_first <= day <= config["request_end"]]
    audit["common_first_session"] = common_first
    audit["common_last_session"] = common_sessions[-1] if common_sessions else None
    audit["common_session_count"] = len(common_sessions)
    warmup = [day for day in common_sessions if day <= config["initial_signal_on_or_before"]]
    audit["initial_signal_session"] = warmup[-1] if warmup else None
    audit["warmup_observations_through_initial_signal"] = len(warmup)
    if len(warmup) < 253:
        errors.append("insufficient_253_observation_warmup")
    if not common_sessions or common_sessions[-1] != config["request_end"]:
        errors.append("requested_end_is_not_common_exchange_session")
    data = {"sessions": common_sessions, "adjusted_open": {}, "adjusted_close": {}}
    for symbol, (rows, event_rows) in parsed.items():
        symbol_audit = audit["symbols"][symbol]
        observed = [row["session_date"] for row in rows]
        unexpected = sorted(set(observed) - expected_set)
        relevant = [row for row in rows if row["session_date"] >= common_first]
        days = [row["session_date"] for row in relevant]
        missing = sorted(set(common_sessions) - set(days))
        symbol_audit.update({"unexpected_non_session_dates": unexpected,
                             "missing_common_sessions": missing,
                             "trimmed_pre_common_rows": len(rows) - len(relevant),
                             "common_session_count": len(relevant),
                             "common_dates_match": days == common_sessions})
        if unexpected:
            errors.append(symbol + ":observations_outside_exchange_sessions")
        if days != common_sessions:
            errors.append(symbol + ":common_session_sequence_mismatch")
        event_off_session = sorted({event["vendor_event_date"] for event in event_rows
                                    if event["vendor_event_date"] not in expected_set})
        symbol_audit["event_dates_outside_exchange_sessions"] = event_off_session
        if event_off_session:
            errors.append(symbol + ":events_outside_exchange_sessions")
        ratios = [row["adjclose"] / row["close"] for row in relevant]
        opens = [row["open"] * ratio for row, ratio in zip(relevant, ratios)]
        closes = [row["adjclose"] for row in relevant]
        if any(not math.isfinite(x) or x <= 0 for x in opens + closes + ratios):
            errors.append(symbol + ":invalid_derived_adjusted_value")
        jumps, large_returns = [], []
        events_by_date = {}
        for event in event_rows:
            events_by_date.setdefault(event["vendor_event_date"], []).append(event["event_type"])
        for index in range(1, len(relevant)):
            ratio_change = ratios[index] / ratios[index - 1] - 1
            daily_return = closes[index] / closes[index - 1] - 1
            if abs(ratio_change) > audit["large_adjustment_jump_threshold"]:
                jumps.append({"session": days[index], "ratio_change": ratio_change,
                              "same_day_event_types": events_by_date.get(days[index], [])})
            if abs(daily_return) > audit["adjusted_daily_return_block_threshold"]:
                large_returns.append({"session": days[index], "adjusted_close_return": daily_return})
        symbol_audit.update({"adjustment_ratio_min": min(ratios) if ratios else None,
                             "adjustment_ratio_max": max(ratios) if ratios else None,
                             "large_adjustment_jumps": jumps,
                             "adjusted_daily_return_outliers": large_returns})
        if jumps:
            audit["warnings"].append(symbol + ":large_adjustment_ratio_jumps_require_interpretation")
        if large_returns:
            errors.append(symbol + ":adjusted_daily_return_exceeds_50_percent")
        data["adjusted_open"][symbol] = opens
        data["adjusted_close"][symbol] = closes
    audit["passed"] = not errors
    return (data if audit["passed"] else None), audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--acquire", action="store_true")
    mode.add_argument("--raw-dir", type=Path)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--audit-output", type=Path, help="Private output directory for audit.json and data.json")
    args = parser.parse_args(argv)
    raw_dir = None
    try:
        config = read_json(CONFIG_PATH.read_bytes())
        raw_dir = acquire(config, args.data_root) if args.acquire else args.raw_dir
        data, audit = load_and_audit(raw_dir, config)
        if args.audit_output:
            output = args.audit_output.resolve()
            if output == (ROOT / "site") or ROOT / "site" in output.parents:
                raise DiagnosticError("private_audit_output_required")
            output.mkdir(parents=True, exist_ok=False)
            _json_write(output / "audit.json", audit)
            if data is not None:
                _json_write(output / "data.json", data)
        print(json.dumps({"passed": audit["passed"], "raw_dir": str(raw_dir),
                          "common_session_count": audit.get("common_session_count"),
                          "common_first_session": audit.get("common_first_session"),
                          "common_last_session": audit.get("common_last_session"),
                          "errors": audit["errors"]}, allow_nan=False))
        return 0 if audit["passed"] else 1
    except (DiagnosticError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"passed": False, "raw_dir": str(raw_dir) if raw_dir else None,
                          "error": str(error) if isinstance(error, DiagnosticError) else "pilot_data_io_or_configuration_failure"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
