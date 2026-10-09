"""Numerical and timing checks against independently evaluated formulas."""
import io
import json
from pathlib import Path
import unittest
import zipfile

try:
    import numpy as np
    from pilot.mechanism_analysis import paired_inference, state_diagnostics, factor_diagnostics, bootstrap_intervals
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

from scripts.acquire_french_factors import parse_zip


@unittest.skipUnless(AVAILABLE, "install requirements-analysis.txt for statistical checks")
class AnalysisTests(unittest.TestCase):
    def test_hac_mean_against_manual_bartlett_covariance(self):
        rng = np.random.default_rng(81)
        innovation = rng.normal(0, 0.004, 300)
        d = np.empty(300); d[0] = innovation[0]
        for i in range(1, 300): d[i] = 0.5 * d[i - 1] + innovation[i]
        d += 0.0003
        # A has zero log growth; B half of the known spread; C all of it.
        simple = np.expm1(np.column_stack([np.zeros(300), d / 2, d]))
        result = paired_inference(simple)[0]
        u = d - d.mean()
        meat = float(u @ u)
        for lag in range(1, 13): meat += 2 * (1 - lag / 13) * float(u[lag:] @ u[:-lag])
        variance = 300 / 299 * meat / (300 ** 2)
        self.assertAlmostEqual(result["annualized_log_growth_difference_pp"], 1200 * d.mean(), places=11)
        self.assertAlmostEqual(result["hac_standard_error_annualized_pp"], 1200 * np.sqrt(variance), places=11)
        p = [r["raw_p_value"] for r in paired_inference(simple)]
        order = np.argsort(p); expected = np.empty(3); running = 0
        for rank, j in enumerate(order):
            running = max(running, (3 - rank) * p[j]); expected[j] = min(1, running)
        np.testing.assert_allclose([r["holm_p_value"] for r in paired_inference(simple)], expected)

    def test_paired_bootstrap_preserves_identical_accounts(self):
        rng = np.random.default_rng(9)
        r = rng.normal(0.003, 0.02, 300)
        values = np.column_stack([r, r, r])
        rows = bootstrap_intervals(values, 200, 12, 20261009)
        for row in rows:
            np.testing.assert_allclose(row["growth95_annualized_log_pp"], [0, 0], atol=1e-12)
            np.testing.assert_allclose(row["cagr95_difference_pp"], [0, 0], atol=1e-12)
        self.assertEqual(rows, bootstrap_intervals(values, 200, 12, 20261009))

    def test_state_covariance_retains_calendar_gaps(self):
        rng = np.random.default_rng(7)
        labels = (np.arange(300) % 9 < 3).astype(int)
        spread = 0.001 + 0.002 * labels + rng.normal(0, 0.005, 300)
        values = np.expm1(np.column_stack([np.zeros(300), spread / 2, spread]))
        rows = state_diagnostics(values, {"volatility": labels})
        x = np.column_stack([np.ones(300), labels]); inv = np.linalg.inv(x.T @ x)
        beta = inv @ x.T @ spread; residual = spread - x @ beta; scores = x * residual[:, None]
        meat = scores.T @ scores
        for lag in range(1, 13):
            cross = scores[lag:].T @ scores[:-lag]
            meat += (1 - lag / 13) * (cross + cross.T)
        cov = 300 / 298 * inv @ meat @ inv
        for state in (0, 1):
            row = next(r for r in rows if r["contrast"] == "C-A" and r["state"] == state)
            vector = np.array([1, state]); mean = vector @ beta; se = np.sqrt(vector @ cov @ vector)
            self.assertEqual(row["full_timeline_months"], 300)
            self.assertEqual(row["months"], int((labels == state).sum()))
            self.assertAlmostEqual(row["annualized_log_growth_difference_pp"], 1200 * mean, places=10)
            self.assertAlmostEqual(row["hac95_annualized_log_pp"][1], 1200 * (mean + 1.959963984540054 * se), places=9)

    def test_factor_spread_does_not_subtract_RF_again(self):
        rng = np.random.default_rng(62)
        factors = rng.normal(0, 0.03, (300, 4)); rf = np.full(300, 0.002)
        coefficients = np.array([[0.7, 0.1, 0.2, -0.1], [0.8, 0.2, 0.1, 0.1], [0.9, -0.1, 0.3, 0.2]])
        alpha = np.array([0.0002, 0.0004, 0.0006])
        values = rf[:, None] + alpha + factors @ coefficients.T
        rows = factor_diagnostics(values, factors, rf)["regressions"]
        spread = next(r for r in rows if r["label"] == "C-A")
        self.assertAlmostEqual(spread["alpha_bp_per_month"], 4.0, places=10)
        for k, name in enumerate(("Mkt-RF", "SMB", "HML", "Mom")):
            self.assertAlmostEqual(spread["coefficients"][name]["estimate"], coefficients[2, k] - coefficients[0, k], places=10)

    def test_state_uses_only_preceding_month_end(self):
        from scripts.analyze_etf_mechanisms import monthly_states
        protocol = json.loads((Path(__file__).resolve().parents[1] / "configs/sector-etf-mechanisms.v1.json").read_text())
        dates = [f"2000-{i:03d}" for i in range(400)]
        prices = [100 * np.exp(0.001 * i) for i in range(400)]
        data = {"sessions": dates, "adjusted_close": {"SPY": prices}}
        # Labels are opaque here; indices, not string date arithmetic, govern timing.
        first = monthly_states(data, [dates[350]], dates[300], protocol)
        for i in range(301, 400): prices[i] *= 5
        second = monthly_states(data, [dates[350]], dates[300], protocol)
        self.assertEqual(first, second)


class FactorParsingTests(unittest.TestCase):
    def body(self, duplicate=False):
        rows = [",Mkt-RF,SMB,HML,RF"]
        rows += [f"{year}{month:02d},1,2,3,0.1" for year in range(2001, 2026) for month in range(1, 13)]
        if duplicate: rows.append(rows[-1])
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as z: z.writestr("factors.csv", "\n".join(rows))
        return content.getvalue()

    def test_units_and_exact_months(self):
        rows = parse_zip(self.body(), ["Mkt-RF", "SMB", "HML", "RF"])
        self.assertEqual(len(rows), 300)
        self.assertEqual(rows["2001-01"]["Mkt-RF"], 0.01)
        self.assertEqual(rows["2025-12"]["RF"], 0.001)

    def test_duplicates_block(self):
        with self.assertRaises(ValueError): parse_zip(self.body(True), ["Mkt-RF", "SMB", "HML", "RF"])


if __name__ == "__main__": unittest.main()
