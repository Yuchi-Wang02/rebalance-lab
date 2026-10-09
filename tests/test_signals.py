"""Protocol endpoints, missing-data failures, selection and cap allocation."""

import math
import statistics
import unittest

from spmo_lab.signals import SignalDataError, build_targets, score_momentum


class MomentumTests(unittest.TestCase):
    def test_exact_endpoints_sample_volatility_and_skipped_tail(self):
        # t=6, L=5, skip=2: endpoints are indices 1 and 4. The three
        # included daily returns are 10%, -10%, 20%; indices 5/6 are unused.
        prices = [None, 100.0, 110.0, 99.0, 118.8, None, float("nan")]
        result = score_momentum(prices, [1], lookbacks=[5], skip=2, annualization=4)
        expected = (118.8 / 100 - 1) / (statistics.stdev([0.1, -0.1, 0.2]) * 2)
        self.assertAlmostEqual(result.score, expected)
        self.assertEqual(result.reason, None)
        self.assertAlmostEqual(result.components[0], expected)

    def test_changes_after_skip_endpoint_cannot_change_current_signal(self):
        common = [8, 9, 8, 11, 10, 12]
        first = score_momentum(common + [10, 20], [1], lookbacks=[7], skip=2)
        second = score_momentum(common + [None, -100], [1], lookbacks=[7], skip=2)
        self.assertEqual(first, second)

    def test_disabled_horizon_does_not_require_its_history(self):
        result = score_momentum([100, 110, 105, 120, 118, None], [0, 1], lookbacks=[252, 5], skip=1)
        self.assertIsNone(result.components[0])
        self.assertGreater(result.score, 0)

    def test_disabled_long_horizon_does_not_validate_its_older_gaps(self):
        result = score_momentum([None, float("nan"), 100, 110, 105, 120, 118, None], [0, 1], lookbacks=[7, 5], skip=1)
        self.assertGreater(result.score, 0)

    def test_protocol_default_has_231_returns_and_253_price_positions(self):
        daily_returns = [0.01 if index % 2 else -0.005 for index in range(231)]
        prices = [100.0]
        for daily_return in daily_returns:
            prices.append(prices[-1] * (1 + daily_return))
        expected = (prices[-1] / prices[0] - 1) / (statistics.stdev(daily_returns) * math.sqrt(252))
        prices.extend([None] * 21)
        self.assertEqual(len(prices), 253)
        result = score_momentum(prices, [1, 0, 0])
        self.assertAlmostEqual(result.score, expected)
        self.assertEqual(result.components[1:], (None, None))
        self.assertEqual(score_momentum(prices[1:], [1, 0, 0]).reason, "insufficient_history")

    def test_required_gaps_and_invalid_prices_raise(self):
        for bad in (None, 0, -1, float("nan"), float("inf"), True, "100"):
            for index in (0, 2, 4):
                with self.subTest(bad=bad, index=index):
                    prices = [100, 110, 105, 120, 118, 130]
                    prices[index] = bad
                    with self.assertRaises(SignalDataError):
                        score_momentum(prices, [1], lookbacks=[5], skip=1)

    def test_short_listing_is_an_explicit_eligibility_outcome(self):
        result = score_momentum([100, 110, 105, 120], [1], lookbacks=[5], skip=1)
        self.assertEqual(result.reason, "insufficient_history")
        self.assertIsNone(result.score)
        self.assertEqual(result.components, (None,))

    def test_flat_prices_have_zero_volatility(self):
        result = score_momentum([100] * 6, [1], lookbacks=[5], skip=1)
        self.assertEqual(result.reason, "zero_volatility")
        self.assertIsNone(result.score)

    def test_zero_volatility_cannot_hide_corrupt_enabled_window(self):
        with self.assertRaises(SignalDataError):
            score_momentum([None, 100, 100, 100, 100, 100], [0.5, 0.5], lookbacks=[3, 5], skip=1)

    def test_nonpositive_score_is_ineligible_without_erasing_component(self):
        result = score_momentum([100, 80, 85, 70, 75, 90], [1], lookbacks=[5], skip=1)
        self.assertEqual(result.reason, "nonpositive_score")
        self.assertIsNone(result.score)
        self.assertLess(result.components[0], 0)

    def test_blend_uses_raw_components_without_cross_sectional_transform(self):
        prices = [100, 95, 110, 108, 117, 120, 125, 124]
        result = score_momentum(prices, [0.7, 0.3], lookbacks=[7, 4], skip=1)
        long = score_momentum(prices, [1], lookbacks=[7], skip=1)
        short = score_momentum(prices, [1], lookbacks=[4], skip=1)
        self.assertAlmostEqual(result.score, 0.7 * long.score + 0.3 * short.score)
        self.assertEqual(result.components, (long.score, short.score))

    def test_invalid_configuration_and_arithmetic_overflow_raise(self):
        configurations = [
            {"weights": [0]}, {"weights": [-1]}, {"weights": [float("nan")]},
            {"weights": [0.5]}, {"weights": [1, 0]}, {"weights": [True]},
            {"weights": [1], "skip": -1}, {"weights": [1], "skip": True},
            {"weights": [1], "lookbacks": [2]}, {"weights": [1], "lookbacks": [5.0]},
            {"weights": [1], "annualization": 0}, {"weights": [1], "annualization": float("inf")},
        ]
        for configuration in configurations:
            arguments = {"weights": [1], "lookbacks": [5], "skip": 1, **configuration}
            with self.subTest(configuration=configuration), self.assertRaises(SignalDataError):
                score_momentum([100, 110, 105, 120, 118, 130], **arguments)
        with self.assertRaises(SignalDataError):
            score_momentum([1e-308, 1e308, 1, 2], [1], lookbacks=[3], skip=0)


class TargetTests(unittest.TestCase):
    def test_ties_use_security_id_and_selection_is_deterministic(self):
        scores = {"Z": 4, "B": 4, "A": 4, "N": None, "X": -1}
        targets = build_targets(scores, {"A": 1, "B": 1, "Z": 1}, count=2, cap=1)
        reversed_targets = build_targets(dict(reversed(list(scores.items()))), {"Z": 1, "B": 1, "A": 1}, count=2, cap=1)
        self.assertEqual(targets, {"A": 0.5, "B": 0.5})
        self.assertEqual(list(targets.items()), list(reversed_targets.items()))

    def test_weights_use_square_root_of_security_capitalization(self):
        targets = build_targets({"A": 1, "B": 1}, {"A": 4, "B": 1}, cap=1)
        self.assertAlmostEqual(targets["A"], 2 / 3)
        self.assertAlmostEqual(targets["B"], 1 / 3)

    def test_cap_overflow_is_redistributed_proportionally(self):
        targets = build_targets({"A": 9, "B": 1, "C": 1}, {"A": 1, "B": 1, "C": 1}, cap=0.5)
        self.assertEqual(targets, {"A": 0.5, "B": 0.25, "C": 0.25})

    def test_redistribution_repeats_when_second_security_reaches_cap(self):
        targets = build_targets({"A": 100, "B": 9, "C": 1}, {"A": 1, "B": 1, "C": 1}, cap=0.4)
        self.assertAlmostEqual(targets["A"], 0.4)
        self.assertAlmostEqual(targets["B"], 0.4)
        self.assertAlmostEqual(targets["C"], 0.2)

    def test_fewer_than_target_count_can_still_be_fully_invested(self):
        scores = {f"S{index:02}": 1 for index in range(13)}
        targets = build_targets(scores, dict.fromkeys(scores, 1))
        self.assertAlmostEqual(math.fsum(targets.values()), 1)
        self.assertTrue(all(value <= 0.08 for value in targets.values()))
        self.assertAlmostEqual(targets["S00"], 1 / 13)

    def test_insufficient_cap_capacity_leaves_only_required_cash(self):
        scores = {f"S{index:02}": 1 for index in range(12)}
        targets = build_targets(scores, dict.fromkeys(scores, 1))
        self.assertEqual(set(targets.values()), {0.08})
        self.assertAlmostEqual(1 - math.fsum(targets.values()), 0.04)
        self.assertEqual(build_targets({"A": 0, "B": -1, "C": None}, {}), {})

    def test_missing_cap_below_selection_cutoff_still_blocks_result(self):
        for bad in (None, -1, 0, float("nan"), float("inf"), True):
            with self.subTest(bad=bad), self.assertRaises(SignalDataError):
                build_targets({"A": 2, "B": 1}, {"A": 1, "B": bad}, count=1)

    def test_invalid_target_configuration_scores_and_overflow_raise(self):
        for arguments in ({"count": 0}, {"count": True}, {"count": 1.5}, {"cap": 0}, {"cap": 1.1}, {"cap": float("nan")}):
            with self.subTest(arguments=arguments), self.assertRaises(SignalDataError):
                build_targets({"A": 1}, {"A": 1}, **arguments)
        for scores, caps in (({"A": float("inf")}, {"A": 1}), ({"A": True}, {"A": 1}), ({1: 1}, {1: 1}), ({"A": 1e308}, {"A": 1e308})):
            with self.subTest(scores=scores), self.assertRaises(SignalDataError):
                build_targets(scores, caps)


if __name__ == "__main__":
    unittest.main()
