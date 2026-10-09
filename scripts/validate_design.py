#!/usr/bin/env python3
"""Validate a research specification; deliberately does not backtest markets."""

import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    config = json.loads((root / "configs/experiment.v1.json").read_text())
    status = json.loads((root / "results/status.json").read_text())
    period, common, arms = config["period"], config["common"], config["arms"]
    require(date.fromisoformat(period["warmup_request_start"]) < date.fromisoformat(period["anchor_close"]) < date.fromisoformat(period["end_close"]), "Date ordering must be warmup < anchor < end.")
    require(period["warmup_min_price_points"] >= max(config["signal_definition"]["lookback_sessions"]) + 1, "Warmup must contain 253 prices for a 252-session interval.")
    require(period["classification"] == "retrospective_exploratory", "2026 must remain explicitly exploratory.")
    require(common["execution_time"] == "next_exchange_session_open", "Close signals must execute at the next open.")
    require(common["cost_bps_per_side_base"] in common["cost_bps_per_side_scenarios"], "Cost scenarios must include the base case.")
    require(all(c >= 0 for c in common["cost_bps_per_side_scenarios"]), "Costs cannot be negative.")
    require(0 < common["security_weight_cap"] <= 1, "Weight cap must be in (0,1].")
    require(not common["weekly_risk_overlay"], "Weekly risk rules are explicitly deferred.")
    require(not config["universe"]["current_constituents_backfill_allowed"], "Current constituents cannot be backfilled.")
    for name, arm in arms.items():
        weights = arm["signal_weights"]
        require(len(weights) == len(config["signal_definition"]["lookback_sessions"]), f"{name}: signal weights and windows differ in length.")
        require(all(w >= 0 for w in weights) and math.isclose(sum(weights), 1), f"{name}: signal weights must be nonnegative and sum to one.")
        require(arm["target_count"] > 0, f"{name}: target count must be positive.")
    for fast, slow in [("F_FAST", "F_SLOW"), ("B1", "B0")]:
        differing = {key for key in arms[fast].keys() | arms[slow].keys() if arms[fast].get(key) != arms[slow].get(key)}
        require(differing == {"rebalance"}, f"{fast}/{slow}: frequency controls must differ only in rebalance.")
    known = set(arms) | set(config["benchmarks"]["tradeable"])
    comparisons = config["comparisons"]
    for pair in [comparisons["primary_frequency"], comparisons["primary_real_world"], comparisons["secondary_market"], *comparisons["ablation_chain"]]:
        require(len(pair) == 2 and all(x in known for x in pair), f"Unknown comparison: {pair}.")
    require(config["aliases"].get("B5") == "F_FAST", "B5 must alias F_FAST rather than create another trial.")
    require(not config["results"]["executed"] and config["results"]["market_returns"] is None, "The design has no market results.")
    require(status["stage"] == "design_only" and not status["engine_implemented"] and not status["data_audit_completed"] and not status["market_backtest_executed"] and status["returns"] is None, "Result status must accurately say design-only.")
    for document in sorted(root.rglob("*.md")):
        if ".git" in document.parts:
            continue
        for raw in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            destination = raw.split(" ", 1)[0].strip("<>")
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = document.parent / unquote(parsed.path)
            require(target.exists(), f"Broken local link in {document.relative_to(root)}: {destination}")
    return errors


def main() -> int:
    try:
        errors = validate(ROOT)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: Cannot validate specification: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: design constraints, frequency controls, status and local Markdown links.")
    print("NOT RUN: market data audit, backtest engine tests, or market backtest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
