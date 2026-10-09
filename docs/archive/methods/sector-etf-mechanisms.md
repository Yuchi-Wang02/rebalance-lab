> Archived research document. Historical scope and status are retained; see the [current validation case](../../studies/validation-study.md).

# Selection updates and weight rebalancing in sector momentum

**Status at protocol creation: planned analysis, no B-arm performance calculated.**

This extension retains the preserved sector-ETF inputs and original engine. The history and the A/C results have already been inspected. Fixing this protocol before computing B is a record of analytical choices, not prospective registration or an untouched holdout.

## Question and contribution

How much of the monthly-versus-semiannual difference is associated with restoring portfolio weights, and how much with refreshing the selected target portfolio? The contribution is an inspectable empirical comparison within one explicit model, followed by tests of calendar/cost sensitivity and descriptive market-state dependence. Dynamic trading with costs is established research; this study does not claim a new optimal trading theorem or a first discovery.

## Three policies

| Policy | Target selection | Weight reset |
|---|---|---|
| A | Semiannual | Semiannual |
| B | Semiannual | Monthly |
| C | Monthly | Monthly |

B freezes the entire semiannual target: names, one-third weights, and unused cash slots. An ETF becoming ineligible between refresh dates is not removed. A new positive score does not admit a replacement. Reset to the frozen weights using B's own post-fee NAV, not A's units or wealth. At a refresh/reset coincidence there is one net trade and one fee. Record target-origin, reset-decision and next-session execution dates separately.

Retain the nine funds, common formation, 2000 burn-in, 2001-2025 reporting, 2026 through October 2 as a separate case, signals, score eligibility, tie breaking, fractional adjusted units, zero-interest cash and post-fee equation from the original protocol. A and C numerical payloads must reproduce the saved experiment.

Run both signals, all six semiannual phases and 0/5/10/25 bps. There are 104 strategy accounts and four SPY accounts. The primary setting remains 12-1, March/September and 5 bps. Mixed momentum is prespecified robustness. Reuse C across phases; do not call phases independent replications or promote the best result.

## Outcomes and inference

Display C-A as the headline comparison. B-A measures additional resetting under fixed semiannual target histories. C-B measures additional target updating under monthly resetting, including ranks, eligibility and strategic cash. These are conditional contrasts, not uniquely identified economic causal contributions.

Extract 300 common calendar-month returns from close NAVs, including the correct month-start overnight movement. For each account, `g_t = log(NAV_t / NAV_(t-1))`. The three paired growth differences telescope each month and over time. Report `12 * mean(d)` alongside CAGR differences, terminal wealth ratios, drawdown, volatility, two-sided traded NAV and cash. Drawdown and volatility do not have an additive mechanism attribution.

For the three primary contrasts use intercept OLS with Bartlett HAC(12), small-sample correction and asymptotic normal two-sided inference. Show individual 95% intervals, raw and Holm-adjusted p-values for the fixed family of three. These are not simultaneous confidence intervals. Joint stationary bootstrap: 10,000 samples of the same A/B/C rows, seed 20261009, geometric blocks with mean 12; means 6/24 are appendix checks. Recompute growth and CAGR differences; do not independently resample accounts or rerun selection on resampled price history. Stationarity and design-selection limitations remain.

## States and historical cases

States are measured at the preceding month-end: SPY 252-to-21-session return >0 versus <=0; trailing 63 daily simple-return sample SD times sqrt(252) >20% versus <=20%. No full-sample quantiles, threshold search, crossed state grid or state-driven policy. Estimate each state effect on the full monthly timeline using indicator regressions and full HAC covariance. Do not compress nonadjacent state months. Show counts and intervals without additional significance claims; fewer than 24 months is sparse.

Keep whole-year windows 2001-2002, 2007-2009, 2020 and 2022. Measure from the preceding year-end close through the last window close, without reinitializing accounts. Show cumulative return, daily drawdown, traded NAV and paired log growth. Known retrospective cases do not identify the independent effect of pandemic, inflation or policy changes. Cite event context separately from portfolio findings.

## Exposure and trading diagnostics

Use official French monthly FF3 plus Momentum, frozen by retrieval date and SHA-256. Join exactly 2001-01 through 2025-12; percentage inputs become decimals. Regress primary account simple returns less RF on four factors with HAC(12); regress paired simple-return differences without deducting RF again. Report alpha in bp/month, factor betas and individual intervals, without stars or alpha ranking. Coefficients of paired regressions must match differences of account coefficients; standard errors must not be subtracted. Current revised factor history is not a historical real-time vintage. Cash still earns zero in the portfolio ledger.

Classify executed notional/fees into entries, exits and retained-position resizing. This exact order classification is not a return attribution. Distinguish scheduled resets, materially nonzero trade events (relative tolerance 1e-12 NAV) and order count. Cost scenarios are independent accounts; their terminal effect includes changes to downstream wealth.

## Verification and public evidence

Preserve legacy config/code/output; new experiment namespace and immutable manifests. Verify all A/C daily states and metrics against saved paths. Independently replay B's frozen-target state machine and analytic fee equation without calling production B. Test cash slots, negative eligibility between refreshes, one next-open trade per reset, future-price invariance and self-financing.

Publish only derived portfolio data, figures, methods, provenance and bounded verification. Keep source bars and private ledgers local. The source snapshot actually covers 1998-12-22 onward; this supports the ETF window. It does not establish long-history stock inputs through the separate Sharadar route.

## Sources

- [Gârleanu and Pedersen, Dynamic Trading with Predictable Returns and Transaction Costs](https://docs.lhpedersen.com/DynamicTrading.pdf).
- [Newey and West, HAC covariance](https://www.nber.org/papers/t0055).
- [Politis and Romano, The Stationary Bootstrap](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870).
- [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
