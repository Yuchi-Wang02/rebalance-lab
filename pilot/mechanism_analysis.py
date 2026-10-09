"""Prespecified paired inference and diagnostics; no strategy optimization."""
import math
import numpy as np
import statsmodels.api as sm
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

CONTRAST_INDICES = (("C-A", 2, 0), ("B-A", 1, 0), ("C-B", 2, 1))


def hac_fit(y, x, lags=12):
    y, x = np.asarray(y, dtype=float), np.asarray(x, dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x).all() or len(y) != len(x):
        raise ValueError("nonfinite or mismatched regression input")
    if np.linalg.matrix_rank(x) != x.shape[1]:
        raise ValueError("rank-deficient diagnostic regression")
    return sm.OLS(y, x).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": True}, use_t=False)


def paired_inference(simple_returns, lags=12):
    values = np.asarray(simple_returns, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or len(values) < lags + 2 or not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError("A/B/C require valid aligned simple returns")
    logs = np.log1p(values)
    rows = []
    for name, high, low in CONTRAST_INDICES:
        d = logs[:, high] - logs[:, low]
        fit = hac_fit(d, np.ones((len(d), 1)), lags)
        mean, se = float(fit.params[0]), float(fit.bse[0])
        p = float(2 * norm.sf(abs(mean / se))) if se > 1e-16 else (1.0 if abs(mean) <= 1e-16 else 0.0)
        ci = [mean - norm.ppf(0.975) * se, mean + norm.ppf(0.975) * se]
        cagr = np.expm1(12 * logs.mean(axis=0))
        rows.append({"contrast": name, "months": len(d), "annualized_log_growth_difference_pp": mean * 1200,
                     "hac_standard_error_annualized_pp": se * 1200, "hac95_annualized_log_pp": [v * 1200 for v in ci],
                     "raw_p_value": p, "cagr_difference_pp": float(100 * (cagr[high] - cagr[low]))})
    adjusted = multipletests([r["raw_p_value"] for r in rows], alpha=0.05, method="holm")[1]
    for row, p in zip(rows, adjusted):
        row["holm_p_value"] = float(p)
    return rows


def stationary_indices(months, repetitions, mean_block, seed):
    if months < 2 or repetitions < 1 or mean_block < 1:
        raise ValueError("invalid stationary bootstrap dimensions")
    rng = np.random.default_rng(np.random.SeedSequence([seed, mean_block]))
    indices = np.empty((repetitions, months), dtype=np.int32)
    indices[:, 0] = rng.integers(0, months, size=repetitions)
    for t in range(1, months):
        restart = rng.random(repetitions) < 1 / mean_block
        starts = rng.integers(0, months, size=repetitions)
        indices[:, t] = np.where(restart, starts, (indices[:, t - 1] + 1) % months)
    return indices


def bootstrap_intervals(simple_returns, repetitions, mean_block, seed):
    values = np.asarray(simple_returns, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError("invalid paired bootstrap returns")
    logs = np.log1p(values)
    indices = stationary_indices(len(values), repetitions, mean_block, seed)
    sampled_means = logs[indices].mean(axis=1)
    sampled_cagrs = np.expm1(12 * sampled_means)
    rows = []
    for name, high, low in CONTRAST_INDICES:
        growth = 1200 * (sampled_means[:, high] - sampled_means[:, low])
        cagr = 100 * (sampled_cagrs[:, high] - sampled_cagrs[:, low])
        rows.append({"contrast": name, "mean_block_months": mean_block, "repetitions": repetitions,
                     "seed": seed, "rng": "numpy_default_rng_SeedSequence_seed_and_block_length",
                     "growth95_annualized_log_pp": [float(v) for v in np.quantile(growth, [0.025, 0.975])],
                     "cagr95_difference_pp": [float(v) for v in np.quantile(cagr, [0.025, 0.975])]})
    return rows


def state_diagnostics(simple_returns, states, lags=12, minimum=24):
    logs = np.log1p(np.asarray(simple_returns, dtype=float))
    rows = []
    for dimension, labels in states.items():
        labels = np.asarray(labels, dtype=int)
        if len(labels) != len(logs) or set(labels) != {0, 1}:
            raise ValueError("state requires two groups on the full monthly timeline")
        x = np.column_stack([np.ones(len(labels)), labels])
        for name, high, low in CONTRAST_INDICES:
            fit = hac_fit(logs[:, high] - logs[:, low], x, lags)
            for state in (0, 1):
                vector = np.array([1.0, float(state)])
                estimate = float(vector @ fit.params)
                variance = float(vector @ fit.cov_params() @ vector)
                se = math.sqrt(max(0, variance))
                count = int((labels == state).sum())
                rows.append({"dimension": dimension, "state": state, "contrast": name, "months": count,
                             "full_timeline_months": len(labels), "sparse": count < minimum,
                             "annualized_log_growth_difference_pp": estimate * 1200,
                             "hac95_annualized_log_pp": [(estimate - norm.ppf(0.975) * se) * 1200,
                                                         (estimate + norm.ppf(0.975) * se) * 1200]})
    return rows


def factor_diagnostics(simple_returns, factor_matrix, rf, lags=12):
    values, factors, rf = np.asarray(simple_returns, dtype=float), np.asarray(factor_matrix, dtype=float), np.asarray(rf, dtype=float)
    if factors.shape != (len(values), 4) or rf.shape != (len(values),):
        raise ValueError("factor inputs must align exactly with strategy months")
    x = np.column_stack([np.ones(len(values)), factors])
    rows, account_coefficients = [], {}
    for j, policy in enumerate(("A", "B", "C")):
        fit = hac_fit(values[:, j] - rf, x, lags)
        account_coefficients[policy] = fit.params
        rows.append(factor_row(policy, fit))
    maximum_error = 0.0
    for name, high, low in CONTRAST_INDICES:
        fit = hac_fit(values[:, high] - values[:, low], x, lags)
        expected = account_coefficients[("A", "B", "C")[high]] - account_coefficients[("A", "B", "C")[low]]
        maximum_error = max(maximum_error, float(np.max(np.abs(fit.params - expected))))
        rows.append(factor_row(name, fit))
    if maximum_error > 1e-10:
        raise ValueError("factor contrast coefficients do not reconcile")
    return {"regressions": rows, "max_coefficient_difference_error": maximum_error}


def factor_row(label, fit):
    names = ["alpha", "Mkt-RF", "SMB", "HML", "Mom"]
    bounds = fit.conf_int(alpha=0.05)
    return {"label": label, "months": int(fit.nobs), "r_squared": float(fit.rsquared),
            "alpha_bp_per_month": float(fit.params[0] * 10000),
            "alpha95_bp_per_month": [float(v * 10000) for v in bounds[0]],
            "coefficients": {name: {"estimate": float(value), "hac95": [float(v) for v in ci]}
                             for name, value, ci in zip(names, fit.params, bounds)}}
