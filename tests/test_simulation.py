"""Point-in-time orchestration, scheduling and reporting boundaries."""

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from pathlib import Path
import unittest

from spmo_lab.signals import SignalDataError
from spmo_lab.simulation import (
    Bar, Capitalization, Dataset, MembershipEvent, NY, Session, SimulationError,
    _signal_targets, members_at, metrics_for, run_arm, selection_due, validate_dataset,
)
from spmo_lab.synthetic import make_fixture


ROOT = Path(__file__).resolve().parents[1]


def protocol():
    return json.loads((ROOT / "configs" / "experiment.v1.json").read_text())


def session(day):
    parsed = date.fromisoformat(day)
    return Session(day, datetime.combine(parsed, time(9, 30), NY),
                   datetime.combine(parsed, time(16), NY))


def small_fixture():
    """Tiny helper fixture, deliberately outside the full-run protocol gate."""
    sessions = [session(day) for day in (
        "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
        "2025-02-03", "2025-02-04",
    )]
    paths = {"A": [100, 110, 105, 120, 118, 121, 123],
             "B": [90, 95, 94, 100, 104, 105, 107]}
    origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
    bars = {security: {s.day: Bar(price, price, price, s.close_at)
                       for s, price in zip(sessions, prices)}
            for security, prices in paths.items()}
    caps = [Capitalization(security, s.day, 100, s.close_at)
            for security in paths for s in sessions]
    data = Dataset(sessions, bars,
                   [MembershipEvent(security, True, origin, origin) for security in paths],
                   caps, [], {}, {"A": "ISSUER-A", "B": "ISSUER-B"})
    config = protocol()
    config["signal_definition"].update({"lookback_sessions": [4], "skip_sessions": 1})
    config["common"].update({"security_weight_cap": 1, "target_count": 2})
    config["arms"]["S12"]["signal_weights"] = [1]
    return data, config


def targets(data, config, index=4):
    cap_index = {}
    for cap in data.capitalizations:
        cap_index.setdefault((cap.security_id, cap.day), []).append(cap)
    return _signal_targets(data, config, config["arms"]["S12"], index, cap_index)


class PointInTimeTests(unittest.TestCase):
    def test_membership_requires_effective_time_and_knowledge(self):
        origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
        effective = origin + timedelta(days=1)
        learned = origin + timedelta(days=2)
        events = [MembershipEvent("A", True, origin, origin),
                  MembershipEvent("A", False, effective, learned),
                  MembershipEvent("B", True, learned, effective)]
        self.assertEqual(members_at(events, origin), {"A"})
        self.assertEqual(members_at(events, effective), {"A"})
        self.assertEqual(members_at(events, learned), {"B"})
        self.assertEqual(members_at(list(reversed(events)), learned), {"B"})

    def test_future_signal_values_do_not_change_prior_decisions(self):
        data, config = small_fixture()
        original = targets(data, config)
        for security in data.bars:
            for later in data.sessions[5:]:
                old = data.bars[security][later.day]
                data.bars[security][later.day] = replace(old, signal_close=1e12)
            # The decision close itself is within the skipped interval.
            old = data.bars[security][data.sessions[4].day]
            data.bars[security][data.sessions[4].day] = replace(old, signal_close=1e15)
        self.assertEqual(targets(data, config), original)

    def test_historical_signal_unavailable_at_decision_is_rejected(self):
        data, config = small_fixture()
        required = data.sessions[1].day
        old = data.bars["A"][required]
        data.bars["A"][required] = replace(
            old, signal_known_at=data.sessions[4].close_at + timedelta(seconds=1))
        with self.assertRaises(SignalDataError):
            targets(data, config)

    def test_missing_required_signal_observation_is_rejected(self):
        for missing_row in (True, False):
            data, config = small_fixture()
            required = data.sessions[1].day
            if missing_row:
                del data.bars["A"][required]
            else:
                data.bars["A"][required] = replace(data.bars["A"][required], signal_close=None)
            with self.subTest(missing_row=missing_row), self.assertRaises(SignalDataError):
                targets(data, config)

    def test_future_or_wrong_session_cap_cannot_support_current_decision(self):
        for future in (True, False):
            data, config = small_fixture()
            decision = data.sessions[4]
            data.capitalizations = [
                cap for cap in data.capitalizations
                if not (cap.security_id == "A" and cap.day == decision.day)
            ]
            if future:
                data.capitalizations.append(Capitalization(
                    "A", decision.day, 100, decision.close_at + timedelta(seconds=1)))
            # Earlier-session observations remain present in either case.
            with self.subTest(future=future), self.assertRaisesRegex(SimulationError, "capitalization"):
                targets(data, config)

    def test_latest_available_cap_revision_wins_and_future_revision_is_ignored(self):
        data, config = small_fixture()
        decision = data.sessions[4]
        data.capitalizations = [
            cap for cap in data.capitalizations
            if not (cap.security_id == "A" and cap.day == decision.day)
        ]
        data.capitalizations.extend([
            Capitalization("A", decision.day, 100, decision.close_at - timedelta(seconds=2)),
            Capitalization("A", decision.day, 400, decision.close_at - timedelta(seconds=1)),
            Capitalization("A", decision.day, 999999, decision.close_at + timedelta(seconds=1)),
        ])
        _, decisions = targets(data, config)
        observed = {item["security_id"]: item["market_cap"] for item in decisions}
        self.assertEqual(observed, {"A": 400, "B": 100})


class ScheduleAndReportingTests(unittest.TestCase):
    def test_selection_uses_next_supplied_month_and_does_not_invent_final_month_end(self):
        sessions = [session(day) for day in (
            "2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04")]
        self.assertFalse(selection_due(sessions, 0, "monthly"))
        self.assertTrue(selection_due(sessions, 1, "monthly"))
        self.assertFalse(selection_due(sessions, 2, "monthly"))
        self.assertFalse(selection_due(sessions, 3, "monthly"))
        self.assertFalse(selection_due(sessions, 1, "semiannual"))
        march = [session("2025-03-31"), session("2025-04-01")]
        self.assertTrue(selection_due(march, 0, "semiannual"))

    def test_reporting_uses_existing_anchor_nav_and_only_later_costs(self):
        rows = [{"session": "2025-12-30", "nav": 90},
                {"session": "2025-12-31", "nav": 120},
                {"session": "2026-01-02", "nav": 100},
                {"session": "2026-01-05", "nav": 132}]
        trades = [
            {"session": "2025-12-30", "cost": 99, "notional": 990, "pretrade_nav": 90},
            {"session": "2025-12-31", "cost": 9, "notional": 900, "pretrade_nav": 120},
            {"session": "2026-01-02", "cost": 0.1, "notional": 20, "pretrade_nav": 100},
            {"session": "2026-01-02", "cost": 0.2, "notional": 40, "pretrade_nav": 100},
        ]
        result = metrics_for(rows, trades, "2025-12-31", "2026-01-05")
        self.assertAlmostEqual(result["net_total_return"], 0.1)
        self.assertAlmostEqual(result["maximum_drawdown"], -1 / 6)
        self.assertAlmostEqual(result["reporting_cost"], 0.3)
        self.assertEqual(result["gross_traded_notional"], 60)
        self.assertAlmostEqual(result["two_sided_turnover"], 0.6)
        self.assertEqual(result["reporting_close_count"], 3)
        self.assertEqual(result["anchor_nav"], 120)

    def test_missing_reporting_boundary_cannot_be_substituted(self):
        rows = [{"session": "2026-01-02", "nav": 100}]
        with self.assertRaises(SimulationError):
            metrics_for(rows, [], "2025-12-31", "2026-01-02")
        with self.assertRaises(SimulationError):
            metrics_for(rows, [], "2026-01-02", "2026-01-05")


class RunValidationTests(unittest.TestCase):
    def test_unsupported_policy_changes_are_rejected_before_execution(self):
        for section, key, value in (("signal_definition", "volatility_ddof", 0),
                                    ("signal_definition", "cross_sectional_zscore", True),
                                    ("common", "cash_annual_yield", 0.04),
                                    ("common", "dividend_accounting", "cash_on_ex_date")):
            config = protocol()
            config[section][key] = value
            data, _ = small_fixture()
            with self.subTest(key=key), self.assertRaisesRegex(SimulationError, "frozen v0.2"):
                run_arm(data, config, "S12", 5)

    def test_market_data_and_unsupported_events_are_rejected(self):
        for changes in ({"data_track": "market"}, {"unsupported_events": ("unresolved merger",)}):
            data, _ = small_fixture()
            for key, value in changes.items():
                setattr(data, key, value)
            with self.subTest(changes=changes), self.assertRaises(SimulationError):
                run_arm(data, protocol(), "S12", 5)

    def test_ambiguous_membership_and_naive_availability_are_rejected(self):
        data, _ = small_fixture()
        original = data.membership[0]
        data.membership.append(replace(original, active=False))
        with self.assertRaises(SimulationError):
            validate_dataset(data)
        data, _ = small_fixture()
        day = data.sessions[0].day
        data.bars["A"][day] = replace(data.bars["A"][day], signal_known_at=datetime(2025, 1, 27))
        with self.assertRaises(SimulationError):
            validate_dataset(data)


class SyntheticIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = protocol()
        cls.data = make_fixture(cls.config, security_count=8)
        cls.result = run_arm(cls.data, cls.config, "S12", 5)

    def test_initial_signal_executes_at_next_supplied_open_with_per_side_cost(self):
        initial = self.config["period"]["initial_signal_close"]
        index = next(i for i, item in enumerate(self.data.sessions) if item.day == initial)
        next_session = self.data.sessions[index + 1].day
        self.assertTrue(self.result["trades"])
        self.assertEqual(self.result["trades"][0]["session"], next_session)
        self.assertFalse(any(item["session"] == initial for item in self.result["trades"]))
        self.assertEqual(self.result["daily"][0]["nav"], 1_000_000)
        for trade in self.result["trades"]:
            self.assertAlmostEqual(trade["cost"], trade["notional"] * 0.0005)

    def test_anchor_keeps_holdings_and_measurement_excludes_burn_in_costs(self):
        anchor = self.config["period"]["report_anchor_close"]
        end = self.config["period"]["report_end_close"]
        snapshot = self.result["snapshots"][anchor]
        self.assertTrue(snapshot["positions"])
        self.assertNotEqual(snapshot["nav"], 100)
        report_costs = math.fsum(t["cost"] for t in self.result["trades"] if anchor < t["session"] <= end)
        all_costs = math.fsum(t["cost"] for t in self.result["trades"])
        self.assertGreater(all_costs, report_costs)
        self.assertAlmostEqual(self.result["metrics"]["reporting_cost"], report_costs)
        self.assertAlmostEqual(self.result["metrics"]["net_total_return"],
                               self.result["snapshots"][end]["nav"] / snapshot["nav"] - 1)
        # December is not a semiannual selection month; normalization itself
        # must not manufacture either a selection or a cash reset.
        self.assertFalse(any(t["session"] == anchor for t in self.result["trades"]))
        self.assertFalse(any(s["decision_session"] == anchor for s in self.result["signals"]))


if __name__ == "__main__":
    unittest.main()
