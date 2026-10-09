> Archived research document. Historical scope and status are retained; see the [current validation case](../../studies/validation-study.md).

# Experiment protocol v0.2

**Status: proposed protocol with a synthetic engine prototype; no completed market backtest.** The purpose is to test faster momentum rotation, not to establish in advance that a faster strategy wins. The [engine guide](../validation/engine.md) describes the fictional-data implementation and its remaining acceptance work. This release supersedes the v0.1 cumulative ablation chain; the previous commit remains in Git history.

## 1. What changed and why

The first design mixed selection frequency, signal horizons, position count, buffering, weighting and trend filters. The revised primary experiment is a four-arm **2 × 2 factorial design**. It separates the frequency effect under two signals and removes optional overlays from the main claim.

A second change fixes the YTD interpretation. Buying everything from cash at the first 2026 open is a legitimate new-account experiment, but it is not the calendar YTD of an already-running strategy. The main protocol now establishes holdings during 2025, then measures their 2026 performance.

## 2. Hypotheses and comparisons

| Arm | Scheduled selection | Momentum signal |
|---|---|---|
| S12 | Last trading close of March and September | 12–1 |
| M12 | Last trading close of every month | 12–1 |
| SMIX | Last trading close of March and September | 50% 12–1 + 30% 6–1 + 20% 3–1 |
| MMIX | Last trading close of every month | Same blend |

All other rules are identical. Initial formation, corporate actions, constituent exits and dividend reinvestment are common maintenance exceptions; semiannual does not mean literally two transactions a year.

- **Primary hypothesis:** monthly selection improves net total return under the 12–1 signal. Estimate `return(M12) − return(S12)` in percentage points.
- **Within-study robustness:** estimate `return(MMIX) − return(SMIX)` under the blended signal. The pairs share securities, market conditions, data and implementation; agreement is not independent replication.
- **Secondary interaction:** `(MMIX − SMIX) − (M12 − S12)`. Describe whether the frequency effect changes with the signal; do not select whichever pair happened to win as a new primary result.
- **Product comparison:** report all four arms beside actual SPMO and SPY. Differences from a real ETF include more than frequency and must not be called frequency alpha.

The null is no improvement after modeled costs. A positive realized spread is descriptive evidence for this window, not proof of statistical significance, long-run superiority or risk-adjusted alpha. No overall pass/fail threshold is invented without an agreed drawdown and turnover tolerance.

## 3. Timeline and initialization

| Milestone | Fixed convention |
|---|---|
| Requested historical start | 2023-12-01, subject to actual exchange-calendar coverage |
| Initial signal | 2024-12-31 close; at least 253 valid price points ending there |
| Initial execution | First exchange session open after the initial signal, from equal cash balances |
| Burn-in | All of 2025, each arm following its own schedule |
| Reporting anchor | 2025-12-31 close; normalize each existing portfolio NAV to 100 without trading |
| Reporting end | 2026-10-02 close; no terminal liquidation |

Publish each arm's actual holdings, receivables and cash at the reporting anchor. Initial formation costs and 2025 maintenance belong to the burn-in ledger and affect the starting state; do not charge them again as 2026 costs. Benchmark portfolios receive the same initialization convention. Only the reporting-period returns and trades enter YTD statistics.

This burn-in reduces the artificial January reset but is not a claim that initialization has no effect. A different initialization date, if investigated, is a separately labeled sensitivity, not a replacement chosen after seeing results.

The 2026 window is **retrospective exploratory research**: its market developments helped motivate the strategy. Correct historical data alignment does not turn it into an untouched holdout. Future testing begins only after a timestamped freeze of the complete implementation and protocol.

## 4. Shared universe and eligibility

Use S&P 500 membership effective at each decision time and available by that time. Preserve permanent security IDs, historical ticker mappings, departed members and delisted securities. Different share classes are distinct securities; report aggregate issuer exposure as well.

An eligible security must have the required common-calendar price history, finite positive market capitalization, and a finite positive combined momentum score. Missing supplier records are a data-quality failure, not an opportunity to silently exclude inconvenient stocks. Genuinely insufficient listing history is a documented eligibility exclusion.

The positive-score rule is an explicit absolute-momentum filter common to all arms. It is not represented as a verified official SPMO rule. Historical membership records alone do not prove historical publication-time availability: preserve effective-time and as-of evidence separately.

## 5. Signal definition

Let `t` denote the signal session on the common exchange calendar. Let `P` be the split-adjusted price series excluding reinvested cash dividends.

| Signal | Price return | Volatility sample |
|---|---|---|
| 12–1 | `P[t−21] / P[t−252] − 1` | 231 daily simple returns ending at `t−21` |
| 6–1 | `P[t−21] / P[t−126] − 1` | 105 daily simple returns ending at `t−21` |
| 3–1 | `P[t−21] / P[t−63] − 1` | 42 daily simple returns ending at `t−21` |

For each enabled horizon, divide its price return by the sample standard deviation of those same daily returns (`ddof=1`) times `sqrt(252)`. Zero/missing volatility makes the required signal invalid. Validate only positive-weight horizons; the unused short horizons do not exclude securities from S12/M12.

The blend uses the raw risk-adjusted values with weights 0.50/0.30/0.20. There is no hidden z-score, winsorization or percentile transform. These coefficient weights do not imply equal horizon risk contributions. Signals affect both rankings and score-based weights by design; the interaction must be interpreted accordingly.

## 6. Selection and weighting

Select the highest 75 eligible scores, breaking exact ties by ascending permanent security ID. There is no 60/100 buffer, moving-average filter or weekly risk overlay in the primary experiment.

Raw weight is `positive_score × sqrt(historical_security_total_market_cap)`. Market cap means the security class's original price times shares outstanding known at the signal time, or a proven equivalent historical series. Do not copy company-wide capitalization onto each share class, substitute present-day shares, or silently switch to free-float cap.

Normalize selected weights and impose an 8% target security cap through iterative proportional redistribution. If fewer than 75 genuinely eligible names exist, normalize over the selected names subject to that same cap; **do not add an N/75 market-timing budget**. Retain cash only when no eligible holdings exist, cap capacity is insufficient, orders cannot fill, or accounting creates temporary cash. Missing historical data must not be disguised as such a cash decision.

The cap applies to scheduled target weights. Subsequent price movements and maintenance flows may produce drift; report it rather than introducing an unannounced daily rebalance. A cap-data-independent equal-weight variant would need a separate configuration and name, not a silent fallback for the primary study.

## 7. Execution and accounting

- Compute scheduled signals after the trading close and execute at the next trading open. The semiannual dates are March/September month-end proxies, not claimed official SPMO rebalance dates.
- Use raw executable prices for the share/cash ledger, not adjusted close as if it were an opening fill. Fractional shares, no leverage, no shorting, USD, zero cash interest and no investor-level taxes are explicit simplifications.
- The opening fill model assumes the full executable order fills at the raw open. Converting target weights to fractional shares using that open is an idealized simulation, not proof that identical real auction orders can be submitted before the opening price is known.
- Account for splits and other corporate actions in shares/cash. Recognize dividend receivables on the ex-date and make cash spendable on the pay date. Never combine an already dividend-adjusted return with the same dividend cash flow again.
- Reinvest only newly paid dividends at the next open in proportion to eligible existing holdings at the preceding close. If there are none, retain cash. Existing strategic cash is not swept into the market by this rule.
- On overlapping dates, process corporate actions, required constituent exits, then scheduled rebalancing; dividend reinvestment is subsumed into scheduled rebalancing rather than traded twice. Net same-security orders before assessing transaction costs.
- Once a constituent removal is both effective and known, exit at the next tradable open. Proceeds remain cash until the next scheduled selection. Never buy an exited security back through a dividend instruction.
- Cancel unfilled ordinary rebalance/dividend orders for that day; do not pursue them automatically. Required exits remain pending and retry at the next tradable open. Do not spend proceeds of failed sells. Scale executable buys proportionally if cash is insufficient, including fees, and report target/actual deviations.
- Missing prices, suspensions and delistings require explicit event and valuation treatment. An old carried price is not a tradable quote; unresolved material settlement data block a formal result.

Benchmark portfolios use the same external trade-cost and dividend-cash conventions. A vendor's standard close-to-close ETF total-return series can appear as a separate reference with its reinvestment convention labeled. Embedded ETF expenses must not be deducted a second time.

## 8. Costs, metrics and interpretation

Apply **5 bps per side** to actual executed notional: each buy and each sell pays separately. Report all prespecified 0/5/10/25 bps scenarios. These are assumptions covering aggregate trading friction, not measured execution costs or guaranteed fills.

| Metric | Definition / role |
|---|---|
| Net total return | Reporting-end NAV / reporting-anchor NAV − 1 |
| Primary frequency spread | `100 × (net return M12 − net return S12)`, percentage points |
| Within-study robustness and interaction | Same units and same window; definitions above |
| Maximum drawdown | Minimum of NAV / prior running maximum − 1, using reporting-period daily closes including anchor |
| Gross traded notional | Sum of absolute executed buy and sell values; also sum each event's traded value / pretrade NAV; no hidden division by two |
| Cost sensitivity | Rerun every account under all four cost scenarios; separate gross and net paths |
| Diagnostics | Monthly returns, holdings count, cash weight, weight drift, issuer concentration, failures and stale marks |

Do not annualize a partial-year realized return and label it a multi-year CAGR. Sharpe is optional only with an explicit risk-free series and short-sample caveat. Net-return spreads are not factor-adjusted alpha. A single observed year, more bootstrap draws or a longer list of strategies cannot erase design-selection bias.

Read net return together with drawdown, extra traded notional and cash exposure. A shallower drawdown accompanied by much more cash is a different tradeoff from the same drawdown at similar exposure. No unagreed risk tolerance converts these measures into a single winner score. Costs affect cash and later trades, so a fee break-even point cannot be inferred by subtracting a linear annual fee estimate from one run; a claimed crossing requires actual reruns and a stated search procedure.

## 9. Release and extension rules

Before any market result: audit the [data contract](../data/feasibility.md), verify the chosen [source route](../data/sources.md), implement and test accounting, freeze the code/configuration/data manifest, and execute every prespecified arm/cost pair. Store the full reporting and burn-in ledgers separately.

The initial release deliberately does not test buffers, a 200-day filter, weekly stops, Turbo variants, parameter sweeps or live trading. They become separate future protocols only after the four-arm result is understood. Report negative outcomes as readily as positive ones.

## 10. Supplementary calendar sensitivity

Keep March/September as the primary semiannual schedule. The supplementary [calendar configuration](../../../configs/calendar-sensitivity.v1.json) prespecifies all six month pairs: January/July, February/August, March/September, April/October, May/November and June/December. Use each month's last exchange-session close and the same next-open execution rule. Apply the full burn-in separately to every account; changing the schedule also changes its reporting-anchor holdings.

For each signal and cost scenario, report the monthly-minus-semiannual contrast for every pair, including the original March/September pair. Also report the descriptive mean and minimum/maximum of those six contrasts. Do not select the most favorable phase, redefine the primary comparison or present the phases as six independent experiments. They reuse prices, overlap in holdings and share the same market episodes. The mean of phase-level results is not the return of a tradable blended portfolio. See the [calendar sensitivity guide](calendar-sensitivity.md) for execution and output details.

## 11. Longer-history research plan

The fixed 2026 cutoff remains a retrospective case study. A stronger claim about persistence needs a separately frozen multi-year extension after historical coverage is audited. Before running it, publish the exact covered dates, warm-up, initial formation, burn-in, eligible complete calendar years, data versions, all comparisons and cost scenarios. Select the interval by a documented coverage rule rather than by which dates produce attractive returns. No dates or results for that extension are implied by this release.

Use continuing accounts through the accepted interval and report annual paired frequency effects alongside the full-period result. Annual measurement anchors normalize existing portfolios without resetting holdings or charging initial formation again. Show losing years, drawdown episodes, traded notional and cash exposure; adjacent years and different calendar phases are not independent observations. Partial years remain separately labeled. Earlier historical windows are still retrospective research, not automatically untouched holdouts. A genuinely prospective track begins only after a timestamped freeze.

The [research blueprint](research-blueprint.md) explains the decision and presentation priorities. The [data acceptance sample](../data/acceptance-sample.md) defines the next evidence needed before a market run.
