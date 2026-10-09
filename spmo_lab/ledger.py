"""Fractional-share USD accounting for the experimental protocol.

Prices passed here are executable, unadjusted marks. Calendar construction,
point-in-time membership and signal generation belong to the caller. Mergers
and delistings have no implicit payout treatment in this primitive and require
explicit handling before it can be used for market research. A missing opening
quote can be used only for valuation via
a flagged previous-close mark; it can never produce a fill.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import math
from numbers import Real
from typing import Any


class LedgerError(ValueError):
    """An invalid accounting input or impossible ledger transition."""


@dataclass(frozen=True)
class Dividend:
    event_id: str
    security_id: str
    ex_date: str
    pay_date: str
    amount_per_share: float


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or any(ord(c) < 32 for c in value):
        raise LedgerError(f"{field} must be a nonempty, trimmed identifier")
    return value


def _session(value: Any, field: str = "session") -> str:
    if not isinstance(value, str):
        raise LedgerError(f"{field} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise LedgerError(f"{field} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise LedgerError(f"{field} must use YYYY-MM-DD")
    return value


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise LedgerError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        raise LedgerError(f"{field} must be finite and {'positive' if positive else 'nonnegative'}")
    return result


def _marks(values: Mapping[str, float | None], field: str) -> dict[str, float | None]:
    if not isinstance(values, Mapping):
        raise LedgerError(f"{field} must be a mapping")
    return {
        _identifier(key, "security_id"): None if value is None else _number(value, f"{field}[{key}]", positive=True)
        for key, value in values.items()
    }


def _ids(values: Iterable[str], field: str) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise LedgerError(f"{field} must be an iterable of identifiers, not a string")
    try:
        return {_identifier(value, field) for value in values}
    except TypeError as exc:
        raise LedgerError(f"{field} must be an iterable of identifiers") from exc


def _finite_sum(values, field: str) -> float:
    try:
        result = math.fsum(values)
    except OverflowError as exc:
        raise LedgerError(f"{field} is nonfinite") from exc
    if not math.isfinite(result):
        raise LedgerError(f"{field} is nonfinite")
    return result


class Ledger:
    """Long-only accounting with explicit ex-date and pay-date dividends.

    Call ``open_session`` then ``close_session`` exactly once per supplied
    exchange session, in increasing order. Methods that raise ``LedgerError``
    leave the ledger unchanged so a corrected input may be supplied.
    """

    def __init__(self, initial_cash: float, cost_bps: float = 5):
        self.cash = _number(initial_cash, "initial_cash")
        self.cost_bps = _number(cost_bps, "cost_bps")
        if self.cost_bps >= 10_000:
            raise LedgerError("cost_bps must be less than 10000")
        self.positions: dict[str, float] = {}
        self.trades: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.exceptions: list[dict[str, Any]] = []
        self.cumulative_cost = 0.0
        self.receivables: dict[str, dict[str, Any]] = {}
        self.pending_exits: set[str] = set()
        self.snapshots: list[dict[str, Any]] = []
        self._removed_ids: set[str] = set()
        self._dividend_ids: set[str] = set()
        self._eligible_ids: set[str] | None = None
        self._last_closes: dict[str, float] = {}
        self._last_close_values: dict[str, float] = {}
        self._last_session: str | None = None
        self._active_session: str | None = None
        self._reinvest_budget = 0.0

    @property
    def receivables_value(self) -> float:
        return _finite_sum((item["amount"] for item in self.receivables.values()), "receivables")

    def open_session(
        self,
        session: str,
        opens: Mapping[str, float | None],
        *,
        targets: Mapping[str, float] | None = None,
        forced_exits: Iterable[str] = (),
        splits: Mapping[str, float] | None = None,
        dividends: Sequence[Dividend] = (),
        eligible_ids: Iterable[str] | None = None,
    ) -> None:
        # _open only appends to these histories. Copying their accumulated
        # contents on every session makes an otherwise linear run quadratic.
        history_names = ("trades", "events", "exceptions", "snapshots")
        histories = {name: (getattr(self, name), len(getattr(self, name)))
                     for name in history_names}
        saved = deepcopy({name: value for name, value in self.__dict__.items()
                          if name not in histories})
        try:
            self._open(session, opens, targets, forced_exits, splits, dividends, eligible_ids)
        except LedgerError:
            self.__dict__.clear()
            self.__dict__.update(saved)
            for name, (history, length) in histories.items():
                del history[length:]
                setattr(self, name, history)
            raise

    def _open(self, session, opens, targets, forced_exits, splits, dividends, eligible_ids):
        session = _session(session)
        if self._active_session is not None:
            raise LedgerError("close the active session before opening another")
        if self._last_session is not None and session <= self._last_session:
            raise LedgerError("sessions must increase strictly")
        marks = _marks(opens, "opens")
        forced = _ids(forced_exits, "forced_exits")
        split_map = _marks({} if splits is None else splits, "splits")
        if any(value is None for value in split_map.values()):
            raise LedgerError("split ratios cannot be missing")
        weights = None
        if targets is not None:
            if not isinstance(targets, Mapping):
                raise LedgerError("targets must be a mapping")
            weights = {_identifier(key, "security_id"): _number(value, f"target[{key}]") for key, value in targets.items()}
            if any(weight > 1 for weight in weights.values()) or math.fsum(weights.values()) > 1 + 1e-12:
                raise LedgerError("target weights cannot exceed one; leverage is unsupported")
        if eligible_ids is not None:
            self._eligible_ids = _ids(eligible_ids, "eligible_ids")
            # A subsequent explicit membership observation may permit re-entry.
            self._removed_ids.difference_update(self._eligible_ids - self.pending_exits - forced)
        try:
            actions = list(dividends)
        except TypeError as exc:
            raise LedgerError("dividends must be a sequence of Dividend records") from exc
        new_ids = set()
        for action in actions:
            if not isinstance(action, Dividend):
                raise LedgerError("dividends must contain Dividend records")
            _identifier(action.event_id, "event_id")
            _identifier(action.security_id, "security_id")
            if _session(action.ex_date, "ex_date") != session:
                raise LedgerError("supply each dividend on its ex-date session")
            if _session(action.pay_date, "pay_date") < session:
                raise LedgerError("pay_date cannot precede ex_date")
            _number(action.amount_per_share, "amount_per_share")
            if action.event_id in self._dividend_ids or action.event_id in new_ids:
                raise LedgerError(f"duplicate dividend event_id: {action.event_id}")
            new_ids.add(action.event_id)

        previous_budget = self._reinvest_budget
        paid_today = 0.0
        fallback = dict(self._last_closes)
        for security, ratio in sorted(split_map.items()):
            before = self.positions.get(security, 0.0)
            after = before * ratio
            if not math.isfinite(after):
                raise LedgerError("split creates a nonfinite position")
            if before:
                self.positions[security] = after
            if security in fallback:
                fallback[security] /= ratio
            self.events.append({"session": session, "type": "split", "security_id": security,
                                "ratio": ratio, "shares_before": before, "shares_after": after})
        for action in actions:
            quantity = self.positions.get(action.security_id, 0.0)
            amount = quantity * float(action.amount_per_share)
            if not math.isfinite(amount):
                raise LedgerError("dividend creates a nonfinite receivable")
            record = {"event_id": action.event_id, "security_id": action.security_id,
                      "ex_date": action.ex_date, "pay_date": action.pay_date,
                      "amount_per_share": float(action.amount_per_share),
                      "ex_date_quantity": quantity, "amount": amount}
            self._dividend_ids.add(action.event_id)
            self.receivables[action.event_id] = record
            self.events.append({"session": session, "type": "dividend_receivable", **record})
        for event_id, record in list(self.receivables.items()):
            if record["pay_date"] <= session:
                self.cash += record["amount"]
                paid_today += record["amount"]
                self.events.append({"session": session, "type": "dividend_payment", **record})
                del self.receivables[event_id]

        self.pending_exits.update(forced)
        self._removed_ids.update(forced)
        for security in sorted(forced):
            self.events.append({"session": session, "type": "forced_exit_requested", "security_id": security})
        blocked = self._removed_ids | self.pending_exits
        if self._eligible_ids is not None:
            blocked |= (set(self.positions) | set(weights or {})) - self._eligible_ids
        valuation = {}
        for security, quantity in self.positions.items():
            mark = marks.get(security)
            if mark is None:
                mark = fallback.get(security)
                if mark is None:
                    raise LedgerError(f"missing open and previous close for held security {security}")
                self.exceptions.append({"session": session, "security_id": security,
                                        "type": "missing_open_valuation_only", "valuation_price": mark,
                                        "reason": "previous close, adjusted for today's split; not executable"})
            valuation[security] = quantity * mark
        pretrade_nav = self.cash + self.receivables_value + _finite_sum(valuation.values(), "opening securities value")
        if not math.isfinite(pretrade_nav):
            raise LedgerError("nonfinite opening NAV")

        orders: dict[str, tuple[float, str]] = {}
        for security in sorted(self.pending_exits):
            quantity = self.positions.get(security, 0.0)
            if not quantity:
                continue
            if marks.get(security) is None:
                self.exceptions.append({"session": session, "security_id": security,
                                        "type": "forced_exit_unfilled", "reason": "missing opening price; retry next session"})
            else:
                orders[security] = (-quantity, "forced_exit")
        if weights is not None:
            self.events.append({"session": session, "type": "scheduled_rebalance", "pretrade_nav": pretrade_nav})
            for security in sorted(set(self.positions) | set(weights)):
                if security in self.pending_exits:
                    continue  # Required exit dominates an overlapping target.
                desired_weight = weights.get(security, 0.0)
                if security in blocked and desired_weight:
                    self.exceptions.append({"session": session, "security_id": security,
                                            "type": "target_excluded", "reason": "security is removed or ineligible"})
                    desired_weight = 0.0
                price = marks.get(security)
                if price is None:
                    if self.positions.get(security, 0.0) or desired_weight:
                        self.exceptions.append({"session": session, "security_id": security,
                                                "type": "ordinary_order_unfilled", "reason": "missing opening price; order cancelled"})
                    continue
                quantity = desired_weight * pretrade_nav / price - self.positions.get(security, 0.0)
                if quantity:
                    orders[security] = (quantity, "scheduled_rebalance")
            # A scheduled selection can use every cash dollar, including newly
            # paid dividends; no payment is earmarked for a second next-day buy.
            self._reinvest_budget = 0.0
        else:
            budget = min(previous_budget, self.cash)
            eligible_values = {
                security: value for security, value in self._last_close_values.items()
                if value > 0 and self.positions.get(security, 0.0) > 0 and security not in blocked
                and (self._eligible_ids is None or security in self._eligible_ids)
            }
            denominator = _finite_sum(eligible_values.values(), "reinvestment weights")
            if budget > 0 and denominator > 0:
                self.events.append({"session": session, "type": "dividend_reinvestment", "budget": budget,
                                    "weighting": "preceding_close_eligible_holdings", "pretrade_nav": pretrade_nav})
                for security, value in sorted(eligible_values.items()):
                    price = marks.get(security)
                    if price is None:
                        self.exceptions.append({"session": session, "security_id": security,
                                                "type": "ordinary_order_unfilled", "reason": "missing opening price; dividend order cancelled"})
                        continue
                    quantity = budget * (value / denominator) / (1 + self.cost_bps / 10_000) / price
                    orders[security] = (quantity, "dividend_reinvestment")
            self._reinvest_budget = paid_today

        self._execute(session, marks, orders, pretrade_nav)
        self.pending_exits.intersection_update(self.positions)
        rounding_tolerance = max(1e-10, abs(pretrade_nav) * 1e-12)
        if not math.isfinite(self.cash) or self.cash < -rounding_tolerance:
            raise LedgerError("cash accounting would borrow or become nonfinite")
        self.cash = max(0.0, self.cash)
        self._active_session = session

    def _execute(self, session, marks, orders, pretrade_nav):
        fee_rate = self.cost_bps / 10_000
        # All sale cash must actually arrive before buy sizing.
        for security, (quantity, reason) in sorted(orders.items()):
            if quantity >= 0:
                continue
            held = self.positions.get(security, 0.0)
            sold = min(-quantity, held)
            if sold <= 0:
                continue
            price = marks[security]
            notional = sold * price
            cost = notional * fee_rate
            if not all(math.isfinite(value) for value in (notional, cost)):
                raise LedgerError("nonfinite sale")
            self.cash += notional - cost
            remaining = held - sold
            if remaining > 0:
                self.positions[security] = remaining
            else:
                self.positions.pop(security, None)
            self._record_trade(session, security, "sell", sold, price, notional, cost, reason, pretrade_nav)
        buys = {security: item for security, item in orders.items() if item[0] > 0}
        required = _finite_sum((quantity * marks[security] * (1 + fee_rate) for security, (quantity, _) in buys.items()), "buy requirements")
        if not math.isfinite(required):
            raise LedgerError("nonfinite buy requirements")
        scale = min(1.0, self.cash / required) if required > 0 else 0.0
        for security, (quantity, reason) in sorted(buys.items()):
            bought = quantity * scale
            if bought <= 0:
                continue
            price = marks[security]
            notional = bought * price
            cost = notional * fee_rate
            self.cash -= notional + cost
            self.positions[security] = self.positions.get(security, 0.0) + bought
            self._record_trade(session, security, "buy", bought, price, notional, cost, reason, pretrade_nav)
        if scale < 1 and buys:
            self.exceptions.append({"session": session, "type": "buys_scaled_to_cash", "scale": scale,
                                    "reason": "available cash includes only executed sale proceeds and fees"})

    def _record_trade(self, session, security, side, quantity, price, notional, cost, reason, pretrade_nav):
        self.cumulative_cost += cost
        self.trades.append({"session": session, "security_id": security, "side": side,
                            "quantity": quantity, "price": price, "notional": notional,
                            "cost": cost, "reason": reason, "pretrade_nav": pretrade_nav})

    def close_session(self, session: str, closes: Mapping[str, float | None], *,
                      eligible_ids: Iterable[str] | None = None) -> dict[str, Any]:
        session = _session(session)
        if self._active_session != session:
            raise LedgerError("close must match the active open session")
        marks = _marks(closes, "closes")
        eligible = self._eligible_ids if eligible_ids is None else _ids(eligible_ids, "eligible_ids")
        values = {}
        for security, quantity in self.positions.items():
            if marks.get(security) is None:
                raise LedgerError(f"missing closing price for held security {security}; stale marks forbidden")
            values[security] = quantity * marks[security]
        securities_value = _finite_sum(values.values(), "closing securities value")
        receivables = self.receivables_value
        nav = self.cash + receivables + securities_value
        if not math.isfinite(nav):
            raise LedgerError("nonfinite closing NAV")
        snapshot = {"session": session, "cash": self.cash, "receivables": receivables,
                    "securities_value": securities_value, "nav": nav,
                    "cumulative_cost": self.cumulative_cost, "holdings_count": len(self.positions),
                    "max_security_weight": max(values.values(), default=0.0) / nav if nav else 0.0,
                    "cash_weight": self.cash / nav if nav else 0.0,
                    "receivables_weight": receivables / nav if nav else 0.0,
                    "positions": dict(sorted(self.positions.items())),
                    "pending_exits": sorted(self.pending_exits)}
        self._eligible_ids = eligible
        self._last_closes = {security: marks[security] for security in self.positions}
        self._last_close_values = values
        self._last_session = session
        self._active_session = None
        self.snapshots.append(deepcopy(snapshot))
        return snapshot
