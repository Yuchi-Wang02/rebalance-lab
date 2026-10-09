"""Point-in-time orchestration for synthetic fixtures only.

The supplied calendar is authoritative for a fixture. This module does not infer
exchange sessions or provide an adapter for unaudited vendor observations.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Mapping
from zoneinfo import ZoneInfo

from .ledger import Dividend, Ledger
from .signals import build_targets, score_momentum

NY = ZoneInfo("America/New_York")
POLICY_KEYS = ("protocol_version", "timezone", "currency", "universe", "signal_definition",
               "common", "arms", "benchmarks", "comparisons", "metrics", "deferred")
SUPPORTED_POLICY_SHA256 = "c181a0a92be68a1a74bbbc1212fbc38ff6e6cb47d613ff714030154e5ed97c70"
PRIMARY_CONFIG_SHA256 = "0754c1f425d65382457f3a006ca74235f416f5d205f42c1847c8f98f6a0c86b9"
PRIMARY_CONFIG_CANONICAL_SHA256 = "5055917956fceb22a0a6d4d9e5fe8c856a9e17d25bec18b74b5b7c6d48df942f"
CALENDAR_PHASES = ((1, 7), (2, 8), (3, 9), (4, 10), (5, 11), (6, 12))
CALENDAR_SENSITIVITY_SPEC = {
    "schema_version": 1,
    "experiment_track": "calendar_phase_sensitivity",
    "status": "synthetic_validation_only",
    "primary_config": "configs/experiment.v1.json",
    "primary_config_sha256": PRIMARY_CONFIG_SHA256,
    "primary_reference_phase": [3, 9],
    "phase_pairs": [list(pair) for pair in CALENDAR_PHASES],
    "comparisons": [
        {"signal": "12-1", "monthly_control": "M12", "semiannual": "S12"},
        {"signal": "mixed", "monthly_control": "MMIX", "semiannual": "SMIX"},
    ],
    "cost_bps_per_side_scenarios": [0, 5, 10, 25],
    "monthly_control_count": 8,
    "semiannual_run_count": 48,
    "unique_run_count": 56,
    "paired_contrast_count": 48,
    "only_changed_policy": "semiannual_signal_months",
    "inference_scope": "within_study_robustness_not_independent_replication",
    "report_all_phases": True,
    "promote_best_phase": False,
    "market_backtest_executed": False,
    "research_ready": False,
}


class SimulationError(ValueError):
    """Unsupported inputs or violated research invariants."""


def validate_protocol(config):
    """Reject policy changes until their semantics have an implementation/test review."""
    try:
        policy = json.dumps({k: config[k] for k in POLICY_KEYS}, sort_keys=True, separators=(",", ":"))
    except (KeyError, TypeError, ValueError) as error:
        raise SimulationError("Incomplete or malformed experiment policy.") from error
    if hashlib.sha256(policy.encode()).hexdigest() != SUPPORTED_POLICY_SHA256:
        raise SimulationError("Only the frozen v0.2 policy is implemented; policy changes require implementation review.")


def validate_calendar_sensitivity(config, sensitivity, primary_config_sha256):
    """Bind this supplementary track to the complete, unchanged primary file."""
    validate_protocol(config)
    try:
        primary = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        supplied = json.dumps(sensitivity, sort_keys=True, separators=(",", ":"), allow_nan=False)
        expected = json.dumps(CALENDAR_SENSITIVITY_SPEC, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise SimulationError("Malformed calendar sensitivity configuration.") from error
    if (primary_config_sha256 != PRIMARY_CONFIG_SHA256
            or hashlib.sha256(primary.encode()).hexdigest() != PRIMARY_CONFIG_CANONICAL_SHA256):
        raise SimulationError("Calendar sensitivity requires the unchanged primary configuration and file hash.")
    if supplied != expected:
        raise SimulationError("Only the fixed six-phase calendar sensitivity specification is implemented.")


@dataclass(frozen=True)
class Session:
    day: str
    open_at: datetime
    close_at: datetime


@dataclass(frozen=True)
class Bar:
    open: float | None
    close: float | None
    signal_close: float | None
    signal_known_at: datetime


@dataclass(frozen=True)
class MembershipEvent:
    security_id: str
    active: bool
    effective_at: datetime
    known_at: datetime


@dataclass(frozen=True)
class Capitalization:
    security_id: str
    day: str
    value: float
    known_at: datetime


@dataclass
class Dataset:
    sessions: list[Session]
    bars: dict[str, dict[str, Bar]]
    membership: list[MembershipEvent]
    capitalizations: list[Capitalization]
    dividends: list[Dividend]
    splits: dict[str, dict[str, float]]
    issuers: dict[str, str]
    data_track: str = "synthetic"
    unsupported_events: tuple[str, ...] = ()


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def validate_dataset(data: Dataset):
    if data.data_track != "synthetic":
        raise SimulationError("Only synthetic fixtures are accepted; a market-data adapter requires a separate audit.")
    if data.unsupported_events:
        raise SimulationError("Unsupported corporate actions or settlements block execution.")
    days = [s.day for s in data.sessions]
    if not days or days != sorted(set(days)):
        raise SimulationError("Fixture calendar must contain unique increasing sessions.")
    for session in data.sessions:
        if (not _aware(session.open_at) or not _aware(session.close_at)
                or not session.open_at < session.close_at
                or session.open_at.astimezone(NY).date().isoformat() != session.day
                or session.close_at.astimezone(NY).date().isoformat() != session.day):
            raise SimulationError("Invalid fixture session timestamps.")
    if not data.bars or set(data.bars) != set(data.issuers):
        raise SimulationError("Every fixture security requires a unique identifier and issuer mapping.")
    for security, bars in data.bars.items():
        if not set(bars).issubset(days):
            raise SimulationError(f"{security}: observations outside the supplied calendar.")
        for bar in bars.values():
            if not _aware(bar.signal_known_at):
                raise SimulationError("Signal availability must be timezone-aware.")
            for value in (bar.open, bar.close, bar.signal_close):
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                          or not math.isfinite(value) or value <= 0):
                    raise SimulationError("Invalid fixture price; missing quotes must be explicit None.")
    cap_keys = set()
    for cap in data.capitalizations:
        key = (cap.security_id, cap.day, cap.known_at)
        if (cap.security_id not in data.bars or cap.day not in days or not _aware(cap.known_at)
                or key in cap_keys or isinstance(cap.value, bool)
                or not isinstance(cap.value, (int, float)) or not math.isfinite(cap.value) or cap.value <= 0):
            raise SimulationError("Invalid or duplicate capitalization observation.")
        cap_keys.add(key)
    event_keys = set()
    for event in data.membership:
        key = (event.security_id, event.effective_at, event.known_at)
        if (event.security_id not in data.bars or type(event.active) is not bool
                or not _aware(event.effective_at) or not _aware(event.known_at) or key in event_keys):
            raise SimulationError("Invalid or conflicting membership event.")
        event_keys.add(key)
    for dividend in data.dividends:
        if (dividend.security_id not in data.bars or dividend.ex_date not in days
                or dividend.pay_date not in days or dividend.pay_date < dividend.ex_date):
            raise SimulationError("Fixture dividend dates must be supplied sessions with pay >= ex.")
    for day, changes in data.splits.items():
        if day not in days or any(s not in data.bars for s in changes):
            raise SimulationError("Invalid split session/security.")


def members_at(events, instant):
    """Evaluate both effective time and information availability, never download time."""
    state = {}
    for event in sorted(events, key=lambda x: (x.effective_at, x.known_at, x.security_id)):
        if event.effective_at <= instant and event.known_at <= instant:
            state[event.security_id] = event.active
    return {security for security, active in state.items() if active}


def selection_due(sessions, index, frequency, semiannual_months=(3, 9)):
    day = sessions[index].day
    # A truncated final month is not evidence that its last supplied date is month-end.
    if index + 1 == len(sessions):
        return False
    month_end = day[:7] != sessions[index + 1].day[:7]
    if frequency == "monthly":
        return month_end
    if frequency == "semiannual":
        return month_end and int(day[5:7]) in semiannual_months
    raise SimulationError("Unknown selection frequency.")


def _signal_targets(data, config, arm, index, cap_index):
    session = data.sessions[index]
    universe = members_at(data.membership, session.close_at)
    scores, caps, decisions = {}, {}, []
    definition = config["signal_definition"]
    for security in sorted(universe):
        prices = []
        for prior in data.sessions[:index + 1]:
            bar = data.bars[security].get(prior.day)
            prices.append(bar.signal_close if bar and bar.signal_known_at <= session.close_at else None)
        result = score_momentum(prices, arm["signal_weights"],
                                lookbacks=definition["lookback_sessions"],
                                skip=definition["skip_sessions"],
                                annualization=definition["annualization_sessions"])
        scores[security] = result.score
        if result.score is not None:
            available = [c for c in cap_index.get((security, session.day), []) if c.known_at <= session.close_at]
            if not available:
                raise SimulationError(f"{security}: no same-session capitalization known at decision close.")
            caps[security] = max(available, key=lambda c: c.known_at).value
        decisions.append({"decision_session": session.day, "security_id": security,
                          "score": result.score, "components": list(result.components),
                          "reason": result.reason, "market_cap": caps.get(security)})
    targets = build_targets(scores, caps, count=config["common"]["target_count"],
                            cap=config["common"]["security_weight_cap"])
    for record in decisions:
        record["target_weight"] = targets.get(record["security_id"], 0.0)
    return targets, decisions


def metrics_for(daily, trades, anchor, end):
    report = [row for row in daily if anchor <= row["session"] <= end]
    if not report or report[0]["session"] != anchor or report[-1]["session"] != end:
        raise SimulationError("Reporting anchor and end require actual fixture closes.")
    anchor_nav = report[0]["nav"]
    if anchor_nav <= 0:
        raise SimulationError("Reporting anchor NAV must be positive.")
    high, drawdown = anchor_nav, 0.0
    for row in report:
        high = max(high, row["nav"])
        drawdown = min(drawdown, row["nav"] / high - 1)
    fills = [trade for trade in trades if anchor < trade["session"] <= end]
    return {"net_total_return": report[-1]["nav"] / anchor_nav - 1,
            "maximum_drawdown": drawdown,
            "reporting_cost": sum(t["cost"] for t in fills),
            "gross_traded_notional": sum(t["notional"] for t in fills),
            "two_sided_turnover": sum(t["notional"] / t["pretrade_nav"] for t in fills),
            "anchor_nav": anchor_nav, "end_nav": report[-1]["nav"],
            "reporting_close_count": len(report)}


def run_arm(data: Dataset, config: Mapping, strategy_id: str, cost_bps: float, initial_cash=1_000_000.0,
            *, experiment_track="primary", calendar_phase=None):
    validate_protocol(config)
    validate_dataset(data)
    if strategy_id not in config["arms"] or cost_bps not in config["common"]["cost_bps_per_side_scenarios"]:
        raise SimulationError("Strategy or cost scenario is outside the configured experiment.")
    if config["results"]["executed"] or config["results"]["market_returns"] is not None:
        raise SimulationError("Synthetic execution cannot accept a market-results declaration.")
    period = config["period"]
    days = [s.day for s in data.sessions]
    for key in ("initial_signal_close", "report_anchor_close", "report_end_close"):
        if period[key] not in days:
            raise SimulationError(f"Missing required fixture session: {key}.")
    initial_index = days.index(period["initial_signal_close"])
    if initial_index < max(config["signal_definition"]["lookback_sessions"]):
        raise SimulationError("Fixture does not include the configured signal warmup.")
    arm = config["arms"][strategy_id]
    if experiment_track not in ("primary", "calendar_phase_sensitivity"):
        raise SimulationError("Unknown experiment track.")
    if experiment_track == "primary":
        if calendar_phase is not None:
            raise SimulationError("A calendar phase override requires the explicit supplementary experiment track.")
        semiannual_months = config["common"]["semiannual_signal_months"]
    elif arm["rebalance"] == "semiannual":
        if (not isinstance(calendar_phase, (list, tuple))
                or any(type(month) is not int for month in calendar_phase)
                or tuple(calendar_phase) not in CALENDAR_PHASES):
            raise SimulationError("A supplementary semiannual run requires one of the six fixed calendar phases.")
        semiannual_months = calendar_phase
    else:
        if calendar_phase is not None:
            raise SimulationError("Monthly controls cannot have a calendar phase override.")
        semiannual_months = config["common"]["semiannual_signal_months"]
    ledger = Ledger(initial_cash, cost_bps=cost_bps)
    cap_index = {}
    for cap in data.capitalizations:
        cap_index.setdefault((cap.security_id, cap.day), []).append(cap)
    ex_dates = {}
    for dividend in data.dividends:
        ex_dates.setdefault(dividend.ex_date, []).append(dividend)
    pending_targets, pending_decision = None, None
    daily, decisions, snapshots = [], [], {}
    previous_members = members_at(data.membership, data.sessions[initial_index].close_at)
    for index in range(initial_index, len(data.sessions)):
        session = data.sessions[index]
        if session.day > period["report_end_close"]:
            break
        # Information first released at this exact open cannot produce an order
        # in the same opening auction. It becomes executable next session.
        current_members = members_at(data.membership, session.open_at - timedelta(microseconds=1))
        if index > initial_index:
            # Removals learned during the previous session remain due at this open.
            held_removals = set(ledger.positions) - current_members
            forced = (previous_members - current_members) | held_removals
            opens = {sid: bars[session.day].open if session.day in bars else None
                     for sid, bars in data.bars.items()}
            prior_fill_count = len(ledger.trades)
            ledger.open_session(session.day, opens, targets=pending_targets,
                                forced_exits=forced, splits=data.splits.get(session.day),
                                dividends=ex_dates.get(session.day, ()), eligible_ids=current_members)
            for fill in ledger.trades[prior_fill_count:]:
                if fill["reason"] == "scheduled_rebalance":
                    fill["decision_session"] = pending_decision
        else:
            # Seed the common cash account at the initial signal close, without buying.
            ledger.open_session(session.day, {}, eligible_ids=current_members)
        pending_targets, pending_decision = None, None
        closes = {sid: bars[session.day].close if session.day in bars else None
                  for sid, bars in data.bars.items()}
        close_members = members_at(data.membership, session.close_at)
        snapshot = ledger.close_session(session.day, closes, eligible_ids=close_members)
        daily.append({**snapshot, "data_track": "synthetic",
                      "period": "burn_in" if session.day <= period["report_anchor_close"] else "measurement"})
        if session.day in (period["report_anchor_close"], period["report_end_close"]):
            snapshots[session.day] = {"positions": dict(ledger.positions), "cash": ledger.cash,
                                      "receivables": snapshot["receivables"], "nav": snapshot["nav"]}
        if index == initial_index or selection_due(data.sessions, index, arm["rebalance"],
                                                  semiannual_months):
            if session.day < period["report_end_close"]:
                pending_targets, records = _signal_targets(data, config, arm, index, cap_index)
                pending_decision = session.day
                decisions.extend(records)
        previous_members = current_members
    metrics = metrics_for(daily, ledger.trades, period["report_anchor_close"], period["report_end_close"])
    return {"data_track": "synthetic", "experiment_track": experiment_track,
            "calendar_phase": list(semiannual_months) if arm["rebalance"] == "semiannual" else None,
            "strategy_id": strategy_id, "cost_bps": cost_bps,
            "daily": daily, "trades": ledger.trades, "signals": decisions,
            "corporate_actions": ledger.events, "exceptions": ledger.exceptions,
            "snapshots": snapshots, "metrics": metrics}


def run_matrix(data, config):
    return [run_arm(data, config, strategy, cost)
            for strategy in config["arms"]
            for cost in config["common"]["cost_bps_per_side_scenarios"]]


def run_calendar_matrix(data, config, sensitivity, *, primary_config_sha256):
    """Run every fixed phase, reusing each monthly control across six contrasts.

    These synthetic comparisons check implementation and within-study calendar
    sensitivity. They are not independent evidence or a schedule-selection rule.
    """
    validate_calendar_sensitivity(config, sensitivity, primary_config_sha256)
    monthly_controls, phase_runs, phase_table = [], [], []
    for comparison in sensitivity["comparisons"]:
        monthly_strategy, slow_strategy = comparison["monthly_control"], comparison["semiannual"]
        for cost in sensitivity["cost_bps_per_side_scenarios"]:
            monthly = run_arm(data, config, monthly_strategy, cost,
                              experiment_track="calendar_phase_sensitivity")
            monthly["strategy_run_id"] = f"{monthly_strategy}-{cost}bps-monthly-control"
            monthly["run_role"] = "monthly_control"
            monthly_controls.append(monthly)
            for pair in sensitivity["phase_pairs"]:
                slow = run_arm(data, config, slow_strategy, cost,
                               experiment_track="calendar_phase_sensitivity", calendar_phase=pair)
                slow["strategy_run_id"] = f"{slow_strategy}-{cost}bps-phase-{pair[0]:02d}-{pair[1]:02d}"
                slow["run_role"] = "semiannual_phase"
                phase_runs.append(slow)
                fast_metrics, slow_metrics = monthly["metrics"], slow["metrics"]
                phase_table.append({
                    "data_track": "synthetic", "experiment_track": "calendar_phase_sensitivity",
                    "signal": comparison["signal"], "calendar_phase": list(pair),
                    "is_primary_reference_phase": pair == sensitivity["primary_reference_phase"],
                    "cost_bps": cost, "monthly_control_id": monthly["strategy_run_id"],
                    "semiannual_run_id": slow["strategy_run_id"],
                    "monthly_strategy": monthly_strategy, "semiannual_strategy": slow_strategy,
                    "monthly_net_total_return": fast_metrics["net_total_return"],
                    "semiannual_net_total_return": slow_metrics["net_total_return"],
                    "net_return_difference_percentage_points": 100 * (
                        fast_metrics["net_total_return"] - slow_metrics["net_total_return"]),
                    "monthly_maximum_drawdown": fast_metrics["maximum_drawdown"],
                    "semiannual_maximum_drawdown": slow_metrics["maximum_drawdown"],
                    "drawdown_difference_percentage_points": 100 * (
                        fast_metrics["maximum_drawdown"] - slow_metrics["maximum_drawdown"]),
                    "monthly_two_sided_turnover": fast_metrics["two_sided_turnover"],
                    "semiannual_two_sided_turnover": slow_metrics["two_sided_turnover"],
                    "extra_two_sided_turnover": fast_metrics["two_sided_turnover"] - slow_metrics["two_sided_turnover"],
                    "monthly_reporting_cost": fast_metrics["reporting_cost"],
                    "semiannual_reporting_cost": slow_metrics["reporting_cost"],
                    "extra_reporting_cost": fast_metrics["reporting_cost"] - slow_metrics["reporting_cost"],
                })
    return {"monthly_controls": monthly_controls, "phase_runs": phase_runs, "phase_table": phase_table}
