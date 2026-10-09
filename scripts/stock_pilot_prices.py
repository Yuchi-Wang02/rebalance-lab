#!/usr/bin/env python3
"""Capture private Yahoo daily prices for an explicitly supplied stock universe.

No strategy, selection or performance calculation takes place in this module.
All failures, including retired-symbol HTTP 404s, remain in the manifest. There
are no automatic retries and existing unverified files are never overwritten.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ingest_diagnostic import (  # noqa: E402
    DiagnosticError, MAX_BYTES, digest, fetch_bytes, inspect_payload,
    read_json, request_spec, request_url, retrieval_date,
)

WORKERS = 3
START_INTERVAL_SECONDS = 0.25
PRIVATE_USE_NOTICE = "Private research capture; raw Yahoo data is not cleared for public redistribution."


def write_json_exclusive(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    Path(path).chmod(0o444)


def validate_symbols(symbols, start, end):
    if not isinstance(symbols, list) or not symbols:
        raise DiagnosticError("symbols_file_must_be_nonempty_json_list")
    if not all(isinstance(symbol, str) for symbol in symbols):
        raise DiagnosticError("symbols_file_requires_strings")
    if len(set(symbols)) != len(symbols):
        raise DiagnosticError("symbols_file_contains_duplicates")
    for symbol in symbols:
        request_spec([symbol], start, end)
    return symbols


class StartThrottle:
    """Share a request-start interval across the bounded worker pool."""

    def __init__(self, interval=START_INTERVAL_SECONDS):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_start = 0.0

    def wait(self):
        with self.lock:
            delay = max(0.0, self.next_start - time.monotonic())
            if delay:
                time.sleep(delay)
            self.next_start = time.monotonic() + self.interval


def _read_verified(directory, capture, symbol, spec):
    """Verify a recorded request and exact body before allowing any reuse."""
    directory = Path(directory)
    filename = symbol + ".json"
    path = directory / filename
    if (not isinstance(capture, dict) or capture.get("symbol") != symbol
            or capture.get("file") != filename or path.is_symlink()
            or capture.get("http_status") != 200
            or capture.get("request_url") != request_url(symbol, spec)):
        raise DiagnosticError("reuse_capture_metadata_mismatch")
    recorded_spec = capture.get("request")
    if recorded_spec is not None and recorded_spec != spec:
        raise DiagnosticError("reuse_capture_request_mismatch")
    retrieval_date(capture.get("retrieved_at", capture.get("retrieved_at_utc")))
    body = path.read_bytes()
    byte_count = capture.get("byte_count", capture.get("bytes"))
    if len(body) > MAX_BYTES or len(body) != byte_count or digest(body) != capture.get("sha256"):
        raise DiagnosticError("reuse_capture_hash_or_size_mismatch")
    report, _, _, _ = inspect_payload(body, symbol, spec)
    if report["errors"]:
        raise DiagnosticError("reuse_capture_failed_parser_audit")
    return body, report


def _probe_candidates(symbol, spec):
    """Read only our known private feasibility captures, never an arbitrary cache."""
    root = ROOT / "data" / "raw" / "free-price-feasibility"
    if not root.is_dir():
        return
    for manifest_path in sorted(root.glob("*/manifest.json"), reverse=True):
        try:
            if manifest_path.is_symlink():
                continue
            manifest_bytes = manifest_path.read_bytes()
            manifest = read_json(manifest_bytes)
            source_hash = digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes())
            if manifest.get("provider") != "yahoo_chart" or manifest.get("request_source_sha256") != source_hash:
                continue
            for capture in manifest.get("captures", []):
                if not isinstance(capture, dict) or capture.get("symbol") != symbol or capture.get("request") != spec:
                    continue
                try:
                    body, report = _read_verified(manifest_path.parent, capture, symbol, spec)
                except (DiagnosticError, OSError, TypeError, ValueError):
                    continue
                yield body, report, capture, {
                    "kind": "verified_private_feasibility_capture",
                    "source_snapshot": manifest_path.parent.name,
                    "source_manifest_sha256": digest(manifest_bytes),
                }
        except (DiagnosticError, OSError, TypeError, ValueError):
            continue


def capture_symbol(symbol, start, end, output_dir, throttle, reuse_private_probes=True):
    """Return a manifest entry; failures are explicit and never trigger retries."""
    spec = request_spec([symbol], start, end)
    output_dir = Path(output_dir)
    body_path = output_dir / (symbol + ".json")
    capture_path = output_dir / (symbol + ".capture.json")
    base = {"symbol": symbol, "request": spec, "request_url": request_url(symbol, spec)}
    try:
        if capture_path.exists() or body_path.exists():
            if capture_path.is_symlink() or not capture_path.is_file():
                raise DiagnosticError("unverified_existing_output_file")
            capture = read_json(capture_path.read_bytes())
            if capture.get("status") == "failed":
                if (capture.get("symbol") != symbol or capture.get("request") != spec
                        or capture.get("request_url") != base["request_url"]):
                    raise DiagnosticError("existing_failure_request_mismatch")
                return {**capture, "acquisition": "reused_recorded_failure", "automatic_retries": 0}
            if not body_path.is_file():
                raise DiagnosticError("unverified_existing_output_file")
            _, report = _read_verified(output_dir, capture, symbol, spec)
            if capture.get("request_source_sha256") != digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()):
                raise DiagnosticError("existing_capture_parser_source_mismatch")
            return {**capture, "status": "passed", "acquisition": "reused_verified_output", "audit": report}

        candidate = next(_probe_candidates(symbol, spec), None) if reuse_private_probes else None
        if candidate is not None:
            body, report, original, provenance = candidate
            status = 200
            retrieved_at = original.get("retrieved_at", original.get("retrieved_at_utc"))
            acquisition = "reused_verified_private_probe"
        else:
            throttle.wait()
            status, body = fetch_bytes(base["request_url"])
            retrieved_at = datetime.now(timezone.utc).isoformat()
            report, _, _, _ = inspect_payload(body, symbol, spec)
            provenance = {"kind": "live_unauthenticated_https"}
            acquisition = "downloaded"
        # Capture even a parse-invalid 200 response for audit; it remains failed.
        with body_path.open("xb") as stream:
            stream.write(body)
        body_path.chmod(0o444)
        capture = {
            **base, "file": body_path.name, "http_status": status,
            "retrieved_at": retrieved_at, "sha256": digest(body), "byte_count": len(body),
            "request_source_sha256": digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()),
            "downloader_source_sha256": digest(Path(__file__).read_bytes()),
            "provenance": provenance,
            "status": "passed" if not report["errors"] else "failed",
        }
        if report["errors"]:
            capture.update(error="payload_or_data_checks_failed", parser_error_codes=report["errors"])
        write_json_exclusive(capture_path, capture)
        return {**capture, "acquisition": acquisition, "audit": report}
    except DiagnosticError as error:
        code = str(error)
        result = {**base, "status": "failed", "error": code, "automatic_retries": 0}
        if code.startswith("http_status_"):
            try:
                result["http_status"] = int(code.rsplit("_", 1)[1])
            except ValueError:
                pass
        if not capture_path.exists() and not body_path.exists():
            try:
                write_json_exclusive(capture_path, {
                    **result, "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
                    "request_source_sha256": digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()),
                    "downloader_source_sha256": digest(Path(__file__).read_bytes()),
                })
            except OSError:
                pass
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return {**base, "status": "failed", "error": "capture_or_reuse_io_failure", "automatic_retries": 0}


def acquire_prices(symbols, start, end, output_dir, progress=False, reuse_private_probes=True):
    """Acquire exactly the supplied universe; return (manifest_path, manifest)."""
    symbols = validate_symbols(symbols, start, end)
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise DiagnosticError("symlink_output_directory_rejected")
    output_dir = output_dir.resolve()
    if output_dir == ROOT / "site" or ROOT / "site" in output_dir.parents:
        raise DiagnosticError("private_output_directory_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink():
        raise DiagnosticError("symlink_output_directory_rejected")
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    throttle = StartThrottle()
    results = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(capture_symbol, s, start, end, output_dir, throttle, reuse_private_probes): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            results[symbol] = future.result()
            if progress:
                print(json.dumps({"completed": len(results), "total": len(symbols), "symbol": symbol,
                                  "status": results[symbol]["status"],
                                  "error": results[symbol].get("error")}), file=sys.stderr, flush=True)
    ordered = [results[symbol] for symbol in symbols]
    manifest = {
        "schema_version": 1, "provider": "yahoo_chart",
        "purpose": "private_stock_pilot_price_capture_not_original_protocol_acceptance",
        "run_id": run_id, "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols, "start": start, "end_inclusive": end,
        "workers": WORKERS, "request_start_interval_seconds": START_INTERVAL_SECONDS,
        "automatic_retries": 0, "captures": ordered,
        "passed_symbol_count": sum(c["status"] == "passed" for c in ordered),
        "failed_symbol_count": sum(c["status"] != "passed" for c in ordered),
        "all_symbols_passed": all(c["status"] == "passed" for c in ordered),
        "request_source_sha256": digest((ROOT / "scripts" / "ingest_diagnostic.py").read_bytes()),
        "downloader_source_sha256": digest(Path(__file__).read_bytes()),
        "license_note": PRIVATE_USE_NOTICE,
        "limitations": ["Price source adjustment conventions have not been independently verified.",
                        "Successful price capture does not prove membership, capitalization, corporate-action or settlement completeness."],
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path = output_dir / ("manifest." + run_id + ".json")
    write_json_exclusive(manifest_path, manifest)
    return manifest_path, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols-file", required=True, type=Path, help="JSON list of exactly the symbols to acquire")
    parser.add_argument("--output-dir", required=True, type=Path, help="Private immutable capture directory; verified files can be reused")
    parser.add_argument("--start", required=True, help="Inclusive YYYY-MM-DD start")
    parser.add_argument("--end", required=True, help="Inclusive YYYY-MM-DD end")
    args = parser.parse_args(argv)
    try:
        symbols_bytes = args.symbols_file.read_bytes()
        symbols = read_json(symbols_bytes)
        path, manifest = acquire_prices(symbols, args.start, args.end, args.output_dir, progress=True)
        print(json.dumps({"manifest": str(path), "symbols_file_sha256": digest(symbols_bytes),
                          "all_symbols_passed": manifest["all_symbols_passed"],
                          "passed_symbol_count": manifest["passed_symbol_count"],
                          "failed_symbol_count": manifest["failed_symbol_count"]}))
        return 0 if manifest["all_symbols_passed"] else 1
    except (DiagnosticError, OSError, ValueError, TypeError) as error:
        print(json.dumps({"all_symbols_passed": False,
                          "error": str(error) if isinstance(error, DiagnosticError) else "input_or_output_failure"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
