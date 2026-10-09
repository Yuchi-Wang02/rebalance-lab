"""Deterministic momentum selection primitives for the frozen protocol.

The caller supplies prices on a common exchange calendar through the decision
close. This module does not infer missing sessions, adjust prices, or fetch data.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from numbers import Real
import statistics


class SignalDataError(ValueError):
    """A required input or configuration cannot support a reliable signal."""


@dataclass(frozen=True)
class SignalResult:
    score: float | None
    components: tuple[float | None, ...]
    reason: str | None


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise SignalDataError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise SignalDataError(f"{label} must be a finite number") from error
    if not math.isfinite(number):
        raise SignalDataError(f"{label} must be a finite number")
    return number


def score_momentum(
    prices: Sequence[float | None],
    weights: Sequence[float],
    *,
    lookbacks: Sequence[int] = (252, 126, 63),
    skip: int = 21,
    annualization: float = 252,
) -> SignalResult:
    """Compute the weighted, volatility-scaled price momentum at the last row.

    For horizon ``L``, the price return is ``P[t-skip] / P[t-L] - 1``.
    Its denominator is the sample standard deviation (ddof=1) of the
    ``L-skip`` simple daily returns within those exact endpoints, annualized
    by ``sqrt(annualization)``. Disabled horizons have a ``None`` component.

    Insufficient history, zero volatility and nonpositive combined scores
    are explicit eligibility outcomes. A corrupt required observation raises
    SignalDataError; it must not silently remove a security from the universe.
    """
    if isinstance(skip, bool) or not isinstance(skip, int) or skip < 0:
        raise SignalDataError("skip must be a nonnegative integer")
    factor = _finite_number(annualization, "annualization")
    if factor <= 0:
        raise SignalDataError("annualization must be positive")
    if len(weights) != len(lookbacks) or not weights:
        raise SignalDataError("weights and lookbacks must have equal nonzero lengths")
    coefficients = tuple(_finite_number(value, "weight") for value in weights)
    if any(value < 0 for value in coefficients):
        raise SignalDataError("weights must be nonnegative")
    try:
        total_weight = math.fsum(coefficients)
    except OverflowError as error:
        raise SignalDataError("weight sum overflow") from error
    if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise SignalDataError("weights must sum to one")
    active = []
    for index, (lookback, weight) in enumerate(zip(lookbacks, coefficients)):
        if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback <= 0:
            raise SignalDataError("lookbacks must be positive integers")
        if weight > 0:
            if lookback - skip < 2:
                raise SignalDataError("enabled horizons require at least two daily returns")
            active.append((index, lookback, weight))

    components: list[float | None] = [None] * len(lookbacks)
    if any(len(prices) <= lookback for _, lookback, _ in active):
        return SignalResult(None, tuple(components), "insufficient_history")

    last = len(prices) - 1
    end = last - skip
    # Validate every required window before classifying zero volatility. A
    # zero-volatility horizon must not hide a corrupt second enabled horizon.
    windows = []
    for index, lookback, weight in active:
        start = last - lookback
        window = []
        for position in range(start, end + 1):
            value = _finite_number(prices[position], f"price at index {position}")
            if value <= 0:
                raise SignalDataError(f"price at index {position} must be positive")
            window.append(value)
        windows.append((index, weight, window))

    zero_volatility = False
    for index, _, window in windows:
        daily_returns = []
        for previous, current in zip(window, window[1:]):
            value = current / previous - 1.0
            if not math.isfinite(value):
                raise SignalDataError("daily return overflow")
            daily_returns.append(value)
        volatility = statistics.stdev(daily_returns)
        if not math.isfinite(volatility):
            raise SignalDataError("volatility overflow")
        if volatility == 0:
            zero_volatility = True
            continue
        price_return = window[-1] / window[0] - 1.0
        denominator = volatility * math.sqrt(factor)
        if not math.isfinite(price_return) or not math.isfinite(denominator):
            raise SignalDataError("momentum arithmetic overflow")
        if denominator == 0:
            raise SignalDataError("annualized volatility underflow")
        component = price_return / denominator
        if not math.isfinite(component):
            raise SignalDataError("momentum score overflow")
        components[index] = component
    if zero_volatility:
        return SignalResult(None, tuple(components), "zero_volatility")

    try:
        score = math.fsum(coefficients[index] * components[index] for index, _, _ in active)
    except OverflowError as error:
        raise SignalDataError("combined momentum score overflow") from error
    if not math.isfinite(score):
        raise SignalDataError("combined momentum score overflow")
    if score <= 0:
        return SignalResult(None, tuple(components), "nonpositive_score")
    return SignalResult(score, tuple(components), None)


def build_targets(
    scores: Mapping[str, float | None],
    market_caps: Mapping[str, float | None],
    *,
    count: int = 75,
    cap: float = 0.08,
) -> dict[str, float]:
    """Select positive scores and proportionally redistribute capped weights.

    Exact score ties use ascending security ID. Every positive candidate needs
    valid historical security-class market capitalization, including candidates
    below the selection cutoff. Residual cash is implicit as ``1-sum(targets)``;
    it arises from insufficient cap capacity, never from an N/count budget.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise SignalDataError("count must be a positive integer")
    limit = _finite_number(cap, "cap")
    if not 0 < limit <= 1:
        raise SignalDataError("cap must be in (0, 1]")
    candidates = []
    for security_id, value in scores.items():
        if not isinstance(security_id, str) or not security_id:
            raise SignalDataError("security IDs must be nonempty strings")
        if value is None:
            continue
        score = _finite_number(value, f"score for {security_id}")
        if score <= 0:
            continue
        capitalization = _finite_number(market_caps.get(security_id), f"market cap for {security_id}")
        if capitalization <= 0:
            raise SignalDataError(f"market cap for {security_id} must be positive")
        raw_weight = score * math.sqrt(capitalization)
        if not math.isfinite(raw_weight) or raw_weight <= 0:
            raise SignalDataError(f"raw target weight overflow or underflow for {security_id}")
        candidates.append((security_id, score, raw_weight))
    candidates.sort(key=lambda candidate: (-candidate[1], candidate[0]))
    selected = candidates[:count]
    if not selected:
        return {}

    allocated: dict[str, float] = {}
    remaining = selected
    while remaining:
        budget = max(0.0, 1.0 - math.fsum(allocated.values()))
        # Scaling avoids overflow in the sum without changing proportions.
        scale = max(candidate[2] for candidate in remaining)
        relative = {security_id: raw_weight / scale for security_id, _, raw_weight in remaining}
        denominator = math.fsum(relative.values())
        proposed = {security_id: budget * value / denominator for security_id, value in relative.items()}
        capped = {security_id for security_id, value in proposed.items() if value > limit}
        if not capped:
            allocated.update(proposed)
            break
        for security_id in sorted(capped):
            allocated[security_id] = limit
        remaining = [candidate for candidate in remaining if candidate[0] not in capped]

    # Roundoff must not create even a tiny negative cash balance. Correct the
    # largest allocation deterministically; no economic rescaling is involved.
    excess = math.fsum(allocated.values()) - 1.0
    if excess > 0:
        largest = min(allocated, key=lambda security_id: (-allocated[security_id], security_id))
        allocated[largest] -= excess
    return {security_id: allocated[security_id] for security_id in sorted(allocated)}
