"""Fixed-baseline historical stock pilot; never the formal market engine.

The caller supplies a fixed, explicitly documented cohort, dated membership,
capitalization and common-calendar Yahoo price proxies. Signal prices and
adjusted accounting prices are intentionally separate. Accounting units are
vendor-adjusted units, not raw shares; no dividend cash flows are added.
"""

from datetime import date
import math
from numbers import Real
import statistics

from pilot.engine import PilotDataError, execute_rebalance
from spmo_lab.signals import SignalDataError, build_targets, score_momentum


DATA_TRACK = "baseline_issuer_stock_pilot"


class StockPilotError(ValueError):
    """Missing inputs or an accounting condition blocks this proxy run."""


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise StockPilotError(f"{label}: finite numeric value required")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise StockPilotError(f"{label}: finite numeric value required") from error
    if not math.isfinite(result) or (positive and result <= 0):
        raise StockPilotError(f"{label}: finite {'positive ' if positive else ''}value required")
    return result


def _day(value, label):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise StockPilotError(f"{label}: canonical ISO date required") from error
    if parsed.isoformat() != value:
        raise StockPilotError(f"{label}: canonical ISO date required")
    return parsed


def _ids(values, label, *, nonempty=True):
    if not isinstance(values, (list, tuple, set)):
        raise StockPilotError(f"{label}: identifier collection required")
    if ((nonempty and not values) or any(not isinstance(v, str) or not v or v != v.strip() for v in values)
            or len(values) != len(set(values))):
        raise StockPilotError(f"{label}: unique nonempty identifiers required")
    return list(values)


def _validated(data, config):
    sessions = data.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise StockPilotError("sessions: nonempty common calendar required")
    parsed = [_day(day, "session") for day in sessions]
    if any(a >= b for a, b in zip(parsed, parsed[1:])):
        raise StockPilotError("sessions: strictly increasing unique dates required")
    cohort = sorted(_ids(data.get("cohort"), "cohort"))
    metadata = data.get("security", data.get("securities", {}))
    if not isinstance(metadata, dict):
        raise StockPilotError("security: metadata mapping required")
    for security in cohort:
        item = metadata.get(security)
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in ("ticker", "issuer_id")):
            raise StockPilotError(f"{security}: ticker and issuer_id metadata required")
        if item.get("listed_from") is not None:
            _day(item["listed_from"], f"{security}/listed_from")
    memberships = data.get("membership_by_day", {})
    if not isinstance(memberships, dict):
        raise StockPilotError("membership_by_day: dated mapping required")
    members = {}
    for day in sessions:
        if day not in memberships:
            raise StockPilotError(f"{day}: missing historical membership state")
        members[day] = set(_ids(memberships[day], f"membership/{day}", nonempty=False)) & set(cohort)
    if not isinstance(data.get("bars"), dict) or not isinstance(data.get("market_caps"), dict):
        raise StockPilotError("bars and market_caps mappings required")
    if not isinstance(data.get("universe_exclusions", []), list):
        raise StockPilotError("universe_exclusions: list required")
    indexes = {}
    for name in ("initial_signal", "report_anchor", "report_end"):
        _day(config.get(name), name)
        if config[name] not in sessions:
            raise StockPilotError(f"{name}: exact common-calendar session required")
        indexes[name] = sessions.index(config[name])
    if not indexes["initial_signal"] < indexes["report_anchor"] < indexes["report_end"]:
        raise StockPilotError("initialization, reporting anchor and end must increase")
    slots, cap = config.get("slots", 75), _number(config.get("cap", .08), "cap", positive=True)
    if isinstance(slots, bool) or not isinstance(slots, int) or slots <= 0 or cap > 1:
        raise StockPilotError("slots must be positive integer and cap must be in (0, 1]")
    arms = config.get("arms", {})
    expected = {
        "S12": ("semiannual", [1.0, 0.0, 0.0]),
        "M12": ("monthly", [1.0, 0.0, 0.0]),
        "SMIX": ("semiannual", [.5, .3, .2]),
        "MMIX": ("monthly", [.5, .3, .2]),
    }
    if set(arms) != set(expected):
        raise StockPilotError("all four declared stock arms are required")
    for name, (frequency, weights) in expected.items():
        arm = arms[name]
        if not isinstance(arm, dict) or arm.get("frequency") != frequency or arm.get("signal_weights") != weights:
            raise StockPilotError(f"{name}: configured frequency and signal differ from the declared stock proxy")
    costs = config.get("costs", [0, 5, 10, 25])
    if not isinstance(costs, list) or any(isinstance(c, bool) for c in costs) or costs != [0, 5, 10, 25]:
        raise StockPilotError("costs must contain all four scenarios: 0, 5, 10, 25")
    months = config.get("semiannual_months", [3, 9])
    if months != [3, 9]:
        raise StockPilotError("semiannual_months must be March and September")
    lookbacks, skip = config.get("lookbacks", [252, 126, 63]), config.get("skip", 21)
    annualization = config.get("annualization", 252)
    try:
        for arm in arms.values():
            score_momentum([], arm["signal_weights"], lookbacks=lookbacks, skip=skip, annualization=annualization)
    except SignalDataError as error:
        raise StockPilotError(str(error)) from error
    if indexes["initial_signal"] < max(lookbacks):
        raise StockPilotError("initial signal lacks the required common-calendar warmup")
    cash = _number(config.get("initial_cash", 1_000_000), "initial_cash", positive=True)
    benchmarks = _ids(config.get("benchmarks", []), "benchmarks", nonempty=False)
    if set(benchmarks) & set(cohort):
        raise StockPilotError("benchmark identifiers must be separate from the stock cohort")
    return sessions, parsed, cohort, metadata, members, indexes, cash, benchmarks


def _price(data, security, day, field):
    row = data["bars"].get(security, {}).get(day)
    if not isinstance(row, dict) or field not in row:
        raise StockPilotError(f"{security}/{day}: missing {field}; no fabricated fill or valuation")
    return _number(row[field], f"{security}/{day}/{field}", positive=True)


def _cap(data, security, day):
    caps = data["market_caps"].get(security, {})
    if not isinstance(caps, dict) or day not in caps:
        raise StockPilotError(f"{security}/{day}: missing exact-date capitalization")
    return _number(caps[day], f"{security}/{day}/capitalization", positive=True)


def _metrics(daily, trades, start, end):
    rows = [r for r in daily if start <= r["session"] <= end]
    if not rows or rows[0]["session"] != start or rows[-1]["session"] != end:
        raise StockPilotError("metric interval requires exact observed endpoints")
    first, last = rows[0]["nav"], rows[-1]["nav"]
    high, worst = first, 0.0
    for row in rows:
        high = max(high, row["nav"])
        worst = min(worst, row["nav"] / high - 1)
    fills = [t for t in trades if start < t["session"] <= end]
    exposure_rows = rows[1:] or rows
    return {
        "start_session": start, "end_session": end,
        "start_nav": first, "end_nav": last, "total_return": last / first - 1,
        "max_drawdown": worst, "session_count": len(rows) - 1,
        "transaction_cost": math.fsum(t["cost"] for t in fills),
        "gross_traded_notional": math.fsum(t["traded_notional"] for t in fills),
        "two_sided_turnover": math.fsum(t["turnover"] for t in fills),
        "mean_cash_weight": statistics.fmean(r["cash_weight"] for r in exposure_rows),
        "maximum_cash_weight": max(r["cash_weight"] for r in exposure_rows),
        "maximum_security_weight": max(r["max_security_weight"] for r in exposure_rows),
        "maximum_issuer_weight": max(r["max_issuer_weight"] for r in exposure_rows),
        "mean_holdings_count": statistics.fmean(r["holdings_count"] for r in exposure_rows),
        "execution_event_count": len(fills),
    }


def _orders(receipt, opens):
    """Add explicit price, side and per-order fees to the reused fill receipt."""
    rate = receipt["cost"] / receipt["traded_notional"] if receipt["traded_notional"] else 0.0
    return [{"security_id": row["symbol"], "side": "buy" if row["units"] > 0 else "sell",
             "adjusted_units": row["units"], "quantity": abs(row["units"]),
             "adjusted_price": opens[row["symbol"]], "signed_notional": row["notional"],
             "notional": abs(row["notional"]), "cost": abs(row["notional"]) * rate}
            for row in receipt["orders"]]


def _run(data, config, validated, strategy, cost, decisions, *, benchmark=False):
    sessions, dates, cohort, metadata, members, indexes, initial_cash, _ = validated
    initial, anchor, end = (indexes[k] for k in ("initial_signal", "report_anchor", "report_end"))
    cash, positions = initial_cash, {}
    pending = None
    previous_members = members[sessions[initial]]
    daily, trades, signal_rows = [], [], []
    run_id = f"{strategy}-{cost}bps"
    for index in range(initial, end + 1):
        day = sessions[index]
        # Membership is a close observation. An inactive day never authorizes
        # a sale at that same day's opening price.
        forced = set() if benchmark else set(positions) - previous_members
        if pending is not None or forced:
            targets = pending["targets"] if pending is not None else None
            needed = set(positions) | set(targets or {})
            opens = {s: _price(data, s, day, "adjusted_open") for s in needed}
            pretrade = cash + math.fsum(positions[s] * opens[s] for s in positions)
            if pending is not None:
                safe_targets = {s: w for s, w in targets.items() if s not in forced}
                try:
                    cash, positions, receipt = execute_rebalance(cash, positions, opens, safe_targets, cost)
                except PilotDataError as error:
                    raise StockPilotError(f"{run_id}/{day}: {error}") from error
                receipt["orders"] = _orders(receipt, opens)
                receipt.update({"session": day, "decision_session": pending["decision_session"],
                                "reason": pending["reason"], "forced_exit_ids": sorted(forced)})
            else:
                # Sell only the removed positions. Other adjusted units and all
                # strategic cash remain intact until a scheduled rebalance.
                orders = []
                for security in sorted(forced):
                    units = positions.pop(security)
                    notional = units * opens[security]
                    fee = notional * cost / 10000
                    cash += notional - fee
                    orders.append({"security_id": security, "side": "sell", "adjusted_units": -units,
                                   "quantity": units, "adjusted_price": opens[security],
                                   "signed_notional": -notional, "notional": notional, "cost": fee})
                traded = math.fsum(o["notional"] for o in orders)
                fees = math.fsum(o["cost"] for o in orders)
                receipt = {"pretrade_nav": pretrade, "posttrade_nav": pretrade - fees,
                           "turnover": traded / pretrade, "traded_notional": traded, "cost": fees,
                           "orders": orders, "session": day, "decision_session": sessions[index - 1],
                           "reason": "forced_membership_exit", "forced_exit_ids": sorted(forced)}
            if receipt["orders"]:
                trades.append(receipt)
            pending = None
        close_values = {s: units * _price(data, s, day, "adjusted_close") for s, units in positions.items()}
        nav = cash + math.fsum(close_values.values())
        if not math.isfinite(nav) or nav <= 0 or cash < 0:
            raise StockPilotError(f"{run_id}/{day}: nonpositive NAV or negative cash")
        issuer_values = {}
        for security, value in close_values.items():
            issuer = metadata.get(security, {}).get("issuer_id", security)
            issuer_values[issuer] = issuer_values.get(issuer, 0.0) + value
        daily.append({"session": day, "nav": nav, "cash": cash, "cash_weight": cash / nav,
                      "holdings_count": len(positions), "positions": dict(positions),
                      "max_security_weight": max(close_values.values(), default=0.0) / nav,
                      "max_issuer_weight": max(issuer_values.values(), default=0.0) / nav,
                      "period": "burn_in" if index <= anchor else "measurement",
                      "daily_return": nav / daily[-1]["nav"] - 1 if daily else None})
        month_end = index < end and day[:7] != sessions[index + 1][:7]
        scheduled = index == initial or (not benchmark and month_end and (
            config["arms"][strategy]["frequency"] == "monthly" or dates[index].month in [3, 9]))
        if scheduled and index < end:
            if benchmark:
                target = {strategy: 1.0}
            else:
                target, rows = decisions[(strategy, day)]
                signal_rows.extend(dict(row) for row in rows)
            pending = {"targets": dict(target), "decision_session": day,
                       "reason": "initial_formation" if index == initial else "scheduled_rebalance"}
        previous_members = members[day]
    anchor_nav = daily[anchor - initial]["nav"]
    for row in daily:
        row["nav_index_2026"] = (100.0 if row["session"] == config["report_anchor"]
                                 else 100 * row["nav"] / anchor_nav if row["session"] > config["report_anchor"]
                                 else None)
    metrics = {
        "year2025": _metrics(daily, trades, config["initial_signal"], config["report_anchor"]),
        "ytd2026": _metrics(daily, trades, config["report_anchor"], config["report_end"]),
        "full_period": _metrics(daily, trades, config["initial_signal"], config["report_end"]),
    }
    return {"run_id": run_id, "strategy_id": strategy, "cost_bps_per_side": cost,
            "data_track": DATA_TRACK, "formal_protocol_compliant": False,
            "daily": daily, "trades": trades, "signals": signal_rows, "metrics": metrics}


def run_matrix(data, config):
    """Run the four arms and four costs on one fixed baseline cohort.

    Missing quotes/capitalization raise ``StockPilotError``. The routine cannot
    replace an unavailable security after examining future coverage. Its output is
    a retrospective vendor-price proxy, never a formal-protocol certification.
    """
    validated = _validated(data, config)
    sessions, dates, cohort, metadata, members, indexes, _, benchmarks = validated
    initial, end = indexes["initial_signal"], indexes["report_end"]
    decisions, shared = {}, {}
    lookbacks, skip = config.get("lookbacks", [252, 126, 63]), config.get("skip", 21)
    for strategy, arm in config["arms"].items():
        for index in range(initial, end):
            day = sessions[index]
            month_end = day[:7] != sessions[index + 1][:7]
            if index != initial and not (month_end and (arm["frequency"] == "monthly" or dates[index].month in [3, 9])):
                continue
            key = (day, tuple(arm["signal_weights"]))
            if key not in shared:
                scores, caps, records = {}, {}, []
                for security in sorted(members[day]):
                    cap = _cap(data, security, day)
                    enabled = [lookbacks[i] for i, w in enumerate(arm["signal_weights"]) if w > 0]
                    listed_from = metadata[security].get("listed_from")
                    listing_history_short = listed_from is not None and listed_from > sessions[index - max(enabled)]
                    if listing_history_short:
                        score, components, reason = None, [None] * len(lookbacks), "insufficient_listing_history"
                    else:
                        history = [_price(data, security, sessions[j], "signal_close") if j <= index - skip else None
                                   for j in range(index - max(enabled), index + 1)]
                        try:
                            result = score_momentum(history, arm["signal_weights"], lookbacks=lookbacks,
                                                    skip=skip, annualization=config.get("annualization", 252))
                        except SignalDataError as error:
                            raise StockPilotError(f"{security}/{day}: {error}") from error
                        score, components, reason = result.score, list(result.components), result.reason
                    scores[security], caps[security] = score, cap
                    records.append({"decision_session": day, "security_id": security,
                                    "ticker": metadata[security]["ticker"], "issuer_id": metadata[security]["issuer_id"],
                                    "score": score, "components": components, "reason": reason,
                                    "listed_from": listed_from,
                                    "market_cap_usd": cap, "market_cap_date": day,
                                    "membership_observation_date": day})
                try:
                    targets = build_targets(scores, caps, count=config.get("slots", 75), cap=config.get("cap", .08))
                except SignalDataError as error:
                    raise StockPilotError(f"{day}: {error}") from error
                ranked = sorted((s for s in scores if scores[s] is not None), key=lambda s: (-scores[s], s))
                ranks = {s: i + 1 for i, s in enumerate(ranked)}
                for record in records:
                    record["rank"] = ranks.get(record["security_id"])
                    record["target_weight"] = targets.get(record["security_id"], 0.0)
                shared[key] = targets, records
            decisions[(strategy, day)] = shared[key]
    runs = [_run(data, config, validated, strategy, cost, decisions)
            for strategy in config["arms"] for cost in config.get("costs", [0, 5, 10, 25])]
    benchmark_runs = [_run(data, config, validated, b, cost, {}, benchmark=True)
                      for b in benchmarks for cost in config.get("costs", [0, 5, 10, 25])]
    by_key = {(r["strategy_id"], r["cost_bps_per_side"]): r for r in runs}
    comparisons = []
    for cost in config.get("costs", [0, 5, 10, 25]):
        for period in ("year2025", "ytd2026", "full_period"):
            values = {s: by_key[(s, cost)]["metrics"][period] for s in config["arms"]}
            primary = 100 * (values["M12"]["total_return"] - values["S12"]["total_return"])
            replication = 100 * (values["MMIX"]["total_return"] - values["SMIX"]["total_return"])
            comparisons.append({"cost_bps_per_side": cost, "period": period,
                                "primary_frequency_difference_pp": primary,
                                "replication_frequency_difference_pp": replication,
                                "interaction_difference_pp": replication - primary})
    all_runs = runs + benchmark_runs
    index_by_day = {day: i for i, day in enumerate(sessions)}
    checks = {
        "all_16_strategy_cost_paths": len(runs) == 16 and len({r["run_id"] for r in runs}) == 16,
        "fixed_cohort_for_all_paths": True,
        "no_negative_cash": all(row["cash"] >= 0 for r in all_runs for row in r["daily"]),
        "positive_finite_nav": all(math.isfinite(row["nav"]) and row["nav"] > 0 for r in all_runs for row in r["daily"]),
        "next_session_execution": all(index_by_day[t["session"]] == index_by_day[t["decision_session"]] + 1
                                      for r in all_runs for t in r["trades"]),
        "self_financing_fees": all(math.isclose(t["pretrade_nav"] - t["cost"], t["posttrade_nav"],
                                               rel_tol=1e-12, abs_tol=1e-8) for r in all_runs for t in r["trades"]),
        "fees_match_executed_notional": all(math.isclose(t["cost"], t["traded_notional"] * r["cost_bps_per_side"] / 10000,
                                                       rel_tol=1e-12, abs_tol=1e-8) for r in all_runs for t in r["trades"]),
        "anchor_is_existing_portfolio": all(r["metrics"]["year2025"]["end_nav"] == r["metrics"]["ytd2026"]["start_nav"]
                                            and r["daily"][indexes["report_anchor"] - initial]["nav_index_2026"] == 100
                                            for r in all_runs),
    }
    if not all(checks.values()):
        raise StockPilotError("run checks failed: " + ", ".join(k for k, v in checks.items() if not v))
    aggregate = lambda r: {k: r[k] for k in ("run_id", "strategy_id", "cost_bps_per_side", "metrics")}
    summary = {
        "schema_version": 1, "data_track": DATA_TRACK, "formal_protocol_compliant": False,
        "cohort_size": len(cohort), "universe_exclusion_count": len(data.get("universe_exclusions", [])),
        "initial_signal": config["initial_signal"], "report_anchor": config["report_anchor"], "report_end": config["report_end"],
        "strategy_run_count": len(runs), "benchmark_run_count": len(benchmark_runs), "checks": checks,
        "runs": [aggregate(r) for r in runs], "benchmarks": [aggregate(r) for r in benchmark_runs],
        "comparisons": comparisons,
        "limitations": ["Baseline issuer cohort and restricted position count differ from the full historical S&P 500 protocol",
                        "No unavailable baseline security is replaced using future price coverage",
                        "Membership observations are assumed known at the recorded session close",
                        "Capitalization values are dated vendor observations, not proven historical publication vintages",
                        "One primary security class represents each baseline issuer; weights use issuer capitalization rather than verified class capitalization",
                        "Vendor-adjusted units approximate reinvested total returns; no raw-share corporate-action ledger",
                        "Missing held or required signal prices stop execution; delisting settlements are not inferred"],
    }
    return {"data_track": DATA_TRACK, "formal_protocol_compliant": False, "runs": runs,
            "benchmarks": benchmark_runs, "comparisons": comparisons, "checks": checks, "summary": summary}
