# Validation memo

**Object:** Nine-sector-ETF momentum rebalancing, 2001-2025. **Date:** 9 October 2026. **Purpose:** assess a frequency claim and the reliability of its retrospective evidence. **Judgment:** calculation reconciled; general frequency superiority unsupported; remaining model and data risks disclosed.

## Scope

Compare monthly selection/reweighting with six semiannual calendars, four costs and two signals. Add six autonomous sleeves as a calendar-diversified comparison. The main study is 12-1 at 5 bps per side; 2026 YTD and A/B/C mechanisms are secondary. This is a financial research case, not a bank-approved model, live strategy or trading recommendation.

## Data lineage

Preserved vendor responses -> common-session adjusted open/close input -> fixed portfolio accounts -> independent accounting replay -> tranche sums -> monthly risk and paired intervals -> public derived CSVs and summary. Every capture, protocol and generated account has a SHA-256 manifest. Official French monthly RF is captured separately and joined to exactly 300 months. Hashes establish file identity, not independent authenticity of vendor observations.

## Independent implementation checks

The legacy verifier uses standard-library code and an analytic fee solution rather than the engine's bisection. It reconciles 60 paths. The mechanism verifier reconciles 108 paths and 726,732 daily states; maximum relative NAV error is 1.78e-14. A separate extension verifier imports no project calculation code and checks eight tranches, 53,832 daily states and 34,800 monthly rows, including Sharpe, tracking error, beta and bootstrap percentiles. Maximum relative tranche NAV error is 2.22e-16.

**Independence boundary:** the same AI agent authored the implementations and reviewed the outputs. Different calculations can expose implementation errors; they cannot exclude a shared misunderstanding of the specification. No external reviewer acceptance is claimed.

## Findings

- At 5 bps, changing only the semiannual calendar changes the 12-1 comparison's sign: -0.92 to +0.53 pp/year.
- Monthly minus March/September is -0.49 pp/year; paired 95% CI [-3.03, +2.11]. Monthly minus tranche is -0.22; CI [-2.44, +2.33]. Both span zero.
- Tranche CAGR is 8.24%, but its daily maximum drawdown is -40.91%; calendar pooling does not guarantee lower risk.

## Limitations and residual risk

Historical results were inspected before this extension was specified. Adjusted units approximate total return and next-open execution, rather than a raw-share corporate-action ledger. Cash earns zero; costs are fixed and there is no spread, impact, capacity or tax model. ETF sector definitions changed. Bootstrap stationarity and block choice do not remove regime or design-selection risk. Source-price accuracy and real execution remain unverified. Written result and judgment reviews have been accepted; exact signal-window understanding and an observed oral presentation remain pending. Owner mastery is not certified.

## Disposition

Accept as a reproducible, bounded historical validation case. Do not use it to select an optimal schedule, assert causal timing attribution, certify executable returns or establish personal technical mastery. Publish all tested comparisons and keep computation completion, owner readiness and deployment status separate.

[Result summary](../../site/data/validation-study-summary.json) · [Extension receipt](../../site/data/validation-study-replay.json) · [Reproduction](../reproduction.md)
