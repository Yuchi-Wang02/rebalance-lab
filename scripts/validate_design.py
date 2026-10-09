#!/usr/bin/env python3
"""Check limited design invariants and local links; never run a market backtest."""

import json
import hashlib
import math
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for name in ("href", "src"):
            if attrs.get(name):
                self.targets.append(attrs[name])


def validate(root: Path) -> list[str]:
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    config = json.loads((root / "configs/experiment.v1.json").read_text(encoding="utf-8"))
    status = json.loads((root / "results/status.json").read_text(encoding="utf-8"))
    original_status = status.get("studies", {}).get("original_stock", {})
    catalog = json.loads((root / "configs/data-sources.json").read_text(encoding="utf-8"))
    period, common, arms = config["period"], config["common"], config["arms"]
    dates = [date.fromisoformat(period[key]) for key in ("warmup_request_start", "initial_signal_close", "report_anchor_close", "report_end_close")]
    require(all(a < b for a, b in zip(dates, dates[1:])), "Warmup, initialization, reporting anchor and end must be ordered.")
    require(period["burn_in_year"] == 2025 and period["anchor_action"] == "normalize_existing_nav_without_trading", "YTD requires established holdings and no artificial reporting-boundary trade.")
    require(not period["initialization_costs_recharged_at_anchor"], "Initialization costs cannot be charged again at the YTD anchor.")
    require(period["warmup_min_price_points"] >= max(config["signal_definition"]["lookback_sessions"]) + 1, "A 252-session interval requires 253 price points.")
    require(period["classification"] == "retrospective_exploratory", "The 2026 investigation remains exploratory.")
    require(set(arms) == {"S12", "M12", "SMIX", "MMIX"}, "The primary design must have exactly the four declared factorial arms.")
    for name, arm in arms.items():
        weights = arm["signal_weights"]
        require(len(weights) == len(config["signal_definition"]["lookback_sessions"]), f"{name}: signal windows/weights mismatch.")
        require(all(math.isfinite(w) and w >= 0 for w in weights) and math.isclose(sum(weights), 1), f"{name}: invalid signal weights.")
    for monthly, semiannual in [("M12", "S12"), ("MMIX", "SMIX")]:
        changed = {key for key in arms[monthly].keys() | arms[semiannual].keys() if arms[monthly].get(key) != arms[semiannual].get(key)}
        require(changed == {"rebalance"}, f"{monthly}/{semiannual}: frequency controls must differ only in rebalance.")
        require(arms[monthly]["rebalance"] == "monthly" and arms[semiannual]["rebalance"] == "semiannual", "Frequency labels do not match the factorial arms.")
    require(arms["S12"]["signal_weights"] == [1, 0, 0] and arms["SMIX"]["signal_weights"] == [0.5, 0.3, 0.2], "Declared signal recipes must remain explicit.")
    require(common["target_count"] == 75 and 0 < common["security_weight_cap"] <= 1, "Invalid common portfolio constraints.")
    require(not common["buffer"] and not common["entry_trend_filter"] and not common["weekly_risk_overlay"], "Deferred overlays must not enter the primary design.")
    require("insufficient_candidates_equity_budget" not in common, "The old N/K cash overlay is not part of v0.2.")
    require(common["execution_time"] == "next_exchange_session_open", "Closing signals cannot trade at that same close.")
    require(common["cost_bps_per_side_base"] == 5 and sorted(common["cost_bps_per_side_scenarios"]) == [0, 5, 10, 25], "Prespecified cost scenarios changed.")
    comparisons = config["comparisons"]
    require(comparisons["primary_frequency"] == ["M12", "S12"] and comparisons["replication_frequency"] == ["MMIX", "SMIX"], "Primary and within-study robustness comparisons must not be swapped after seeing outcomes.")
    require(comparisons["interaction"] == {"positive_pair": ["MMIX", "SMIX"], "negative_pair": ["M12", "S12"]}, "Interaction definition disagrees with the protocol.")
    known = set(arms) | set(config["benchmarks"]["tradeable"])
    for pair in comparisons["product_context"]:
        require(len(pair) == 2 and all(x in known for x in pair), f"Unknown product comparison: {pair}.")
    require(not config["results"]["executed"] and config["results"]["market_returns"] is None, "No market result has been generated in this release.")
    require(status["schema_version"] == 2 and status["market_backtest_executed"] is True, "Project status must recognize completed market studies.")
    require(original_status["stage"] == "synthetic_engine_validation" and original_status["engine_implemented"] is True and original_status["engine_status"] == "synthetic_prototype" and original_status["formal_engine_accepted"] is False and not original_status["data_audit_completed"] and not original_status["market_backtest_executed"] and original_status["returns"] is None, "Original-stock status must distinguish synthetic implementation from market acceptance.")
    engine = json.loads((root / "site/data/engine-status.json").read_text(encoding="utf-8"))
    require(engine["engine_status"] == "synthetic_prototype" and engine["data_track"] == "synthetic" and engine["formal_engine_accepted"] is False and engine["market_backtest_executed"] is False and engine["research_ready"] is False, "Synthetic receipt cannot claim market readiness.")
    require(engine["run_count"] == 16 and engine["strategy_ids"] == list(arms) and engine["cost_bps"] == common["cost_bps_per_side_scenarios"], "Synthetic receipt must include every arm and cost scenario.")
    require(engine["checks"] and all(v is True for v in engine["checks"].values()), "Synthetic engineering checks must pass.")
    require(engine["config_sha256"] == hashlib.sha256((root / "configs/experiment.v1.json").read_bytes()).hexdigest(), "Synthetic receipt uses a different configuration.")
    expected_code = {"scripts/run_synthetic.py", *[p.relative_to(root).as_posix() for p in (root / "spmo_lab").glob("*.py")]}
    require(set(engine["code_sha256"]) == expected_code, "Synthetic receipt must identify every engine module.")
    for name, digest in engine["code_sha256"].items():
        require(name in expected_code and hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, "Synthetic receipt code hash mismatch; rerun the fixture.")
    sensitivity_path = root / "configs/calendar-sensitivity.v1.json"
    sensitivity = json.loads(sensitivity_path.read_text(encoding="utf-8"))
    calendar = json.loads((root / "site/data/calendar-sensitivity-status.json").read_text(encoding="utf-8"))
    primary_hash = hashlib.sha256((root / "configs/experiment.v1.json").read_bytes()).hexdigest()
    phases = [[month, month + 6] for month in range(1, 7)]
    require(sensitivity["phase_pairs"] == calendar["phase_pairs"] == phases, "Calendar sensitivity must retain all six prespecified phases.")
    require(sensitivity["primary_reference_phase"] == calendar["primary_reference_phase"] == [3, 9], "The primary March/September schedule cannot change.")
    require(sensitivity["primary_config_sha256"] == calendar["primary_config_sha256"] == primary_hash, "Calendar sensitivity must reference the unchanged primary configuration.")
    require(calendar["sensitivity_config_sha256"] == hashlib.sha256(sensitivity_path.read_bytes()).hexdigest(), "Calendar receipt uses a different supplementary specification.")
    for record in (sensitivity, calendar):
        require(record["experiment_track"] == "calendar_phase_sensitivity" and record["market_backtest_executed"] is False and record["research_ready"] is False, "Calendar sensitivity must remain a separately labeled non-market exercise.")
        require(record["report_all_phases"] is True and record["promote_best_phase"] is False, "Every phase must be reported without promoting a winner.")
        require([record[k] for k in ("monthly_control_count", "semiannual_run_count", "unique_run_count", "paired_contrast_count")] == [8, 48, 56, 48], "Calendar counts must reflect reused monthly controls and all paired contrasts.")
    require(calendar["data_track"] == "synthetic" and calendar["checks"] and all(v is True for v in calendar["checks"].values()), "Calendar receipt must retain passing synthetic checks.")
    calendar_code = (expected_code - {"scripts/run_synthetic.py"}) | {"scripts/run_calendar_sensitivity.py"}
    require(set(calendar["code_sha256"]) == calendar_code, "Calendar receipt must identify the supplementary runner and every engine module.")
    for name, digest in calendar["code_sha256"].items():
        require(name in calendar_code and hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, "Calendar receipt code hash mismatch; rerun the supplementary fixture.")
    summary = json.loads((root / "site/data/ingestion-summary.json").read_text(encoding="utf-8"))
    diagnostic = original_status["price_ingestion_diagnostic"]
    require(summary["research_ready"] is False and diagnostic["research_ready"] is False and diagnostic["full_dataset_audited"] is False, "Price diagnostics cannot certify the research dataset.")
    require(summary["calendar_coverage"] == "not_verified" and summary["price_adjustment_semantics"] == "not_verified", "Outstanding data audits must remain visible.")
    require(summary["requested_start"] == period["warmup_request_start"] and summary["requested_end"] == period["report_end_close"], "Public diagnostic must use the declared experiment window.")
    require(summary["source_script_sha256"] == hashlib.sha256((root / "scripts/ingest_diagnostic.py").read_bytes()).hexdigest(), "Saved diagnostic was not produced by the current ingestion script; rerun and replay after parser changes.")
    require(diagnostic["diagnostic_passed"] == summary["diagnostic_passed"] and diagnostic["cache_replay_verified"] == summary["cache_replay_verified"], "Research status and public diagnostic disagree.")
    require([entry["symbol"] for entry in summary["symbols"]] == config["benchmarks"]["tradeable"], "Public diagnostic must include the declared benchmarks.")
    for entry in summary["symbols"]:
        counts = [entry[key] for key in ("rows", "complete_ohlc_rows", "missing_ohlc_rows", "invalid_ohlc_rows", "error_count", "warning_count")]
        require(all(type(count) is int and count >= 0 for count in counts), f"{entry['symbol']}: invalid diagnostic counts.")
        require(sum(counts[1:4]) == counts[0], f"{entry['symbol']}: OHLC counts do not partition the observed rows.")
        require(bool(re.fullmatch(r"[0-9a-f]{64}", entry["raw_sha256"])), "Invalid raw capture hash.")
        require(period["warmup_request_start"] <= entry["observed_start"] <= entry["observed_end"] <= period["report_end_close"], "Observed diagnostic dates escape the requested interval.")
        if summary["diagnostic_passed"]:
            require(entry["rows"] > 0 and counts[2:5] == [0, 0, 0], "Passing diagnostic has missing/invalid observations or errors.")
    ids = [route["id"] for route in catalog["routes"]]
    require(len(ids) == len(set(ids)) and len(ids) > 0, "Source route IDs must be unique and nonempty.")
    require(not catalog["market_dataset_validated"] and not catalog["authenticated_market_download_completed"], "Provider documentation is not a validated market download.")
    for route in catalog["routes"]:
        require(bool(route.get("documentation_sources")), f"{route['id']}: missing source links.")
        for url in route["documentation_sources"]:
            parsed = urlsplit(url)
            require(parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None, f"{route['id']}: unsafe or invalid documentation URL.")

    def check_link(document, raw, ids=None):
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc:
            return
        if not parsed.path:
            if parsed.fragment and ids is not None:
                require(unquote(parsed.fragment) in ids, f"Unknown page section: {raw}")
            return
        require((document.parent / unquote(parsed.path)).exists(), f"Broken local link in {document.relative_to(root)}: {raw}")

    for document in sorted(root.rglob("*.md")):
        if any(part in document.relative_to(root).parts for part in (".git", ".venv", "tmp", "output")):
            continue
        for raw in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            check_link(document, raw.split(" ", 1)[0].strip("<>"))
    site = root / "site/index.html"
    require(site.exists(), "Static site entrypoint is missing.")
    if site.exists():
        parser = Links()
        parser.feed(site.read_text(encoding="utf-8"))
        for raw in parser.targets:
            check_link(site, raw, parser.ids)
    return errors


def main():
    try:
        errors = validate(ROOT)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: Cannot validate design: {error}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    print("PASS: limited protocol, primary/supplementary controls, source registry, status and local link checks.")
    print("NOT RUN by this command: engine tests, market-data audit or market backtest. Synthetic execution has a separate receipt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
