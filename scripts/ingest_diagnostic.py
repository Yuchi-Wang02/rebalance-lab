#!/usr/bin/env python3
"""Preserve and inspect a small Yahoo chart sample; never run a backtest."""

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
FIELDS = ("open", "high", "low", "close", "volume", "adjclose")
MAX_BYTES = 10_000_000
WARNINGS = [
    "exchange_calendar_coverage_unverified",
    "vendor_OHLC_adjustments_and_raw_execution_prices_unverified",
    "adjclose_kept_separate_no_total_returns_derived",
    "vendor_action_dates_are_not_verified_dividend_payment_dates",
    "historical_membership_market_caps_and_point_in_time_integrity_unverified",
]


class DiagnosticError(Exception):
    """A safe error code, without server bodies or credential-bearing URLs."""


def digest(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    serialized = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)


def read_json(content):
    def invalid_constant(_):
        raise ValueError("nonstandard_json_number")

    try:
        return json.loads(content, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, TypeError) as error:
        raise DiagnosticError("invalid_json") from error


def request_spec(symbols, start, end):
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= 2:
        raise DiagnosticError("provide_one_or_two_symbols")
    if any(not isinstance(s, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", s) for s in symbols):
        raise DiagnosticError("invalid_symbol")
    if len(set(symbols)) != len(symbols):
        raise DiagnosticError("duplicate_symbol")
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first.isoformat() != start or last.isoformat() != end or first > last:
            raise ValueError
        last + timedelta(days=1)
    except (ValueError, TypeError, OverflowError) as error:
        raise DiagnosticError("invalid_date_range") from error
    return {"symbols": symbols, "start": start, "end_inclusive": end,
            "interval": "1d", "currency": "USD", "timezone": "America/New_York"}


def request_url(symbol, spec):
    first = date.fromisoformat(spec["start"])
    after_last = date.fromisoformat(spec["end_inclusive"]) + timedelta(days=1)
    params = {"period1": int(datetime.combine(first, time.min, NY).timestamp()),
              "period2": int(datetime.combine(after_last, time.min, NY).timestamp()),
              "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"}
    return "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol + "?" + urllib.parse.urlencode(params)


def fetch_bytes(url):
    """Use urllib's verified TLS and existing proxy configuration unchanged."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SPMO-Research-Diagnostic/1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            body = response.read(MAX_BYTES + 1)
        if status != 200:
            raise DiagnosticError(f"http_status_{status}")
        if len(body) > MAX_BYTES:
            raise DiagnosticError("response_too_large")
        return status, body
    except urllib.error.HTTPError as error:
        raise DiagnosticError(f"http_status_{error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise DiagnosticError("transport_failure") from None


def numeric(value, *, positive=False):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except (OverflowError, ValueError):
        return False


def session_date(timestamp):
    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
        raise DiagnosticError("invalid_timestamp")
    try:
        return datetime.fromtimestamp(timestamp, NY).date().isoformat()
    except (ValueError, OverflowError, OSError) as error:
        raise DiagnosticError("invalid_timestamp") from error


def retrieval_date(retrieved_at):
    """Interpret capture context, never the wall clock of an offline replay."""
    if not isinstance(retrieved_at, str):
        raise DiagnosticError("invalid_retrieval_timestamp")
    try:
        recorded = datetime.fromisoformat(retrieved_at)
        if recorded.tzinfo is None or recorded.utcoffset() is None:
            raise ValueError("timezone_required")
        return recorded.astimezone(NY).date().isoformat()
    except (ValueError, TypeError, OverflowError) as error:
        raise DiagnosticError("invalid_retrieval_timestamp") from error


def inspect_payload(body, symbol, spec):
    report = {"symbol": symbol, "errors": [], "warnings": list(WARNINGS),
              "research_ready": False, "row_count": 0, "actual_date_bounds": None,
              "complete_ohlc_rows": None, "missing_ohlc_rows": None,
              "invalid_ohlc_rows": None, "incomplete_ohlc_rows": None,
              "per_field_missingness": {}, "event_counts": {}, "events_extracted": False, "metadata": {}}
    rows, event_rows, events = [], [], {}
    errors = report["errors"]
    try:
        payload = read_json(body)
        chart = payload.get("chart") if isinstance(payload, dict) else None
        if not isinstance(chart, dict) or "error" not in chart:
            raise DiagnosticError("invalid_chart_shape")
        if chart["error"] is not None:
            raise DiagnosticError("chart_error")
        result = chart.get("result")
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise DiagnosticError("expected_one_chart_result")
        result = result[0]
        meta = result.get("meta")
        if not isinstance(meta, dict):
            raise DiagnosticError("missing_metadata")
        for key, expected in (("symbol", symbol), ("currency", "USD"),
                              ("exchangeTimezoneName", "America/New_York"), ("dataGranularity", "1d")):
            if meta.get(key) != expected:
                raise DiagnosticError("metadata_mismatch_" + key)
        report["metadata"] = {key: meta.get(key) for key in
                              ("symbol", "currency", "exchangeTimezoneName", "dataGranularity", "exchangeName")}
        stamps = result.get("timestamp")
        if not isinstance(stamps, list) or not stamps:
            raise DiagnosticError("missing_timestamps")
        report["row_count"] = len(stamps)
        indicators = result.get("indicators", {})
        quotes, adjusted = indicators.get("quote"), indicators.get("adjclose")
        if not isinstance(quotes, list) or len(quotes) != 1 or not isinstance(quotes[0], dict):
            raise DiagnosticError("invalid_quote_shape")
        if not isinstance(adjusted, list) or len(adjusted) != 1 or not isinstance(adjusted[0], dict):
            raise DiagnosticError("invalid_adjclose_shape")
        columns = dict(quotes[0], adjclose=adjusted[0].get("adjclose"))
        for field in FIELDS:
            values = columns.get(field)
            if not isinstance(values, list) or len(values) != len(stamps):
                raise DiagnosticError("array_length_mismatch_" + field)
            report["per_field_missingness"][field] = sum(v is None for v in values)
        previous_stamp, previous_date = None, None
        dates = []
        report.update(complete_ohlc_rows=0, missing_ohlc_rows=0, invalid_ohlc_rows=0, incomplete_ohlc_rows=0)
        for index, stamp in enumerate(stamps):
            try:
                day = session_date(stamp)
            except DiagnosticError:
                day = ""
                errors.append(f"row_{index}:invalid_timestamp")
            if day:
                if previous_stamp is not None and stamp <= previous_stamp:
                    errors.append(f"row_{index}:duplicate_or_nonmonotonic_timestamp")
                if previous_date is not None and day <= previous_date:
                    errors.append(f"row_{index}:duplicate_or_nonmonotonic_session_date")
                if not spec["start"] <= day <= spec["end_inclusive"]:
                    errors.append(f"row_{index}:outside_requested_dates")
                previous_stamp, previous_date = stamp, day
                dates.append(day)
            row = {"symbol": symbol, "vendor_timestamp": stamp, "session_date": day}
            row.update({field: columns[field][index] for field in FIELDS})
            for field in FIELDS:
                if not numeric(row[field], positive=field != "volume"):
                    errors.append(f"row_{index}:missing_or_invalid_{field}")
            ohlc = ("open", "high", "low", "close")
            complete = all(numeric(row[f], positive=True) for f in ohlc)
            if complete:
                complete = row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]
                if not complete:
                    errors.append(f"row_{index}:invalid_high_low_bounds")
            if complete:
                report["complete_ohlc_rows"] += 1
            else:
                report["incomplete_ohlc_rows"] += 1
                key = "missing_ohlc_rows" if any(row[f] is None for f in ohlc) else "invalid_ohlc_rows"
                report[key] += 1
            rows.append(row)
        if dates:
            report["actual_date_bounds"] = {"first": min(dates), "last": max(dates)}
        events = result.get("events", {})
        if not isinstance(events, dict):
            raise DiagnosticError("invalid_events_shape")
        for kind, entries in events.items():
            if not isinstance(entries, dict):
                raise DiagnosticError("invalid_event_collection")
            report["event_counts"][kind] = len(entries)
            if kind not in ("dividends", "splits"):
                errors.append("unsupported_event_type")
                continue
            for key, event in entries.items():
                if not isinstance(event, dict):
                    raise DiagnosticError("invalid_event_shape")
                day = session_date(event.get("date"))
                if key != str(event["date"]) or not spec["start"] <= day <= spec["end_inclusive"]:
                    errors.append("event_timestamp_or_range_invalid")
                if kind == "dividends" and not numeric(event.get("amount"), positive=True):
                    errors.append("invalid_dividend_amount")
                if kind == "splits" and not all(numeric(event.get(k), positive=True) for k in ("numerator", "denominator")):
                    errors.append("invalid_split_ratio")
                event_rows.append({"symbol": symbol, "event_type": kind, "vendor_timestamp": event["date"],
                                   "vendor_event_date": day, **{k: event.get(k) for k in
                                   ("amount", "numerator", "denominator", "splitRatio")}})
        report["events_extracted"] = True
    except DiagnosticError as error:
        errors.append(str(error))
    except (AttributeError, TypeError, KeyError, ValueError):
        errors.append("invalid_payload_shape")
    report["diagnostic_passed"] = not errors
    return report, rows, event_rows, events


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def replay_source(raw_dir):
    manifest_path = raw_dir / "manifest.json"
    if manifest_path.is_symlink():
        raise DiagnosticError("replay_manifest_symlink")
    manifest_bytes = manifest_path.read_bytes()
    original = read_json(manifest_bytes)
    if not isinstance(original, dict) or original.get("schema_version") != 1 or original.get("provider") != "yahoo_chart":
        raise DiagnosticError("invalid_replay_manifest")
    source = original.get("request")
    if not isinstance(source, dict):
        raise DiagnosticError("invalid_replay_request")
    spec = request_spec(source["symbols"], source["start"], source["end_inclusive"])
    if source != spec or not isinstance(original.get("captures"), list):
        raise DiagnosticError("invalid_replay_request")
    captures = original["captures"]
    if not all(isinstance(item, dict) for item in captures):
        raise DiagnosticError("invalid_replay_capture")
    if [item.get("symbol") for item in captures] != spec["symbols"]:
        raise DiagnosticError("incomplete_or_duplicate_replay_captures")
    verified = []
    for item in captures:
        symbol = item["symbol"]
        filename = symbol + ".json"
        path = raw_dir / filename
        if item.get("file") != filename or path.is_symlink() or item.get("http_status") != 200:
            raise DiagnosticError("invalid_replay_capture")
        if item.get("request_url") != request_url(symbol, spec):
            raise DiagnosticError("replay_request_url_mismatch")
        retrieval_date(item.get("retrieved_at"))
        body = path.read_bytes()
        if len(body) > MAX_BYTES or digest(body) != item.get("sha256") or len(body) != item.get("byte_count"):
            raise DiagnosticError("replay_raw_hash_or_size_mismatch")
        verified.append((item, body))
    return spec, verified, digest(manifest_bytes)


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    raw_dir = args.data_dir.resolve() / "raw" / "yahoo" / run_id
    processed_dir = args.data_dir.resolve() / "processed" / "yahoo" / run_id
    raw_dir.mkdir(parents=True, exist_ok=False)
    processed_dir.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "provider": "yahoo_chart", "run_id": run_id,
                "mode": "offline_replay" if args.raw_dir else "live", "request": None,
                "script_sha256": digest(Path(__file__).read_bytes()), "captures": [], "failures": [],
                "research_ready": False, "created_at": datetime.now(timezone.utc).isoformat()}
    quality = {"research_ready": False, "diagnostic_passed": False, "symbols": [], "errors": [],
               "warnings": list(WARNINGS), "exchange_calendar_coverage": "unverified",
               "vendor_OHLC_adjustments": "unverified", "symbol_session_agreement": None,
               "session_agreement_is_exchange_calendar_proof": False,
               "ohlc_count_definitions": {"complete": "finite_positive_and_coherent_high_low_bounds",
                                          "missing": "at_least_one_null_OHLC_field",
                                          "invalid": "no_null_OHLC_but_invalid_number_or_bounds",
                                          "incomplete": "missing_plus_invalid; complete_plus_incomplete_equals_row_count",
                                          "unassessable_shape": "counts_are_null"}}
    try:
        replay = None
        if args.raw_dir:
            spec, replay, source_hash = replay_source(args.raw_dir.resolve())
            manifest["source_raw_manifest_sha256"] = source_hash
            if ((args.symbols is not None and args.symbols != spec["symbols"])
                    or (args.start is not None and args.start != spec["start"])
                    or (args.end is not None and args.end != spec["end_inclusive"])):
                raise DiagnosticError("offline_request_override_mismatch")
        else:
            config = read_json((ROOT / "configs" / "experiment.v1.json").read_bytes())
            spec = request_spec(args.symbols or ["SPMO", "SPY"],
                                args.start or config["period"]["warmup_request_start"],
                                args.end or config["period"]["report_end_close"])
        manifest["request"] = spec
        session_sets = []
        for index, symbol in enumerate(spec["symbols"]):
            try:
                url = request_url(symbol, spec)
                if replay is None:
                    status, body = fetch_bytes(url)
                    retrieved_at = datetime.now(timezone.utc).isoformat()
                else:
                    source, body = replay[index]
                    status, retrieved_at = source["http_status"], source["retrieved_at"]
                with (raw_dir / (symbol + ".json")).open("xb") as stream:
                    stream.write(body)
                (raw_dir / (symbol + ".json")).chmod(0o444)
                manifest["captures"].append({"symbol": symbol, "file": symbol + ".json", "http_status": status,
                                            "request_url": url, "retrieved_at": retrieved_at,
                                            "sha256": digest(body), "byte_count": len(body)})
                if spec["end_inclusive"] >= retrieval_date(retrieved_at):
                    warning = "request_includes_current_or_future_date_possible_partial_bars"
                    if warning not in quality["warnings"]:
                        quality["warnings"].append(warning)
                report, rows, event_rows, events = inspect_payload(body, symbol, spec)
                quality["symbols"].append(report)
                if report["errors"]:
                    manifest["failures"].append({"symbol": symbol, "code": "payload_or_data_checks_failed"})
                if rows:
                    write_csv(processed_dir / (symbol + ".csv"), rows,
                              ("symbol", "vendor_timestamp", "session_date", *FIELDS))
                    session_sets.append([row["session_date"] for row in rows])
                write_json(processed_dir / (symbol + ".events.json"),
                           {"symbol": symbol, "extraction_completed": report["events_extracted"],
                            "date_semantics": "vendor_event_date_not_verified_pay_date", "events": events})
                write_csv(processed_dir / (symbol + ".events.csv"), event_rows,
                          ("symbol", "event_type", "vendor_timestamp", "vendor_event_date", "amount", "numerator", "denominator", "splitRatio"))
            except DiagnosticError as error:
                manifest["failures"].append({"symbol": symbol, "code": str(error)})
        if len(session_sets) == len(spec["symbols"]):
            quality["symbol_session_agreement"] = all(days == session_sets[0] for days in session_sets)
            if not quality["symbol_session_agreement"]:
                quality["errors"].append("symbol_session_dates_differ")
    except DiagnosticError as error:
        manifest["failures"].append({"code": str(error)})
    except (OSError, ValueError, KeyError, TypeError):
        manifest["failures"].append({"code": "configuration_replay_or_filesystem_failure"})
    quality["diagnostic_passed"] = not manifest["failures"] and not quality["errors"] and bool(quality["symbols"])
    quality["failure_records"] = manifest["failures"]
    manifest["diagnostic_passed"] = quality["diagnostic_passed"]
    write_json(raw_dir / "manifest.json", manifest)
    (raw_dir / "manifest.json").chmod(0o444)
    write_json(processed_dir / "quality_report.json", quality)
    derived = {path.name: digest(path.read_bytes()) for path in sorted(processed_dir.iterdir())}
    write_json(processed_dir / "manifest.json", {**manifest, "raw_manifest_sha256": digest((raw_dir / "manifest.json").read_bytes()),
                                                "derived_file_sha256": derived})
    print(json.dumps({"diagnostic_passed": quality["diagnostic_passed"], "research_ready": False,
                      "raw_dir": str(raw_dir), "processed_dir": str(processed_dir)}))
    return 0 if quality["diagnostic_passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", help="One or two uppercase symbols; default SPMO SPY")
    parser.add_argument("--start", help="Inclusive first date; default from experiment config")
    parser.add_argument("--end", help="Inclusive last date; default from experiment config")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data", help="Output root; default project-root/data")
    parser.add_argument("--raw-dir", type=Path, help="Replay a prior raw snapshot with SHA-256 verification and no network")
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError):
        print(json.dumps({"diagnostic_passed": False, "research_ready": False, "error": "output_path_conflict_or_io_failure"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
