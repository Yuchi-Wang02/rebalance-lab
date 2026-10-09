"""Behavioral tests for the frozen-target policy, not performance promises."""
import copy
import math
from pathlib import Path
import json
import unittest

from pilot.engine import run_matrix
from pilot.rebalance_mechanisms import run_frozen_target, run_policy_matrix
from test_etf_pilot import fixture

ROOT = Path(__file__).resolve().parents[1]


class MechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.config = fixture()
        cls.protocol = json.loads((ROOT / "configs/sector-etf-mechanisms.v1.json").read_text())
        cls.matrix = run_policy_matrix(cls.data, cls.config, cls.protocol)

    def primary_b(self):
        return next(r for r in self.matrix["runs"] if r["run_id"] == "B12-03-09-5bps")

    def test_matrix_and_legacy_payload_preserved(self):
        self.assertEqual(len(self.matrix["runs"]), 104)
        self.assertEqual(len(self.matrix["comparisons"]["full_period"]), 144)
        self.assertTrue(all(self.matrix["checks"].values()))
        for old in self.matrix["legacy_result"]["runs"]:
            new = next(r for r in self.matrix["runs"] if r["run_id"] == old["run_id"])
            self.assertEqual(new["daily"], old["daily"])
            for period in ("full_period", "ytd2026"):
                for key, value in old["metrics"][period].items():
                    self.assertEqual(new["metrics"][period][key], value)

    def test_one_fill_and_target_origin(self):
        b = self.primary_b()
        for decision, trade in zip(b["signals"], b["trades"]):
            self.assertEqual(trade["decision_session"], decision["decision_session"])
            self.assertEqual(trade["target_origin_session"], decision["target_origin_session"])
            self.assertEqual(self.data["sessions"].index(trade["session"]), self.data["sessions"].index(decision["decision_session"]) + 1)
        self.assertEqual(len({t["session"] for t in b["trades"]}), len(b["trades"]))

    def test_partial_cash_and_full_cash_targets_stay_frozen(self):
        reference = copy.deepcopy(next(r for r in self.matrix["legacy_result"]["runs"] if r["run_id"] == "S12-03-09-5bps"))
        for i, decision in enumerate(reference["signals"]):
            decision["selected"] = ["A", "B"] if i % 2 == 0 else []
        b = run_frozen_target(self.data, self.config, reference)
        target_by_origin = {d["decision_session"]: d["selected"] for d in reference["signals"]}
        for d in b["signals"]:
            expected = target_by_origin[d["target_origin_session"]]
            self.assertEqual(d["selected"], expected)
            self.assertAlmostEqual(d["cash_target_weight"], 1 - len(expected) / 3)
            self.assertEqual(d["target_weights"], {s: 1 / 3 for s in expected})
        self.assertTrue(any(not d["selected"] and not d["target_refreshed"] for d in b["signals"]))

    def test_new_price_ranking_does_not_change_frozen_target(self):
        reference = copy.deepcopy(next(r for r in self.matrix["legacy_result"]["runs"] if r["run_id"] == "S12-03-09-5bps"))
        for d in reference["signals"]:
            d["selected"] = ["A"]
        changed = copy.deepcopy(self.data)
        changed["adjusted_close"]["A"] = [100 * math.exp(-0.005 * i) for i in range(len(self.data["sessions"]))]
        changed["adjusted_close"]["C"] = [100 * math.exp(0.005 * i) for i in range(len(self.data["sessions"]))]
        b = run_frozen_target(changed, self.config, reference)
        self.assertTrue(all(d["selected"] == ["A"] for d in b["signals"]))

    def test_future_prices_cannot_change_past_states(self):
        old = self.primary_b()
        cutoff = "2025-06-30"
        changed = copy.deepcopy(self.data)
        for field in ("adjusted_open", "adjusted_close"):
            for symbol in changed[field]:
                for i, session in enumerate(changed["sessions"]):
                    if session > cutoff:
                        changed[field][symbol][i] *= 1.8
        reference = next(r for r in self.matrix["legacy_result"]["runs"] if r["run_id"] == "S12-03-09-5bps")
        new = run_frozen_target(changed, self.config, reference)
        self.assertEqual([d for d in old["daily"] if d["session"] <= cutoff], [d for d in new["daily"] if d["session"] <= cutoff])

    def test_growth_telescope_and_fee_partition(self):
        rows = self.matrix["comparisons"]["full_period"]
        for signal in ("12-1", "mixed"):
            group = {r["contrast"]: r for r in rows if r["signal"] == signal and r["phase"] == [3, 9] and r["cost_bps_per_side"] == 5}
            self.assertAlmostEqual(group["C-A"]["log_growth_difference"], group["B-A"]["log_growth_difference"] + group["C-B"]["log_growth_difference"])
        for r in self.matrix["runs"]:
            for t in r["trades"]:
                self.assertAlmostEqual(sum(t["fee_by_category"].values()), t["cost"])
                self.assertAlmostEqual(sum(t["notional_by_category"].values()), t["traded_notional"])


if __name__ == "__main__":
    unittest.main()
