"""Three-policy extension; the frozen legacy engine remains unchanged.

A/C use legacy numerical payloads. B freezes A's semiannual targets and
restores them monthly using its own NAV. This module has no network I/O.
"""
import copy
from datetime import date
import math

from pilot.engine import PilotDataError, _period_metrics, execute_rebalance, run_matrix


POLICIES = {
    "A": {"selection": "semiannual", "reset": "semiannual"},
    "B": {"selection": "semiannual", "reset": "monthly"},
    "C": {"selection": "monthly", "reset": "monthly"},
}
CONTRASTS = (("C-A", "C", "A"), ("B-A", "B", "A"), ("C-B", "C", "B"))


def validate_protocol(protocol, config):
    if protocol.get("schema_version") != 1 or protocol.get("policies") != POLICIES:
        raise PilotDataError("mechanism protocol must declare exactly A, B and C")
    if protocol.get("contrasts") != [row[0] for row in CONTRASTS]:
        raise PilotDataError("three ordered planned contrasts are required")
    if protocol.get("primary_phase") != config["primary_reference_phase"]:
        raise PilotDataError("primary phase differs from the preserved design")
    if protocol.get("primary_cost_bps_per_side") != config["base_cost_bps_per_side"]:
        raise PilotDataError("primary cost differs from the preserved design")
    tolerance = protocol.get("nonzero_trade_relative_tolerance")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not 0 <= tolerance <= 1e-8:
        raise PilotDataError("nonzero trade tolerance is invalid")


def classify_orders(trade, old_names, target_names):
    """Partition executed notional and fees, never return P&L."""
    old_names, target_names = set(old_names), set(target_names)
    notionals = {key: 0.0 for key in ("entry", "exit", "resize")}
    for order in trade["orders"]:
        symbol = order["symbol"]
        category = "entry" if symbol not in old_names else ("exit" if symbol not in target_names else "resize")
        order["trade_category"] = category
        notionals[category] += abs(order["notional"])
    ratio = trade["cost"] / trade["traded_notional"] if trade["traded_notional"] else 0.0
    trade["notional_by_category"] = notionals
    trade["fee_by_category"] = {key: value * ratio for key, value in notionals.items()}
    if not math.isclose(math.fsum(notionals.values()), trade["traded_notional"], rel_tol=1e-12, abs_tol=1e-8):
        raise PilotDataError("trade classification does not reconcile")


def add_activity_metrics(run, tolerance):
    metrics = [run["metrics"]["full_period"], run["metrics"]["ytd2026"], *run["metrics"]["annual"].values()]
    for metric in metrics:
        trades = [t for t in run["trades"] if metric["start_session"] < t["session"] <= metric["end_session"]]
        metric["scheduled_reset_count"] = len(trades)
        metric["nonzero_trade_event_count"] = sum(t["traded_notional"] > tolerance * t["pretrade_nav"] for t in trades)
        metric["order_count"] = sum(len(t["orders"]) for t in trades)
        metric["traded_notional_by_category"] = {
            key: math.fsum(t["notional_by_category"][key] for t in trades)
            for key in ("entry", "exit", "resize")
        }
        metric["fee_by_category"] = {
            key: math.fsum(t["fee_by_category"][key] for t in trades)
            for key in ("entry", "exit", "resize")
        }


def decorate_legacy_run(source, tolerance):
    run = copy.deepcopy(source)
    run["policy"] = "C" if source["schedule"] == "monthly" else "A"
    run["legacy_run_id"] = source["run_id"]
    decisions = {row["decision_session"]: row for row in run["signals"]}
    previous_names = []
    for trade in run["trades"]:
        target = decisions[trade["decision_session"]]["selected"]
        classify_orders(trade, previous_names, target)
        previous_names = list(target)
    add_activity_metrics(run, tolerance)
    return run


def run_frozen_target(data, config, reference, tolerance=1e-12):
    """Run B from a semiannual target history produced by the legacy engine."""
    sessions = data["sessions"]
    indices = {session: i for i, session in enumerate(sessions)}
    parsed = [date.fromisoformat(s) for s in sessions]
    origin = reference["signals"][0]["decision_session"]
    initial = indices[origin]
    end = indices[reference["daily"][-1]["session"]]
    refreshes = {row["decision_session"]: row for row in reference["signals"]}
    if reference["schedule"] != "semiannual" or len(refreshes) != len(reference["signals"]):
        raise PilotDataError("B requires a unique semiannual target history")
    month_ends = {i for i in range(initial, end) if sessions[i][:7] != sessions[i + 1][:7]}
    phase = reference["phase"]
    cash, positions = float(config["initial_cash"]), {}
    target, target_origin, pending = None, None, None
    daily, trades, resets, target_history = [], [], [], []
    peak = cash
    for i in range(initial, end + 1):
        if pending is not None:
            opening = {s: data["adjusted_open"][s][i] for s in set(positions) | set(pending["weights"])}
            old_names = list(positions)
            cash, positions, receipt = execute_rebalance(cash, positions, opening, pending["weights"], reference["cost_bps_per_side"])
            receipt.update({
                "decision_session": pending["decision_session"], "session": sessions[i],
                "target_origin_session": pending["target_origin_session"],
                "target_refreshed": pending["target_refreshed"],
            })
            classify_orders(receipt, old_names, pending["weights"])
            trades.append(receipt)
            pending = None
        nav = cash + math.fsum(units * data["adjusted_close"][s][i] for s, units in positions.items())
        if nav <= 0 or not math.isfinite(nav) or cash < 0:
            raise PilotDataError("B has invalid account state")
        peak = max(peak, nav)
        daily.append({"session": sessions[i], "nav": nav, "cash": cash, "cash_weight": cash / nav,
                      "positions": dict(positions), "drawdown_from_formation": nav / peak - 1})
        scheduled = i == initial or i in month_ends
        if scheduled and i < end:
            refreshed = sessions[i] in refreshes
            if refreshed:
                record = refreshes[sessions[i]]
                target = {s: 1.0 / config["slots"] for s in record["selected"]}
                target_origin = sessions[i]
                target_history.append(copy.deepcopy(record))
            elif parsed[i].month in phase:
                raise PilotDataError("declared semiannual refresh absent")
            if target is None:
                raise PilotDataError("B has no initial target")
            reset = {
                "decision_session": sessions[i], "target_origin_session": target_origin,
                "target_refreshed": refreshed, "selected": list(target),
                "target_weights": dict(target), "cash_target_weight": max(0.0, 1 - math.fsum(target.values())),
            }
            resets.append(reset)
            pending = {**reset, "weights": dict(target)}
    full = reference["metrics"]["full_period"]
    ytd = reference["metrics"]["ytd2026"]
    metrics = {
        "full_period": _period_metrics(daily, trades, full["start_session"], full["end_session"], annualization_years=full["annualization_years"]),
        "ytd2026": _period_metrics(daily, trades, ytd["start_session"], ytd["end_session"]),
        "annual": {
            year: _period_metrics(daily, trades, metric["start_session"], metric["end_session"], annualization_years=1)
            for year, metric in reference["metrics"]["annual"].items()
        },
    }
    name = "B12" if reference["signal"] == "12-1" else "BMIX"
    run = {
        "run_id": f"{name}-{phase[0]:02d}-{phase[1]:02d}-{reference['cost_bps_per_side']:g}bps",
        "policy": "B", "arm": name, "signal": reference["signal"],
        "schedule": "semiannual_selection_monthly_reset", "phase": list(phase),
        "cost_bps_per_side": reference["cost_bps_per_side"],
        "reference_run_id": reference["run_id"], "daily": daily, "trades": trades,
        "signals": resets, "target_refreshes": target_history, "metrics": metrics,
    }
    add_activity_metrics(run, tolerance)
    return run


def compare_pair(high, low, contrast, period, phase, year=None):
    a, b = high["metrics"][period], low["metrics"][period]
    if year is not None:
        a, b = a[str(year)], b[str(year)]
    result = {
        "contrast": contrast, "signal": high["signal"], "phase": list(phase),
        "cost_bps_per_side": high["cost_bps_per_side"], "high_run_id": high["run_id"], "low_run_id": low["run_id"],
        "start_session": a["start_session"], "end_session": a["end_session"],
        "high_total_return": a["total_return"], "low_total_return": b["total_return"],
        "net_return_difference_pp": 100 * (a["total_return"] - b["total_return"]),
        "high_cagr": a["cagr"], "low_cagr": b["cagr"],
        "cagr_difference_pp": 100 * (a["cagr"] - b["cagr"]) if a["cagr"] is not None else None,
        "log_growth_difference": math.log((1 + a["total_return"]) / (1 + b["total_return"])),
        "max_drawdown_difference_pp": 100 * (a["max_drawdown"] - b["max_drawdown"]),
        "extra_two_sided_turnover": a["two_sided_turnover"] - b["two_sided_turnover"],
    }
    if a["start_session"] != b["start_session"] or a["end_session"] != b["end_session"]:
        raise PilotDataError("comparison boundaries differ")
    if year is not None:
        result["year"] = int(year)
    return result


def run_policy_matrix(data, legacy_config, protocol):
    validate_protocol(protocol, legacy_config)
    legacy = run_matrix(data, legacy_config)
    tolerance = protocol["nonzero_trade_relative_tolerance"]
    runs = [decorate_legacy_run(r, tolerance) for r in legacy["runs"]]
    by_id = {r["run_id"]: r for r in runs}
    comparisons = {"full_period": [], "ytd2026": [], "annual": []}
    for reference in legacy["runs"]:
        if reference["schedule"] != "semiannual":
            continue
        b = run_frozen_target(data, legacy_config, reference, tolerance)
        runs.append(b)
        a = by_id[reference["run_id"]]
        c_name = "M12" if reference["signal"] == "12-1" else "MMIX"
        c = by_id[f"{c_name}-{reference['cost_bps_per_side']:g}bps"]
        group = {"A": a, "B": b, "C": c}
        for contrast, high, low in CONTRASTS:
            for period in ("full_period", "ytd2026"):
                comparisons[period].append(compare_pair(group[high], group[low], contrast, period, reference["phase"]))
            for year in reference["metrics"]["annual"]:
                comparisons["annual"].append(compare_pair(group[high], group[low], contrast, "annual", reference["phase"], year))
    primary_runs = {
        "A": next(r for r in runs if r["policy"] == "A" and r["signal"] == protocol["primary_signal"] and r["phase"] == protocol["primary_phase"] and r["cost_bps_per_side"] == protocol["primary_cost_bps_per_side"]),
        "B": next(r for r in runs if r["policy"] == "B" and r["signal"] == protocol["primary_signal"] and r["phase"] == protocol["primary_phase"] and r["cost_bps_per_side"] == protocol["primary_cost_bps_per_side"]),
        "C": next(r for r in runs if r["policy"] == "C" and r["signal"] == protocol["primary_signal"] and r["cost_bps_per_side"] == protocol["primary_cost_bps_per_side"]),
    }
    idx = {s: i for i, s in enumerate(data["sessions"])}
    b_runs = [r for r in runs if r["policy"] == "B"]
    checks = {
        "strategy_count": len(runs) == 104,
        "benchmark_count": len(legacy["benchmarks"]) == 4,
        "comparison_matrix_complete": len(comparisons["full_period"]) == 144,
        "monthly_controls_not_duplicated": sum(r["policy"] == "C" for r in runs) == 8,
        "B_next_session_execution": all(idx[t["session"]] == idx[t["decision_session"]] + 1 for r in b_runs for t in r["trades"]),
        "B_one_execution_per_reset": all(len(r["trades"]) == len(r["signals"]) for r in b_runs),
        "B_self_financing": all(math.isclose(t["pretrade_nav"] - t["cost"], t["posttrade_nav"], rel_tol=1e-12, abs_tol=1e-8) for r in b_runs for t in r["trades"]),
        "B_no_boundary_reset": all(r["metrics"]["full_period"]["end_nav"] == r["metrics"]["ytd2026"]["start_nav"] for r in b_runs),
        "B_frozen_target_origins": all(reset["target_origin_session"] <= reset["decision_session"] for r in b_runs for reset in r["signals"]),
    }
    if not all(checks.values()):
        raise PilotDataError(f"mechanism matrix checks failed: {checks}")
    return {"runs": runs, "benchmarks": legacy["benchmarks"], "comparisons": comparisons,
            "primary_run_ids": {key: r["run_id"] for key, r in primary_runs.items()},
            "checks": checks, "boundaries": legacy["boundaries"], "legacy_result": legacy}
