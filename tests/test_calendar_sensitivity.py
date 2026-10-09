"""Fixed calendar-phase robustness cannot become an implicit parameter search."""

from collections import Counter
from copy import deepcopy
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.run_calendar_sensitivity import engineering_checks, public_receipt
from spmo_lab.simulation import (
    CALENDAR_PHASES, NY, PRIMARY_CONFIG_SHA256, Session, SimulationError,
    run_arm, run_calendar_matrix, selection_due, validate_calendar_sensitivity,
)
from spmo_lab.synthetic import make_fixture

ROOT = Path(__file__).resolve().parents[1]


def configs():
    primary_bytes = (ROOT / "configs/experiment.v1.json").read_bytes()
    primary = json.loads(primary_bytes)
    sensitivity = json.loads((ROOT / "configs/calendar-sensitivity.v1.json").read_text())
    return primary, sensitivity, hashlib.sha256(primary_bytes).hexdigest()


def session(day):
    parsed = date.fromisoformat(day)
    return Session(day, datetime.combine(parsed, time(9, 30), NY),
                   datetime.combine(parsed, time(16), NY))


def fake_run(data, config, strategy, cost, *, experiment_track, calendar_phase=None):
    """Distinct controlled outputs test composition, not the trading implementation."""
    fast = config["arms"][strategy]["rebalance"] == "monthly"
    adjustment = 0 if fast else calendar_phase[0] / 100
    return {
        "data_track": "synthetic", "experiment_track": experiment_track,
        "strategy_id": strategy, "cost_bps": cost,
        "calendar_phase": None if fast else list(calendar_phase),
        "daily": [{"session": "2024-12-31", "nav": 1_000_000, "cash": 1_000_000},
                  {"session": "2026-10-02", "nav": 1_000_000, "cash": 0}],
        "trades": [{"session": "2025-01-02", "decision_session": "2024-12-31",
                    "reason": "scheduled_rebalance", "cost": cost, "notional": 10_000}],
        "signals": [{"decision_session": "2024-12-31"}],
        "snapshots": {"2025-12-31": {}, "2026-10-02": {}},
        "metrics": {"net_total_return": 0.2 - adjustment, "maximum_drawdown": -0.1 - adjustment,
                    "two_sided_turnover": 3 - adjustment, "reporting_cost": 0},
    }


class FixedSpecificationTests(unittest.TestCase):
    def test_supplement_matches_complete_unchanged_primary_file(self):
        primary, sensitivity, digest = configs()
        self.assertEqual(digest, PRIMARY_CONFIG_SHA256)
        validate_calendar_sensitivity(primary, sensitivity, digest)

    def test_different_hash_or_primary_period_is_rejected(self):
        primary, sensitivity, digest = configs()
        with self.assertRaisesRegex(SimulationError, "unchanged primary"):
            validate_calendar_sensitivity(primary, sensitivity, "0" * 64)
        primary["period"]["report_end_close"] = "2026-10-01"
        with self.assertRaisesRegex(SimulationError, "unchanged primary"):
            validate_calendar_sensitivity(primary, sensitivity, digest)

    def test_omitted_phase_changed_cost_winner_selection_and_unknown_fields_rejected(self):
        primary, sensitivity, digest = configs()
        changes = [
            {"phase_pairs": [[3, 9]]}, {"phase_pairs": list(reversed(sensitivity["phase_pairs"]))},
            {"cost_bps_per_side_scenarios": [0, 5]}, {"promote_best_phase": True},
            {"unique_run_count": 56.0}, {"unknown_field": "ignored?"},
            {"report_all_phases": 1}, {"primary_reference_phase": [1, 7]},
        ]
        for changeset in changes:
            amended = {**deepcopy(sensitivity), **changeset}
            with self.subTest(changes=changeset), self.assertRaisesRegex(SimulationError, "fixed six-phase"):
                validate_calendar_sensitivity(primary, amended, digest)

    def test_all_six_schedules_are_six_months_apart_and_primary_is_march_september(self):
        sessions = []
        for month in range(1, 13):
            # Fictional two-session months make month boundaries explicit.
            sessions.extend([session(f"2025-{month:02d}-01"), session(f"2025-{month:02d}-28")])
        sessions.append(session("2026-01-02"))
        self.assertEqual(CALENDAR_PHASES[2], (3, 9))
        for pair in CALENDAR_PHASES:
            selected = [item.day for index, item in enumerate(sessions)
                        if selection_due(sessions, index, "semiannual", pair)]
            with self.subTest(pair=pair):
                self.assertEqual([int(day[5:7]) for day in selected], list(pair))
                self.assertTrue(all(day.endswith("-28") for day in selected))


class MatrixCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.primary, cls.sensitivity, cls.digest = configs()
        with patch("spmo_lab.simulation.run_arm", side_effect=fake_run) as runner:
            cls.matrix = run_calendar_matrix(object(), cls.primary, cls.sensitivity,
                                             primary_config_sha256=cls.digest)
        cls.calls = runner.call_args_list

    def test_monthly_controls_reused_eight_times_and_slow_runs_distinct(self):
        self.assertEqual(len(self.calls), 56)
        self.assertEqual(len(self.matrix["monthly_controls"]), 8)
        self.assertEqual(len(self.matrix["phase_runs"]), 48)
        monthly_calls = [call for call in self.calls if call.args[2] in ("M12", "MMIX")]
        self.assertEqual(len(monthly_calls), 8)
        self.assertTrue(all("calendar_phase" not in call.kwargs for call in monthly_calls))
        ids = [result["strategy_run_id"] for result in self.matrix["monthly_controls"] + self.matrix["phase_runs"]]
        self.assertEqual(len(set(ids)), 56)

    def test_only_calendar_argument_changes_and_primary_config_is_not_mutated(self):
        original, _, _ = configs()
        self.assertEqual(self.primary, original)
        for call in self.calls:
            self.assertIs(call.args[1], self.primary)
            self.assertEqual(call.kwargs["experiment_track"], "calendar_phase_sensitivity")
            self.assertLessEqual(set(call.kwargs), {"experiment_track", "calendar_phase"})
            if call.args[2] in ("S12", "SMIX"):
                self.assertIn(tuple(call.kwargs["calendar_phase"]), CALENDAR_PHASES)

    def test_all_48_contrasts_reference_shared_controls_with_correct_differences(self):
        table = self.matrix["phase_table"]
        self.assertEqual(len(table), 48)
        counts = Counter(row["monthly_control_id"] for row in table)
        self.assertEqual(len(counts), 8)
        self.assertEqual(set(counts.values()), {6})
        self.assertEqual(sum(row["is_primary_reference_phase"] for row in table), 8)
        for row in table:
            self.assertAlmostEqual(row["net_return_difference_percentage_points"], row["calendar_phase"][0])
            self.assertAlmostEqual(row["drawdown_difference_percentage_points"], row["calendar_phase"][0])
            self.assertAlmostEqual(row["extra_two_sided_turnover"], row["calendar_phase"][0] / 100)

    def test_engineering_receipt_rejects_missing_contrasts_and_duplicate_controls(self):
        self.assertTrue(all(engineering_checks(self.matrix, self.primary, self.sensitivity).values()))
        truncated = deepcopy(self.matrix)
        truncated["phase_table"].pop()
        with self.assertRaisesRegex(ValueError, "48_paired_contrasts"):
            engineering_checks(truncated, self.primary, self.sensitivity)
        repeated = deepcopy(self.matrix)
        repeated["monthly_controls"][1] = repeated["monthly_controls"][0]
        with self.assertRaisesRegex(ValueError, "8_reused_monthly_controls"):
            engineering_checks(repeated, self.primary, self.sensitivity)

    def test_public_receipt_whitelist_excludes_synthetic_performance(self):
        keys = ("schema_version", "run_id", "data_track", "experiment_track", "generated_at_utc",
                "fixture_sha256", "primary_config_sha256", "sensitivity_config_sha256", "code_sha256",
                "monthly_control_count", "semiannual_run_count", "unique_run_count", "paired_contrast_count",
                "checks", "market_backtest_executed", "research_ready", "calendar_is_verified_exchange_calendar")
        manifest = dict.fromkeys(keys, "placeholder")
        manifest.update(metrics={"net_total_return": 0.99}, phase_table=self.matrix["phase_table"],
                        daily=[{"nav": 999999}], net_total_return=0.99)
        receipt = public_receipt(manifest, self.sensitivity)
        for field in ("metrics", "phase_table", "daily", "net_total_return"):
            self.assertNotIn(field, receipt)
        self.assertFalse(receipt["promote_best_phase"])
        self.assertTrue(receipt["report_all_phases"])


class SyntheticPhaseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.primary, cls.sensitivity, cls.digest = configs()
        cls.data = make_fixture(cls.primary, security_count=8)
        cls.primary_results, cls.supplementary_results = {}, {}
        for strategy in ("S12", "SMIX", "M12"):
            cls.primary_results[strategy] = run_arm(cls.data, cls.primary, strategy, 5)
            kwargs = {"experiment_track": "calendar_phase_sensitivity"}
            if strategy in ("S12", "SMIX"):
                kwargs["calendar_phase"] = (3, 9)
            cls.supplementary_results[strategy] = run_arm(cls.data, cls.primary, strategy, 5, **kwargs)
        cls.january = run_arm(cls.data, cls.primary, "S12", 5,
                              experiment_track="calendar_phase_sensitivity", calendar_phase=(1, 7))

    def test_march_september_matches_primary_output_exactly_except_track(self):
        for strategy in ("S12", "SMIX", "M12"):
            primary = deepcopy(self.primary_results[strategy])
            supplementary = deepcopy(self.supplementary_results[strategy])
            self.assertEqual(primary.pop("experiment_track"), "primary")
            self.assertEqual(supplementary.pop("experiment_track"), "calendar_phase_sensitivity")
            with self.subTest(strategy=strategy):
                self.assertEqual(primary, supplementary)

    def test_january_july_preserves_initialization_and_reporting_boundaries(self):
        result = self.january
        initial = self.primary["period"]["initial_signal_close"]
        index = next(index for index, item in enumerate(self.data.sessions) if item.day == initial)
        self.assertEqual(result["trades"][0]["session"], self.data.sessions[index + 1].day)
        self.assertEqual(result["daily"][0]["nav"], 1_000_000)
        self.assertEqual(result["daily"][0]["cash"], 1_000_000)
        self.assertEqual(set(result["snapshots"]), {"2025-12-31", "2026-10-02"})
        decisions = {record["decision_session"] for record in result["signals"]}
        self.assertEqual({int(day[5:7]) for day in decisions if day != initial}, {1, 7})
        self.assertIn(initial, decisions)
        reporting_cost = sum(trade["cost"] for trade in result["trades"] if trade["session"] > "2025-12-31")
        self.assertAlmostEqual(result["metrics"]["reporting_cost"], reporting_cost)

    def test_phase_override_requires_explicit_track_and_supported_six_month_pair(self):
        attempts = [
            {"calendar_phase": (1, 7)},
            {"experiment_track": "other", "calendar_phase": (1, 7)},
            *({"experiment_track": "calendar_phase_sensitivity", "calendar_phase": pair}
              for pair in ((1, 8), (7, 1), (1, 1), (0, 6), (True, 7), "1,7", None)),
        ]
        for kwargs in attempts:
            with self.subTest(kwargs=kwargs), self.assertRaises(SimulationError):
                run_arm(self.data, self.primary, "S12", 5, **kwargs)
        with self.assertRaisesRegex(SimulationError, "Monthly controls"):
            run_arm(self.data, self.primary, "M12", 5,
                    experiment_track="calendar_phase_sensitivity", calendar_phase=(1, 7))


if __name__ == "__main__":
    unittest.main()
