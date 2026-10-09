"""Independent accounting/timing cases for the separate stock proxy."""

from copy import deepcopy
from datetime import date, timedelta
import math
import unittest

from stock_pilot.engine import StockPilotError, run_matrix


def fixture(count=15):
    day, stop = date(2023, 12, 1), date(2026, 10, 2)
    sessions = []
    while day <= stop:
        if day.weekday() < 5:
            sessions.append(day.isoformat())
        day += timedelta(days=1)
    ids = [f"ID{i:02d}" for i in range(count)]
    bars, caps = {}, {}
    for n, security in enumerate(ids + ["SPY"]):
        bars[security], caps[security] = {}, {}
        for index, session in enumerate(sessions):
            price = (40 + n) * math.exp(.0005 * index + .01 * math.sin(index / 13 + n))
            bars[security][session] = {"signal_close": price, "adjusted_open": price, "adjusted_close": price}
            caps[security][session] = 1_000_000_000 + n * 50_000_000
    data = {"sessions": sessions, "bars": bars, "market_caps": caps,
            "cohort": ids, "security": {s: {"ticker": s, "issuer_id": s} for s in ids},
            "membership_by_day": {s: list(ids) for s in sessions}, "universe_exclusions": []}
    config = {"initial_signal": "2024-12-31", "report_anchor": "2025-12-31", "report_end": "2026-10-02",
              "slots": 75, "cap": .08, "costs": [0, 5, 10, 25], "benchmarks": ["SPY"],
              "arms": {"S12": {"frequency": "semiannual", "signal_weights": [1, 0, 0]},
                       "M12": {"frequency": "monthly", "signal_weights": [1, 0, 0]},
                       "SMIX": {"frequency": "semiannual", "signal_weights": [.5, .3, .2]},
                       "MMIX": {"frequency": "monthly", "signal_weights": [.5, .3, .2]}}}
    return data, config


class StockPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.config = fixture()
        cls.result = run_matrix(cls.data, cls.config)

    def run_for(self, strategy="M12", cost=0, result=None):
        return next(r for r in (result or self.result)["runs"]
                    if r["strategy_id"] == strategy and r["cost_bps_per_side"] == cost)

    def test_all_paths_benchmarks_and_proxy_labels(self):
        self.assertEqual(len(self.result["runs"]), 16)
        self.assertEqual(len(self.result["benchmarks"]), 4)
        self.assertEqual(len(self.result["comparisons"]), 12)
        self.assertTrue(all(self.result["checks"].values()))
        self.assertEqual(self.result["data_track"], "baseline_issuer_stock_pilot")
        self.assertFalse(self.result["formal_protocol_compliant"])
        self.assertNotIn("daily", self.result["summary"]["runs"][0])

    def test_signal_close_executes_next_open_and_monthly_december_crosses_anchor(self):
        run = self.run_for()
        first = run["trades"][0]
        self.assertEqual(first["decision_session"], "2024-12-31")
        self.assertEqual(first["session"], "2025-01-01")
        january = next(t for t in run["trades"] if t["decision_session"] == "2025-12-31")
        self.assertEqual(january["session"], "2026-01-01")
        semi = self.run_for("S12")
        self.assertTrue(all(t["decision_session"][5:7] in ("03", "09") for t in semi["trades"][1:]))

    def test_anchor_retains_state_and_excludes_burnin_costs(self):
        run = self.run_for(cost=25)
        anchor = next(r for r in run["daily"] if r["session"] == "2025-12-31")
        self.assertEqual(anchor["nav_index_2026"], 100)
        self.assertGreater(anchor["holdings_count"], 0)
        self.assertEqual(run["metrics"]["year2025"]["end_nav"], run["metrics"]["ytd2026"]["start_nav"])
        expected = sum(t["cost"] for t in run["trades"] if t["session"] > "2025-12-31")
        self.assertAlmostEqual(run["metrics"]["ytd2026"]["transaction_cost"], expected)
        self.assertGreater(run["metrics"]["full_period"]["transaction_cost"], expected)

    def test_initial_purchase_is_self_financing_with_fees(self):
        run = self.run_for(cost=25)
        first = run["trades"][0]
        self.assertAlmostEqual(first["traded_notional"], 1_000_000 / 1.0025)
        self.assertAlmostEqual(first["cost"], first["traded_notional"] * .0025)
        self.assertAlmostEqual(first["posttrade_nav"], 1_000_000 - first["cost"])
        self.assertTrue(all(row["cash"] >= 0 for row in run["daily"]))

    def test_fewer_names_use_cap_capacity_not_n_over_75(self):
        data, config = fixture(2)
        result = run_matrix(data, config)
        run = self.run_for(result=result)
        first = run["trades"][0]
        self.assertAlmostEqual(first["traded_notional"], 160_000)
        self.assertAlmostEqual(run["daily"][1]["cash"], 840_000)
        self.assertTrue(all(r["target_weight"] == .08 for r in run["signals"] if r["decision_session"] == "2024-12-31"))

    def test_removal_sells_at_next_open_and_leaves_proceeds_in_cash(self):
        data = deepcopy(self.data)
        removed = "ID00"
        removal_day = "2025-02-12"
        for day in data["sessions"]:
            if day >= removal_day:
                data["membership_by_day"][day].remove(removed)
        result = run_matrix(data, self.config)
        run = self.run_for("S12", result=result)
        before = next(r for r in run["daily"] if r["session"] == removal_day)
        after = next(r for r in run["daily"] if r["session"] == "2025-02-13")
        self.assertIn(removed, before["positions"])
        self.assertNotIn(removed, after["positions"])
        self.assertGreater(after["cash"], before["cash"])
        for security in after["positions"]:
            self.assertEqual(after["positions"][security], before["positions"][security])
        event = next(t for t in run["trades"] if t["reason"] == "forced_membership_exit")
        self.assertEqual(event["decision_session"], removal_day)
        self.assertEqual(event["session"], "2025-02-13")
        self.assertEqual(event["orders"][0]["security_id"], removed)

    def test_missing_forced_exit_quote_blocks_without_last_quote_sale(self):
        data = deepcopy(self.data)
        for day in data["sessions"]:
            if day >= "2025-02-12":
                data["membership_by_day"][day].remove("ID00")
        del data["bars"]["ID00"]["2025-02-13"]["adjusted_open"]
        with self.assertRaisesRegex(StockPilotError, "ID00/2025-02-13.*adjusted_open"):
            run_matrix(data, self.config)

    def test_missing_cap_or_signal_or_held_close_blocks(self):
        for field, day in (("cap", "2024-12-31"), ("signal_close", "2024-06-03"), ("adjusted_close", "2025-02-12")):
            data = deepcopy(self.data)
            if field == "cap":
                del data["market_caps"]["ID00"][day]
            else:
                del data["bars"]["ID00"][day][field]
            with self.subTest(field=field), self.assertRaises(StockPilotError):
                run_matrix(data, self.config)

    def test_nonmembers_do_not_enter_despite_extreme_scores(self):
        data = deepcopy(self.data)
        for day in data["sessions"]:
            data["membership_by_day"][day].remove("ID00")
        result = run_matrix(data, self.config)
        self.assertTrue(all("ID00" not in row["positions"] for r in result["runs"] for row in r["daily"]))
        self.assertTrue(all(s["security_id"] != "ID00" for r in result["runs"] for s in r["signals"]))

    def test_explicit_listing_date_allows_only_genuine_short_history(self):
        data = deepcopy(self.data)
        data["security"]["ID00"]["listed_from"] = "2024-10-01"
        for day in list(data["bars"]["ID00"]):
            if day < "2024-10-01":
                del data["bars"]["ID00"][day]
        result = run_matrix(data, self.config)
        initial = [row for row in self.run_for(result=result)["signals"]
                   if row["security_id"] == "ID00" and row["decision_session"] == "2024-12-31"]
        self.assertEqual(initial[0]["reason"], "insufficient_listing_history")
        later = [row for row in self.run_for(result=result)["signals"]
                 if row["security_id"] == "ID00" and row["decision_session"] >= "2025-10-31"]
        self.assertTrue(later)
        self.assertTrue(all(row["score"] is not None for row in later))
        del data["bars"]["ID00"]["2025-03-03"]
        with self.assertRaisesRegex(StockPilotError, "ID00/2025-03-03"):
            run_matrix(data, self.config)

    def test_future_prices_do_not_change_prior_decisions(self):
        data = deepcopy(self.data)
        for day, row in data["bars"]["ID00"].items():
            if day > "2025-06-30":
                for field in row:
                    row[field] *= 2
        result = run_matrix(data, self.config)
        before = [r for r in self.run_for()["signals"] if r["decision_session"] <= "2025-06-30"]
        after = [r for r in self.run_for(result=result)["signals"] if r["decision_session"] <= "2025-06-30"]
        self.assertEqual(before, after)

    def test_skipped_tail_does_not_require_signal_prices(self):
        data = deepcopy(self.data)
        del data["bars"]["ID00"]["2026-09-30"]["signal_close"]
        result = run_matrix(data, self.config)
        before = [r for r in self.run_for()["signals"] if r["decision_session"] == "2026-09-30"]
        after = [r for r in self.run_for(result=result)["signals"] if r["decision_session"] == "2026-09-30"]
        self.assertEqual(before, after)

    def test_empty_membership_is_cash_and_invalid_contract_rejected(self):
        data = deepcopy(self.data)
        data["membership_by_day"] = {d: [] for d in data["sessions"]}
        result = run_matrix(data, self.config)
        self.assertTrue(all(row["cash"] == 1_000_000 for r in result["runs"] for row in r["daily"]))
        self.assertTrue(all(r["metrics"]["full_period"]["total_return"] == 0 for r in result["runs"]))
        config = deepcopy(self.config)
        config["arms"]["S12"]["frequency"] = "monthly"
        with self.assertRaises(StockPilotError):
            run_matrix(self.data, config)


if __name__ == "__main__":
    unittest.main()
