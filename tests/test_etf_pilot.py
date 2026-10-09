"""Independent behavioral checks for the separately scoped ETF pilot."""

import copy
from datetime import date, timedelta
import math
import unittest
from unittest.mock import patch

from pilot.engine import PilotDataError, execute_rebalance, run_matrix
from spmo_lab.signals import score_momentum


def fixture():
    first, last = date(2023, 1, 2), date(2026, 10, 2)
    dates = []
    while first <= last:
        if first.weekday() < 5:
            dates.append(first.isoformat())
        first += timedelta(days=1)
    symbols = ["A", "B", "C", "SPY"]
    closes = {
        symbol: [100 * math.exp((0.0008 + offset * 0.00015) * i + 0.002 * math.sin(i / 3 + offset)) for i in range(len(dates))]
        for offset, symbol in enumerate(symbols)
    }
    data = {"sessions": dates, "adjusted_close": closes, "adjusted_open": {symbol: list(values) for symbol, values in closes.items()}}
    config = {
        "universe": ["A", "B", "C"], "benchmark": "SPY",
        "initial_signal_on_or_before": "2023-12-31",
        "report_anchor_on_or_before": "2024-12-31",
        "full_year_end_on_or_before": "2025-12-31",
        "case_end_on_or_before": "2026-10-02",
        "signal": {"lookbacks": [8, 6, 4], "skip": 1, "annualization": 252},
        "arms": {"M12": [1, 0, 0], "MMIX": [0.5, 0.3, 0.2]},
        "phase_pairs": [[month, month + 6] for month in range(1, 7)],
        "primary_reference_phase": [3, 9],
        "cost_bps_per_side_scenarios": [0, 5, 10, 25],
        "base_cost_bps_per_side": 5,
        "slots": 3, "initial_cash": 1_000_000,
    }
    return data, config


class RebalanceTests(unittest.TestCase):
    def test_initial_purchase_solves_post_fee_weights(self):
        cash, positions, receipt = execute_rebalance(1000, {}, {"A": 10, "B": 20}, {"A": 1 / 3, "B": 1 / 3}, 100)
        expected = 1000 / (1 + 0.01 * 2 / 3)
        self.assertAlmostEqual(receipt["posttrade_nav"], expected)
        self.assertAlmostEqual(positions["A"] * 10, expected / 3)
        self.assertAlmostEqual(positions["B"] * 20, expected / 3)
        self.assertAlmostEqual(cash, expected / 3)
        self.assertAlmostEqual(receipt["cost"], 1000 - expected)

    def test_sale_and_purchase_fee_identity(self):
        cash, positions, receipt = execute_rebalance(100, {"A": 90}, {"A": 10, "B": 5}, {"B": 1}, 25)
        expected = (1000 - 0.0025 * 900) / 1.0025
        self.assertAlmostEqual(receipt["posttrade_nav"], expected)
        self.assertAlmostEqual(receipt["cost"], 0.0025 * (900 + expected))
        self.assertEqual(cash, 0)
        self.assertNotIn("A", positions)
        self.assertAlmostEqual(positions["B"] * 5, expected)

    def test_liquidation_and_idle_cash(self):
        cash, positions, receipt = execute_rebalance(100, {"A": 90}, {"A": 10}, {}, 100)
        self.assertEqual(positions, {})
        self.assertAlmostEqual(cash, 991)
        self.assertAlmostEqual(receipt["turnover"], 0.9)
        self.assertEqual(receipt["cost"], 9)

    def test_rejects_leverage_and_negative_cash(self):
        with self.assertRaises(PilotDataError):
            execute_rebalance(1000, {}, {"A": 10}, {"A": 1.1}, 5)
        with self.assertRaises(PilotDataError):
            execute_rebalance(-1, {}, {}, {}, 5)


class PilotMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.config = fixture()
        cls.result = run_matrix(cls.data, cls.config)

    def run_by_id(self, run_id):
        return next(run for run in self.result["runs"] if run["run_id"] == run_id)

    def test_all_paths_and_shared_monthly_comparators(self):
        self.assertEqual(len(self.result["runs"]), 56)
        self.assertEqual(len(self.result["benchmarks"]), 4)
        rows = self.result["comparisons"]["full_period"]
        self.assertEqual(len(rows), 48)
        self.assertEqual(len({row["monthly_run_id"] for row in rows}), 8)
        for control in {row["monthly_run_id"] for row in rows}:
            self.assertEqual(sum(row["monthly_run_id"] == control for row in rows), 6)
        self.assertTrue(all(self.result["checks"].values()))

    def test_common_initialization_and_exact_next_session_fills(self):
        sessions = self.data["sessions"]
        decision = self.result["boundaries"]["initial_signal_on_or_before"]
        execution = sessions[sessions.index(decision) + 1]
        for run in self.result["runs"] + self.result["benchmarks"]:
            self.assertEqual(run["trades"][0]["decision_session"], decision)
            self.assertEqual(run["trades"][0]["session"], execution)
            for trade in run["trades"]:
                self.assertEqual(sessions.index(trade["session"]), sessions.index(trade["decision_session"]) + 1)

    def test_no_portfolio_reset_at_reporting_anchors(self):
        run = self.run_by_id("S12-03-09-5bps")
        boundary = self.result["boundaries"]["full_year_end_on_or_before"]
        index = next(i for i, row in enumerate(run["daily"]) if row["session"] == boundary)
        before, after = run["daily"][index], run["daily"][index + 1]
        self.assertEqual(before["positions"], after["positions"])
        self.assertEqual(before["cash"], after["cash"])
        self.assertEqual(run["metrics"]["full_period"]["end_nav"], run["metrics"]["ytd2026"]["start_nav"])
        self.assertNotEqual(run["metrics"]["ytd2026"]["start_nav"], self.config["initial_cash"])

    def test_full_year_returns_compound_to_full_period(self):
        for run in self.result["runs"]:
            compounded = math.prod(1 + year["total_return"] for year in run["metrics"]["annual"].values()) - 1
            self.assertAlmostEqual(compounded, run["metrics"]["full_period"]["total_return"])
        self.assertEqual(self.result["primary"]["full_period"]["phase"], [3, 9])
        self.assertEqual(self.result["primary"]["full_period"]["cost_bps_per_side"], 5)

    def test_complete_year_cagr_and_no_ytd_annualization(self):
        for run in self.result["runs"]:
            full = run["metrics"]["full_period"]
            self.assertEqual(full["annualization_years"], 1)
            self.assertAlmostEqual(full["cagr"], full["total_return"])
            self.assertIsNone(run["metrics"]["ytd2026"]["cagr"])
            self.assertIsNone(run["metrics"]["ytd2026"]["annualized_volatility"])
            self.assertIsNone(run["metrics"]["ytd2026"]["annualized_two_sided_turnover"])
        self.assertIsNone(self.result["primary"]["ytd2026"]["cagr_difference_pp"])

    def test_drawdown_includes_anchor_and_transaction_costs_exclude_burnin(self):
        run = self.run_by_id("M12-25bps")
        metrics = run["metrics"]["full_period"]
        values = [row["nav"] for row in run["daily"] if metrics["start_session"] <= row["session"] <= metrics["end_session"]]
        peak, expected = values[0], 0
        for value in values:
            peak = max(peak, value)
            expected = min(expected, value / peak - 1)
        self.assertAlmostEqual(metrics["max_drawdown"], expected)
        expected_cost = sum(t["cost"] for t in run["trades"] if metrics["start_session"] < t["session"] <= metrics["end_session"])
        self.assertAlmostEqual(metrics["transaction_cost"], expected_cost)
        self.assertLess(expected_cost, sum(t["cost"] for t in run["trades"]))

    def test_future_price_mutation_cannot_change_prior_decisions_or_account(self):
        changed = copy.deepcopy(self.data)
        cutoff = "2025-06-30"
        for symbol in changed["adjusted_close"]:
            for i, session in enumerate(changed["sessions"]):
                if session > cutoff:
                    changed["adjusted_close"][symbol][i] *= 8 if symbol == "A" else 0.2
                    changed["adjusted_open"][symbol][i] *= 8 if symbol == "A" else 0.2
        new = run_matrix(changed, self.config)
        for original, mutated in zip(self.result["runs"], new["runs"]):
            self.assertEqual([row for row in original["daily"] if row["session"] <= cutoff], [row for row in mutated["daily"] if row["session"] <= cutoff])
            self.assertEqual([row for row in original["signals"] if row["decision_session"] <= cutoff], [row for row in mutated["signals"] if row["decision_session"] <= cutoff])

    def test_same_close_decision_does_not_receive_same_close_fill(self):
        changed = copy.deepcopy(self.data)
        formation = self.result["boundaries"]["initial_signal_on_or_before"]
        index = changed["sessions"].index(formation)
        following = index + 1
        for symbol in self.config["universe"]:
            changed["adjusted_open"][symbol][following] *= 2
        new = run_matrix(changed, self.config)
        original = self.run_by_id("M12-0bps")
        mutated = next(run for run in new["runs"] if run["run_id"] == "M12-0bps")
        self.assertEqual(original["signals"][0], mutated["signals"][0])
        self.assertEqual(original["daily"][0], mutated["daily"][0])
        for symbol, units in original["daily"][1]["positions"].items():
            self.assertAlmostEqual(mutated["daily"][1]["positions"][symbol], units / 2)

    def test_empty_slots_remain_cash(self):
        data = copy.deepcopy(self.data)
        # Only A has a positive monotone trend with varying daily returns.
        for symbol in ("B", "C"):
            values = [100 * math.exp(-0.001 * i + 0.00001 * math.sin(i)) for i in range(len(data["sessions"]))]
            data["adjusted_open"][symbol] = values
            data["adjusted_close"][symbol] = values
        result = run_matrix(data, self.config)
        run = next(run for run in result["runs"] if run["run_id"] == "M12-0bps")
        self.assertEqual(run["signals"][0]["selected"], ["A"])
        self.assertAlmostEqual(run["daily"][1]["cash_weight"], 2 / 3)

    def test_missing_or_duplicate_observations_block_the_run(self):
        data = copy.deepcopy(self.data)
        data["adjusted_open"]["A"][10] = None
        with self.assertRaises(PilotDataError):
            run_matrix(data, self.config)
        data = copy.deepcopy(self.data)
        data["sessions"][10] = data["sessions"][9]
        with self.assertRaises(PilotDataError):
            run_matrix(data, self.config)

    def test_only_past_window_is_sent_to_score_primitive(self):
        observed = []
        original = score_momentum

        def record(prices, weights, **kwargs):
            observed.append(tuple(prices))
            return original(prices, weights, **kwargs)

        with patch("pilot.engine.score_momentum", side_effect=record):
            result = run_matrix(self.data, self.config)
        expected_windows = {
            tuple(self.data["adjusted_close"][symbol][i - 8:i + 1])
            for i, session in enumerate(self.data["sessions"])
            if i >= 8
            for symbol in self.config["universe"]
        }
        self.assertTrue(all(window in expected_windows for window in observed if window))
        self.assertEqual(len([window for window in observed if window]), result["unique_signal_evaluations"] * len(self.config["universe"]))


if __name__ == "__main__":
    unittest.main()
