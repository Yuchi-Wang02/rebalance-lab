"""Tranche accounting and paired uncertainty for a retrospective validation case."""
import math
import statistics
from collections import defaultdict

import numpy as np

from pilot.engine import _period_metrics
from pilot.mechanism_analysis import stationary_indices


def aggregate_sleeves(sleeves, data, config, run_id):
    if len(sleeves) != 6:
        raise ValueError("exactly six semiannual sleeves are required")
    dates = [r["session"] for r in sleeves[0]["daily"]]
    if any([r["session"] for r in s["daily"]] != dates for s in sleeves):
        raise ValueError("sleeve dates must align exactly")
    cost = sleeves[0]["cost_bps_per_side"]
    if any(s["cost_bps_per_side"] != cost for s in sleeves):
        raise ValueError("sleeve costs must match")
    if len({s["daily"][0]["nav"] for s in sleeves}) != 1:
        raise ValueError("sleeves must have equal formation capital")
    prices = data["adjusted_open"]
    index = {date: i for i, date in enumerate(data["sessions"])}
    trade_maps = [{t["session"]: t for t in s["trades"]} for s in sleeves]
    daily, trades = [], []
    peak = 0.0
    for i, date in enumerate(dates):
        rows = [s["daily"][i] for s in sleeves]
        nav = math.fsum(r["nav"] for r in rows) / 6
        cash = math.fsum(r["cash"] for r in rows) / 6
        units = defaultdict(float)
        for row in rows:
            for symbol, quantity in row["positions"].items():
                units[symbol] += quantity / 6
        peak = max(peak, nav)
        daily.append({"session": date, "nav": nav, "cash": cash, "cash_weight": cash / nav,
                      "positions": dict(units), "drawdown_from_formation": nav / peak - 1})
        events = [m[date] for m in trade_maps if date in m]
        if events:
            if i == 0:
                raise ValueError("formation anchor cannot contain an execution")
            j = index[date]
            pre = math.fsum(s["daily"][i-1]["cash"] + math.fsum(q * prices[symbol][j]
                for symbol, q in s["daily"][i-1]["positions"].items()) for s in sleeves) / 6
            gross = math.fsum(t["traded_notional"] for t in events) / 6
            fee = math.fsum(t["cost"] for t in events) / 6
            if not math.isclose(fee, cost / 10000 * gross, rel_tol=1e-11, abs_tol=1e-8):
                raise ValueError("tranche fee does not reconcile")
            trades.append({"session": date, "pretrade_nav": pre, "posttrade_nav": pre-fee,
                           "traded_notional": gross, "cost": fee, "turnover": gross/pre,
                           "sleeve_executions": len(events), "cross_sleeve_netting": False})
    anchor, end, secondary = (config[k] for k in ("report_anchor", "primary_end", "secondary_end"))
    year_rows = []
    for year in range(2001, 2026):
        start = max(d for d in dates if d[:4] < str(year))
        finish = max(d for d in dates if d[:4] <= str(year))
        year_rows.append({"year": year, **_period_metrics(daily, trades, start, finish, annualization_years=1)})
    metrics = {"full_period": _period_metrics(daily, trades, anchor, end, annualization_years=25),
               "annual": year_rows, "ytd2026": _period_metrics(daily, trades, end, secondary)}
    return {"run_id": run_id, "policy": "T", "signal": sleeves[0]["signal"], "phase": None,
            "cost_bps_per_side": cost, "sleeve_ids": [s["run_id"] for s in sleeves],
            "initial_sleeve_weight": 1/6, "sleeve_transfers": False, "cross_sleeve_netting": False,
            "daily": daily, "trades": trades, "metrics": metrics}


def monthly_path(run, anchor, end):
    days = [d for d in run["daily"] if anchor <= d["session"] <= end]
    if not days or days[0]["session"] != anchor or days[-1]["session"] != end:
        raise ValueError("monthly path lacks exact reporting boundaries")
    ends = {}
    for row in days[1:]:
        ends[row["session"][:7]] = row
    expected = [f"{y}-{m:02d}" for y in range(2001, 2026) for m in range(1, 13)]
    if list(ends) != expected:
        raise ValueError("exactly 300 ordered reporting months required")
    previous = days[0]["nav"]
    rows = []
    for month, day in ends.items():
        rows.append({"month": month, "session": day["session"], "simple_return": day["nav"]/previous-1,
                     "normalized_nav": day["nav"]/days[0]["nav"]})
        previous = day["nav"]
    if not math.isclose(math.prod(1+r["simple_return"] for r in rows), previous/days[0]["nav"], rel_tol=1e-12):
        raise ValueError("monthly compounding fails")
    return rows


def risk_metrics(returns, benchmark, rf):
    values, market, risk_free = [np.asarray(x, dtype=float) for x in (returns, benchmark, rf)]
    if values.ndim != 1 or values.shape != market.shape or values.shape != risk_free.shape or len(values) < 3:
        raise ValueError("risk inputs require aligned monthly vectors")
    if not all(np.isfinite(x).all() for x in (values, market, risk_free)) or (values <= -1).any():
        raise ValueError("invalid monthly return")
    excess, market_excess = values-risk_free, market-risk_free
    sd = float(np.std(excess, ddof=1))
    variance = float(np.var(market_excess, ddof=1))
    beta = float(np.cov(excess, market_excess, ddof=1)[0,1]/variance) if variance > 1e-20 else None
    return {"months": len(values), "sharpe_monthly_annualized": float(math.sqrt(12)*np.mean(excess)/sd) if sd > 1e-14 else None,
            "tracking_error_monthly_annualized": float(math.sqrt(12)*np.std(values-market, ddof=1)),
            "beta_to_SPY_excess_returns": beta,
            "beta_intercept_per_month": float(np.mean(excess)-beta*np.mean(market_excess)) if beta is not None else None,
            "monthly_return_volatility_annualized": float(math.sqrt(12)*np.std(values, ddof=1))}


def paired_cagr_intervals(values, labels, comparisons, spec):
    returns = np.asarray(values, dtype=float)
    if returns.ndim != 2 or returns.shape[1] != len(labels) or len(returns) != 300:
        raise ValueError("bootstrap requires 300 jointly aligned months")
    if not np.isfinite(returns).all() or (returns <= -1).any() or len(set(labels)) != len(labels):
        raise ValueError("invalid paired returns or labels")
    logs = np.log1p(returns)
    observed = np.expm1(logs.mean(axis=0)*12)
    result = []
    for length in [spec["mean_block_months"], *spec["sensitivity_block_months"]]:
        indices = stationary_indices(300, spec["repetitions"], length, spec["seed"])
        # Chunk columns to bound memory while sharing every resampled month index.
        samples = np.column_stack([np.expm1(logs[indices,j].mean(axis=1)*12) for j in range(len(labels))])
        for name, high, low in comparisons:
            hi, lo = labels.index(high), labels.index(low)
            bounds = np.quantile(100*(samples[:,hi]-samples[:,lo]), [.025,.975])
            result.append({"comparison": name, "high_run_id": high, "low_run_id": low,
                           "cagr_difference_pp": float(100*(observed[hi]-observed[lo])),
                           "ci95_difference_pp": bounds.tolist(), "mean_block_months": length,
                           "repetitions": spec["repetitions"], "seed": spec["seed"], "months": 300,
                           "primary_block": length == spec["mean_block_months"]})
    return result
