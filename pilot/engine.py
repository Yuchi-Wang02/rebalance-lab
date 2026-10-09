"""Deterministic, self-financing adjusted-price ETF pilot.

Inputs are already audited, common-session adjusted OHLC observations.  The
engine deliberately neither fetches data nor interprets dividend records.  Its
units represent a vendor-adjusted total-return proxy, not raw ETF shares.
"""

from collections import Counter
from datetime import date
import math
from numbers import Real
import statistics

from spmo_lab.signals import score_momentum


class PilotDataError(ValueError):
    """An input cannot support the declared pilot without a silent assumption."""


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PilotDataError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise PilotDataError(f"{label} must be finite" + (" and positive" if positive else ""))
    return result


def _validated_inputs(data, config):
    sessions = list(data.get("sessions", []))
    if not sessions:
        raise PilotDataError("sessions must not be empty")
    try:
        parsed = [date.fromisoformat(value) for value in sessions]
    except (TypeError, ValueError) as error:
        raise PilotDataError("sessions must contain ISO dates") from error
    if any(value.isoformat() != text for value, text in zip(parsed, sessions)):
        raise PilotDataError("sessions must use canonical ISO dates")
    if any(a >= b for a, b in zip(parsed, parsed[1:])):
        raise PilotDataError("sessions must be strictly ascending without duplicates")
    universe = config.get("universe", [])
    if not universe or len(set(universe)) != len(universe) or any(not isinstance(s, str) or not s for s in universe):
        raise PilotDataError("universe must contain unique symbols")
    benchmark = config.get("benchmark")
    if not isinstance(benchmark, str) or not benchmark or benchmark in universe:
        raise PilotDataError("benchmark must be a separate symbol")
    prices = {}
    for field in ("adjusted_open", "adjusted_close"):
        source = data.get(field, {})
        prices[field] = {}
        for symbol in [*universe, benchmark]:
            values = source.get(symbol, [])
            if len(values) != len(sessions):
                raise PilotDataError(f"{field}/{symbol}: one price per common session is required")
            prices[field][symbol] = [_number(v, f"{field}/{symbol}/{sessions[i]}", positive=True) for i, v in enumerate(values)]
    boundaries = {}
    for key in ("initial_signal_on_or_before", "report_anchor_on_or_before", "full_year_end_on_or_before", "case_end_on_or_before"):
        try:
            cutoff = date.fromisoformat(config[key])
        except (KeyError, TypeError, ValueError) as error:
            raise PilotDataError(f"{key} must be an ISO date") from error
        eligible = [i for i, value in enumerate(parsed) if value <= cutoff]
        if not eligible:
            raise PilotDataError(f"no session on or before {key}")
        boundaries[key] = eligible[-1]
    initial, anchor, full, end = [boundaries[key] for key in boundaries]
    if not initial < anchor < full <= end or initial + 1 >= len(sessions):
        raise PilotDataError("initialization, anchor and reporting endpoints are not ordered")
    if parsed[initial].year != date.fromisoformat(config["initial_signal_on_or_before"]).year:
        raise PilotDataError("initialization year has no price observations")
    for key in ("report_anchor_on_or_before", "full_year_end_on_or_before", "case_end_on_or_before"):
        if parsed[boundaries[key]].year != date.fromisoformat(config[key]).year:
            raise PilotDataError(f"{key}: requested year has no observations")
    slots = config.get("slots", 3)
    if isinstance(slots, bool) or not isinstance(slots, int) or not 1 <= slots <= len(universe):
        raise PilotDataError("slots must be an integer within the universe size")
    costs = config.get("cost_bps_per_side_scenarios", [])
    if not costs or len(set(costs)) != len(costs):
        raise PilotDataError("cost scenarios must be nonempty and unique")
    costs = [_number(value, "cost scenario") for value in costs]
    if any(value < 0 or value >= 10000 for value in costs):
        raise PilotDataError("cost scenarios must be between zero and 10000 bps")
    if config.get("base_cost_bps_per_side", 5) not in costs:
        raise PilotDataError("the base cost must be a cost scenario")
    if config.get("phase_pairs") != [[month, month + 6] for month in range(1, 7)]:
        raise PilotDataError("all six prespecified semiannual phase pairs are required")
    if config.get("primary_reference_phase", [3, 9]) != [3, 9]:
        raise PilotDataError("March/September must remain the primary phase")
    arms = config.get("arms", {})
    if set(arms) != {"M12", "MMIX"}:
        raise PilotDataError("the two declared signals M12 and MMIX are required")
    signal = config.get("signal", {})
    lookbacks = signal.get("lookbacks", [252, 126, 63])
    skip = signal.get("skip", 21)
    annualization = signal.get("annualization", 252)
    # Delegate exact window/weight semantics to the shared tested primitive.
    for weights in arms.values():
        score_momentum([], weights, lookbacks=lookbacks, skip=skip, annualization=annualization)
    if initial < max(lookbacks):
        raise PilotDataError("initial signal does not have all declared lookback observations")
    cash = _number(config.get("initial_cash", 1_000_000), "initial_cash", positive=True)
    return sessions, parsed, prices, universe, benchmark, boundaries, slots, costs, signal, cash


def execute_rebalance(cash, positions, opening_prices, target_weights, cost_bps):
    """Execute target weights of post-fee NAV; return new state and its receipt.

    The scalar equation is continuous and strictly increasing for cost rates
    below 100%, so bisection has a unique solution even when a trade changes
    from a buy to a sell inside the search interval.
    """
    cash = _number(cash, "cash")
    if cash < 0:
        raise PilotDataError("negative cash is not allowed")
    rate = _number(cost_bps, "cost_bps") / 10000.0
    if not 0 <= rate < 1:
        raise PilotDataError("cost_bps must be between zero and 10000")
    symbols = sorted(set(positions) | set(target_weights))
    weights = {symbol: _number(target_weights.get(symbol, 0), f"weight/{symbol}") for symbol in symbols}
    if any(value < 0 for value in weights.values()) or math.fsum(weights.values()) > 1 + 1e-12:
        raise PilotDataError("weights must be nonnegative and sum to at most one")
    old = {}
    for symbol in symbols:
        price = _number(opening_prices[symbol], f"open/{symbol}", positive=True)
        units = _number(positions.get(symbol, 0), f"units/{symbol}")
        if units < 0:
            raise PilotDataError("short positions are not allowed")
        old[symbol] = units * price
    pretrade = cash + math.fsum(old.values())
    if not math.isfinite(pretrade) or pretrade <= 0:
        raise PilotDataError("pretrade NAV must be finite and positive")

    def residual(nav):
        notional = math.fsum(abs(weights[symbol] * nav - old[symbol]) for symbol in symbols)
        return nav + rate * notional - pretrade

    low, high = 0.0, pretrade
    if rate == 0:
        posttrade = pretrade
    else:
        for _ in range(64):
            middle = (low + high) / 2
            if residual(middle) > 0:
                high = middle
            else:
                low = middle
        posttrade = (low + high) / 2
    orders = []
    new_positions = {}
    for symbol in symbols:
        value = weights[symbol] * posttrade
        new_units = value / opening_prices[symbol]
        notional = value - old[symbol]
        if new_units > 0:
            new_positions[symbol] = new_units
        if notional != 0:
            orders.append({"symbol": symbol, "units": new_units - positions.get(symbol, 0), "notional": notional})
    traded = math.fsum(abs(order["notional"]) for order in orders)
    fee = rate * traded
    new_cash = posttrade - math.fsum(weights[symbol] * posttrade for symbol in symbols)
    if new_cash < 0 and new_cash >= -1e-10 * pretrade:
        new_cash = 0.0
    if new_cash < 0 or not math.isclose(pretrade - fee, posttrade, rel_tol=1e-12, abs_tol=1e-8):
        raise PilotDataError("self-financing rebalance did not reconcile")
    return new_cash, new_positions, {
        "pretrade_nav": pretrade,
        "posttrade_nav": posttrade,
        "turnover": traded / pretrade,
        "traded_notional": traded,
        "cost": fee,
        "orders": orders,
    }


def _period_metrics(daily, trades, start, end, *, annualization_years=None):
    rows = [row for row in daily if start <= row["session"] <= end]
    if not rows or rows[0]["session"] != start or rows[-1]["session"] != end:
        raise PilotDataError("reporting interval lacks an exact session boundary")
    initial_nav, final_nav = rows[0]["nav"], rows[-1]["nav"]
    peak = initial_nav
    worst = 0.0
    for row in rows:
        peak = max(peak, row["nav"])
        worst = min(worst, row["nav"] / peak - 1)
    returns = [b["nav"] / a["nav"] - 1 for a, b in zip(rows, rows[1:])]
    events = [trade for trade in trades if start < trade["session"] <= end]
    after_anchor = rows[1:] or rows
    turnover = math.fsum(trade["turnover"] for trade in events)
    return {
        "start_session": start,
        "end_session": end,
        "start_nav": initial_nav,
        "end_nav": final_nav,
        "total_return": final_nav / initial_nav - 1,
        "cagr": (final_nav / initial_nav) ** (1 / annualization_years) - 1 if annualization_years else None,
        "annualization_years": annualization_years,
        "max_drawdown": worst,
        "annualized_volatility": (statistics.stdev(returns) * math.sqrt(252) if len(returns) >= 2 else 0.0) if annualization_years else None,
        "two_sided_turnover": turnover,
        "annualized_two_sided_turnover": turnover / annualization_years if annualization_years else None,
        "transaction_cost": math.fsum(trade["cost"] for trade in events),
        "transaction_cost_over_anchor_nav": math.fsum(trade["cost"] for trade in events) / initial_nav,
        "mean_cash_weight": statistics.fmean(row["cash_weight"] for row in after_anchor),
        "max_cash_weight": max(row["cash_weight"] for row in after_anchor),
        "rebalance_count": len(events),
        "session_count": len(rows) - 1,
    }


def _contrast(monthly, semiannual, period, year=None):
    if year is None:
        a, b = monthly["metrics"][period], semiannual["metrics"][period]
    else:
        a, b = monthly["metrics"]["annual"][year], semiannual["metrics"]["annual"][year]
    result = {
        "signal": monthly["signal"],
        "phase": semiannual["phase"],
        "cost_bps_per_side": monthly["cost_bps_per_side"],
        "monthly_run_id": monthly["run_id"],
        "semiannual_run_id": semiannual["run_id"],
        "monthly_total_return": a["total_return"],
        "semiannual_total_return": b["total_return"],
        "net_return_difference_pp": 100 * (a["total_return"] - b["total_return"]),
        "monthly_cagr": a["cagr"],
        "semiannual_cagr": b["cagr"],
        "cagr_difference_pp": 100 * (a["cagr"] - b["cagr"]) if a["cagr"] is not None and b["cagr"] is not None else None,
        "monthly_max_drawdown": a["max_drawdown"],
        "semiannual_max_drawdown": b["max_drawdown"],
        "max_drawdown_difference_pp": 100 * (a["max_drawdown"] - b["max_drawdown"]),
        "monthly_turnover": a["two_sided_turnover"],
        "semiannual_turnover": b["two_sided_turnover"],
        "extra_two_sided_turnover": a["two_sided_turnover"] - b["two_sided_turnover"],
        "monthly_mean_cash_weight": a["mean_cash_weight"],
        "semiannual_mean_cash_weight": b["mean_cash_weight"],
    }
    if year is not None:
        result["year"] = int(year)
    return result


def run_matrix(data, config):
    """Run the two signals, all schedules/costs and the common SPY benchmark.

    Each path starts from the same formation decision and continues through
    burn-in, full-year history and the later case study without resetting cash,
    units, exposure or costs at a reporting boundary.
    """
    sessions, dates, prices, universe, benchmark, boundaries, slots, costs, signal_spec, initial_cash = _validated_inputs(data, config)
    initial, anchor, full, end = [boundaries[key] for key in boundaries]
    opens, closes = prices["adjusted_open"], prices["adjusted_close"]
    month_ends = {i for i in range(initial, end) if (dates[i].year, dates[i].month) != (dates[i + 1].year, dates[i + 1].month)}
    signal_cache = {}
    max_lookback = max(signal_spec.get("lookbacks", [252, 126, 63]))

    def decision(index, arm):
        key = (index, arm)
        if key not in signal_cache:
            scores = {}
            for symbol in universe:
                observation = score_momentum(
                    closes[symbol][max(0, index - max_lookback):index + 1],
                    config["arms"][arm],
                    lookbacks=signal_spec.get("lookbacks", [252, 126, 63]),
                    skip=signal_spec.get("skip", 21),
                    annualization=signal_spec.get("annualization", 252),
                )
                scores[symbol] = observation.score
            ranked = sorted((symbol for symbol in universe if scores[symbol] is not None), key=lambda symbol: (-scores[symbol], symbol))
            selected = ranked[:slots]
            signal_cache[key] = {"decision_session": sessions[index], "selected": selected, "scores": scores}
        return signal_cache[key]

    annual_boundaries = {}
    for year in range(dates[anchor].year + 1, dates[full].year + 1):
        starts = [i for i in range(anchor, full + 1) if dates[i].year < year]
        ends = [i for i in range(anchor, full + 1) if dates[i].year == year]
        if not starts or not ends:
            raise PilotDataError(f"missing annual reporting boundary for {year}")
        annual_boundaries[str(year)] = (sessions[starts[-1]], sessions[ends[-1]])

    def run(arm, phase, cost, *, is_benchmark=False):
        schedule = "buy_and_hold" if is_benchmark else ("monthly" if phase is None else "semiannual")
        label = benchmark if is_benchmark else (arm if phase is None else {"M12": "S12", "MMIX": "SMIX"}[arm])
        cost_label = f"{cost:g}"
        run_id = f"{label}-{cost_label}bps" if phase is None else f"{label}-{phase[0]:02d}-{phase[1]:02d}-{cost_label}bps"
        cash, positions = initial_cash, {}
        daily, trades, decisions = [], [], []
        pending = None
        formation_peak = initial_cash
        for index in range(initial, end + 1):
            if pending is not None:
                opening = {symbol: opens[symbol][index] for symbol in set(positions) | set(pending["weights"])}
                cash, positions, receipt = execute_rebalance(cash, positions, opening, pending["weights"], cost)
                receipt.update({"decision_session": pending["decision_session"], "session": sessions[index]})
                trades.append(receipt)
                pending = None
            nav = cash + math.fsum(units * closes[symbol][index] for symbol, units in positions.items())
            if not math.isfinite(nav) or nav <= 0 or cash < 0:
                raise PilotDataError(f"invalid NAV or cash on {sessions[index]}")
            formation_peak = max(formation_peak, nav)
            daily.append({
                "session": sessions[index], "nav": nav, "cash": cash,
                "cash_weight": cash / nav, "positions": dict(positions),
                "drawdown_from_formation": nav / formation_peak - 1,
            })
            scheduled = index == initial or (not is_benchmark and index in month_ends and (phase is None or dates[index].month in phase))
            if scheduled and index < end:
                if is_benchmark:
                    recorded = {"decision_session": sessions[index], "selected": [benchmark], "scores": {}}
                    weights = {benchmark: 1.0}
                else:
                    cached = decision(index, arm)
                    recorded = {"decision_session": cached["decision_session"], "selected": list(cached["selected"]), "scores": dict(cached["scores"])}
                    weights = {symbol: 1.0 / slots for symbol in recorded["selected"]}
                decisions.append(recorded)
                pending = {"decision_session": sessions[index], "weights": weights}
        metrics = {
            "full_period": _period_metrics(daily, trades, sessions[anchor], sessions[full], annualization_years=len(annual_boundaries)),
            "ytd2026": _period_metrics(daily, trades, sessions[full], sessions[end]),
            "annual": {year: _period_metrics(daily, trades, start, stop, annualization_years=1) for year, (start, stop) in annual_boundaries.items()},
        }
        return {
            "run_id": run_id, "arm": label,
            "signal": "benchmark" if is_benchmark else ("12-1" if arm == "M12" else "mixed"),
            "schedule": schedule, "phase": list(phase) if phase else None,
            "cost_bps_per_side": cost,
            "daily": daily, "trades": trades, "signals": decisions, "metrics": metrics,
        }

    runs, benchmarks, comparisons = [], [], {"full_period": [], "ytd2026": [], "annual": []}
    for arm in ("M12", "MMIX"):
        for cost in costs:
            monthly = run(arm, None, cost)
            runs.append(monthly)
            for phase in config["phase_pairs"]:
                semiannual = run(arm, phase, cost)
                runs.append(semiannual)
                for period in ("full_period", "ytd2026"):
                    comparisons[period].append(_contrast(monthly, semiannual, period))
                for year in annual_boundaries:
                    comparisons["annual"].append(_contrast(monthly, semiannual, "annual", year))
    for cost in costs:
        benchmarks.append(run(None, None, cost, is_benchmark=True))
    primary = {
        period: next(row for row in comparisons[period] if row["signal"] == "12-1" and row["phase"] == [3, 9] and row["cost_bps_per_side"] == config.get("base_cost_bps_per_side", 5))
        for period in ("full_period", "ytd2026")
    }
    all_runs = runs + benchmarks
    index_by_date = {session: index for index, session in enumerate(sessions)}
    controls = Counter(row["monthly_run_id"] for row in comparisons["full_period"])
    checks = {
        "strategy_run_count": len(runs) == 14 * len(costs),
        "monthly_control_count": sum(run["schedule"] == "monthly" for run in runs) == 2 * len(costs),
        "semiannual_run_count": sum(run["schedule"] == "semiannual" for run in runs) == 12 * len(costs),
        "all_six_phases_reported": len(comparisons["full_period"]) == 12 * len(costs),
        "monthly_controls_reused_six_times": len(controls) == 2 * len(costs) and all(count == 6 for count in controls.values()),
        "benchmark_per_cost": len(benchmarks) == len(costs),
        "fills_at_next_session": all(index_by_date[t["session"]] == index_by_date[t["decision_session"]] + 1 for run in all_runs for t in run["trades"]),
        "self_financing_fees": all(math.isclose(t["pretrade_nav"] - t["cost"], t["posttrade_nav"], rel_tol=1e-12, abs_tol=1e-8) for run in all_runs for t in run["trades"]),
        "nonnegative_cash_and_positive_nav": all(row["cash"] >= 0 and row["nav"] > 0 for run in all_runs for row in run["daily"]),
        "no_boundary_reset": all(run["metrics"]["full_period"]["end_nav"] == run["metrics"]["ytd2026"]["start_nav"] for run in all_runs),
        "all_complete_years_reported": all(set(run["metrics"]["annual"]) == set(annual_boundaries) for run in all_runs),
    }
    if not all(checks.values()):
        raise PilotDataError(f"run-level checks failed: {[key for key, passed in checks.items() if not passed]}")
    return {
        "runs": runs, "benchmarks": benchmarks, "comparisons": comparisons,
        "primary": primary, "checks": checks,
        "boundaries": {key: sessions[index] for key, index in boundaries.items()},
        "unique_signal_evaluations": len(signal_cache),
    }
