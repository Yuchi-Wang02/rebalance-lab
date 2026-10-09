# Method protocol

## Data and timing

Nine original sector ETFs: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV and XLY; SPY is context. Preserved Yahoo chart responses cover their common sessions from 22 December 1998 through 2 October 2026. Signals and accounts start at the 31 December 1999 close; first execution is 3 January 2000. The primary anchor is 29 December 2000, the last common session of 2000, and the primary endpoint is 31 December 2025. No liquidation or capital reset occurs at reporting boundaries.

The signal for lookback L is `(P[t-21] / P[t-L] - 1) / (sample_sd(daily_returns_in_that_window) * sqrt(252))`. The primary recipe uses L=252. At t=1000, its prices are P[748] and P[979], and its volatility contains 231 simple daily returns r[749] through r[979], where r[k]=P[k]/P[k-1]-1. The most recent 21 returns r[980] through r[1000] enter neither numerator nor denominator. The mixed recipe weights the 252/126/63-session components 0.5/0.3/0.2. Scores must be positive; select up to three ranked ETFs. Each selected name receives one-third of post-fee NAV; unused slots stay as zero-interest cash.

Month-end closing decisions execute at the next exchange-session opening proxy. A monthly portfolio refreshes selection and weights monthly; each semiannual portfolio refreshes in its two designated signal months. Six phases cover Jan/Jul through Jun/Dec, with March/September retained as reference. Costs are 0/5/10/25 bps per side, each a separate self-financing account. Execution solves post-fee targets together with fees. Vendor adjusted closes and `Open * AdjClose / Close` are proxy units; no separate dividend cash is added.

## Six-sleeve tranche

For each signal and cost, six semiannual accounts each represent one-sixth of initial capital. Pooled NAV, cash, asset units, gross traded notional and fees are their scaled sums. The 2000 burn-in can create unequal sleeve capital before reporting starts; equalizing at the reporting anchor would change this protocol. No subsequent sleeve transfers or order netting are allowed. Pooled turnover on a trade date divides summed gross notional by pooled opening pretrade NAV, including non-trading sleeves marked at that opening.

## Inference and risk

Use exactly 300 aligned calendar-month net simple returns for 2001-2025. Primary differences are monthly minus March/September and monthly minus tranche, under 12-1 and 5 bps. Paired stationary bootstrap samples common monthly rows, with a geometric restart probability of 1/block_length and circular continuation. Seed 20261009; 10,000 draws; mean block lengths 12 (primary), 6 and 24. Calculate each sampled CAGR as `exp(12 * mean(log(1+r))) - 1`, then take percentile bounds of the paired CAGR differences. The calculation samples return paths, not prices or selection histories. No primary p-value claims or equivalence test are made.

Sharpe is `sqrt(12) * mean(R - RF) / sample_sd(R - RF)`. Tracking error is `sqrt(12) * sample_sd(R - R_SPY)`. Beta includes an intercept and regresses R-RF on R_SPY-RF. RF is the decimal monthly series from the captured Kenneth French factor archive; a revised historical series is not a point-in-time vintage. Daily volatility and maximum drawdown remain separate. Undefined zero-variance ratios are unavailable, never silently set to zero.

## Mechanism appendix

The already computed A/B/C extension is retained. A=semiannual selection/reset; B=semiannual selection/monthly reset with the complete target vector and cash slots frozen; C=monthly selection/reset. Same input and costs, one next-open fill at coinciding events. Conditional differences B-A and C-B telescope in log growth but do not identify unique causal mechanisms. Mean monthly log differences use Bartlett HAC12 with small-sample correction, normal intervals and Holm correction for three contrasts. Stationary bootstrap sensitivity remains attached to the appendix results.

## Registration and interpretation

The original history and calendar results were already inspected. The validation extension's rules were recorded and hashed before its tranche and interval calculation; this is retrospective freezing, not prospective registration or an untouched holdout. Freeze records and previous manifests remain preserved. No observed winning phase is promoted. Market-state, event, adaptive-rule and multi-factor studies are deferred.

[Machine-readable extension protocol](../../configs/sector-etf-validation.v1.json) · [Freeze record](../validation/etf-validation-protocol-freeze.json) · [Legacy ETF rules](../../configs/sector-etf-pilot.v1.json) · [Mechanism rules](../../configs/sector-etf-mechanisms.v1.json)
