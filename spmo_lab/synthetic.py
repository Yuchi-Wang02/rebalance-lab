"""Deterministic fictional inputs; never a substitute for licensed market data."""

from datetime import date, datetime, time, timedelta, timezone
import math

from .ledger import Dividend
from .simulation import Bar, Capitalization, Dataset, MembershipEvent, NY, Session


def make_fixture(config, security_count=80):
    period = config["period"]
    first = date.fromisoformat(period["warmup_request_start"])
    last = date.fromisoformat(period["report_end_close"])
    # Deliberately fictional closure list, not a trading-calendar source.
    closures = {"2024-01-01", "2025-01-01", "2026-01-01"}
    sessions = []
    current = first
    while current <= last:
        if current.weekday() < 5 and current.isoformat() not in closures:
            sessions.append(Session(current.isoformat(),
                                    datetime.combine(current, time(9, 30), NY).astimezone(timezone.utc),
                                    datetime.combine(current, time(16), NY).astimezone(timezone.utc)))
        current += timedelta(days=1)
    by_day = {s.day: i for i, s in enumerate(sessions)}
    securities = [f"SYN{i:03d}" for i in range(security_count)]
    origin = datetime(2020, 1, 1, tzinfo=timezone.utc)
    membership = [MembershipEvent(s, True, origin, origin) for s in securities]
    membership.extend([
        MembershipEvent("SYN003", False, datetime(2025, 5, 15, 0, tzinfo=NY),
                        datetime(2025, 5, 13, 12, tzinfo=NY)),
        MembershipEvent("SYN003", True, datetime(2025, 12, 15, 0, tzinfo=NY),
                        datetime(2025, 12, 12, 12, tzinfo=NY)),
        MembershipEvent("SYN007", False, datetime(2026, 3, 18, 0, tzinfo=NY),
                        datetime(2026, 3, 20, 12, tzinfo=NY)),
    ])
    dividends = []
    for security in securities[:4]:
        for ex_day in ("2025-03-20", "2025-09-18", "2026-03-19", "2026-06-18"):
            pay_day = sessions[by_day[ex_day] + 10].day
            dividends.append(Dividend(f"{security}-{ex_day}", security, ex_day, pay_day, 0.12))
    splits = {"2025-06-16": {"SYN000": 2.0}, "2026-02-17": {"SYN001": 3.0}}
    bars, capitals = {}, []
    for n, security in enumerate(securities):
        bars[security] = {}
        factor, dividend_shift, previous_signal = 1.0, 0.0, None
        for i, session in enumerate(sessions):
            factor *= splits.get(session.day, {}).get(security, 1.0)
            dividend_shift += sum(d.amount_per_share * factor for d in dividends
                                  if d.security_id == security and d.ex_date == session.day)
            # Oscillating deterministic paths exercise rank changes without
            # borrowing prices or estimated returns from real securities.
            base = (35 + n * 1.7) * math.exp(
                (0.00020 + (n % 11) * 0.000045) * i
                + 0.075 * math.sin(i / (24 + n % 17) + n * 0.57)
                + 0.004 * math.sin(i * 1.73 + n))
            signal = base - dividend_shift
            opening = (previous_signal if previous_signal is not None else signal) * (
                1 + 0.0015 * math.sin(i * 0.73 + n)) / factor
            bars[security][session.day] = Bar(opening, signal / factor, signal, session.close_at)
            capitals.append(Capitalization(security, session.day,
                                          (2_000_000_000 + n * 170_000_000) * signal / (35 + n * 1.7),
                                          session.close_at))
            previous_signal = signal
    return Dataset(sessions, bars, membership, capitals, dividends, splits,
                   {s: f"ISSUER-{n // 2:03d}" for n, s in enumerate(securities)})
