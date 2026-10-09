# Public-market sector ETF frequency experiment

This is a **separate real-market pilot**, not completion of the original top-75 stock experiment. The original requires historical membership, class-level capitalization and corporate-action records that the accessible sources do not currently supply. See the original-data audit. This experiment asks a narrower question: does more frequent selection improve a simple sector ETF momentum allocation after modeled costs?

## Protocol fixed before the performance run

The machine-readable specification is `configs/sector-etf-pilot.v1.json`. Freeze it in Git before calculating any strategy performance. This is a retrospective analysis, not an untouched holdout or prospective registration.

- Universe: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV and XLY, the original nine Select Sector SPDR funds. Later sector funds are excluded by the launch-cohort rule, not by measured performance. Sector definitions and underlying holdings have changed historically.
- Request daily observations from December 1, 1998 through October 2, 2026. Audit the common history and actual XNYS sessions. Insufficient initial history or a missing required observation blocks the run.
- Form accounts at the final 1999 session close, execute at the next session open, and use 2000 as portfolio burn-in. Measure the 25 complete years 2001–2025 from the last 2000 close. Keep accounts continuous; annual boundaries never liquidate or reset holdings. Report 2026 through October 2 separately as a secondary case study.
- Compute risk-adjusted momentum over 252/126/63-session horizons, skipping the latest 21 sessions. For each horizon, divide the return between those endpoints by the sample standard deviation of the same interval's daily returns, annualized by the square root of 252. The primary pair uses only 12–1; a 50/30/20 blend is a within-study robustness check.
- Rank positive scores, break exact ties alphabetically and select at most three funds. Allocate one-third of post-fee NAV to each selected fund; unused slots remain in zero-interest cash. This fixed-slot rule is an explicit change from the original stock protocol.
- Monthly selection is compared with all six semiannual month pairs. March/September remains the primary control. Initialize all phases identically and preserve their own subsequent holdings. Reuse monthly controls rather than treating them as six independent observations.
- Signals form after the month-end close and execute at the next verified session open. Trade fractional units, rebalance selected weights even when names do not change, and charge 0/5/10/25 bps on all executed buy and sell notional. Five bps is the primary assumption. Solve post-fee target weights and costs together; do not subtract fees retrospectively from one gross path.
- SPY buy-and-hold is context at the same boundaries, not a control that isolates frequency. Do not subtract fund expenses twice.

## Price and distribution convention

Use Yahoo's reported adjusted closing price as an explicitly labeled **total-return proxy**, both for signals and valuation. Define the adjusted opening proxy as `Open × AdjClose / Close`. Orders trade adjusted units at this proxy, with the same day's adjustment factor. Price scale factors cancel from historical ratios and unit valuations, but source revisions and adjustment errors remain possible.

This convention assumes the vendor's reinvestment adjustments and does not simulate raw shares, dividend receivables, payment-date cash or achievable distribution reinvestment. Do not add dividends separately. These limitations are why this is a different experiment from the original dividend-excluding stock signal and raw-price ledger. Daily adjustment factors, events and return discontinuities must be inspected before execution.

## Required outputs and interpretation

Publish every signal/schedule/cost result, annual paired returns for all 25 full years, the separate 2026 case, net wealth and drawdown plots, trading activity and cash exposure. Compare net growth, drawdown and trading burden together. Identify March/September throughout; neither the most favorable phase nor the most favorable signal replaces it.

The primary numeric comparisons are the monthly-minus-March/September differences in net CAGR and cumulative return over 2001–2025 at 5 bps. CAGR uses 25 full calendar years; the 2026 partial year is not annualized. Drawdown includes the reporting anchor. Turnover means buys plus sells divided by pretrade NAV, without a hidden division by two. Report annualized activity as a descriptive full-period total divided by 25.

Annual outcomes and the six overlapping schedules are dependent. No p-values, independent-replication claim, causal market explanation or promise of future profitability follows from these comparisons. A result about sector allocation cannot establish the result of selecting 75 individual stocks.

Keep raw vendor responses and detailed ledgers private. Publish permitted derived statistics, source URLs, request and response hashes, code/configuration hashes, audit findings and replay instructions. Acquisition and a deterministic rerun are separate checks; neither proves the vendor's values are independently authoritative.

## Execution and replay

Specification freeze: commit `8bb2e11`, before this pilot's performance calculation. The original protocol file was not changed. Install `requirements-pilot.txt` in an isolated environment, then run:

```bash
python scripts/etf_pilot_data.py --acquire --audit-output results/generated/pilot-data-audit
python scripts/run_etf_pilot.py --raw-dir data/raw/sector-etf-pilot/<snapshot> --public-dir site/data
python scripts/validate_etf_pilot_independent.py --help
```

The data command returns the real snapshot directory; replace the placeholder with it. For an offline input replay, use `etf_pilot_data.py --raw-dir <same snapshot> --audit-output <new private directory>`. Each raw response and execution has a hash manifest. The independent verifier documents its arguments in `--help` and imports no engine code. A fresh acquisition can contain vendor revisions, so equality is claimed only for the preserved input snapshot.

The [completed retrospective](pilot-retrospective.md) and [independent validation](pilot-validation.md) distinguish the original stock-data blockers from this pilot's own limitations. Yahoo chart requests are documented by the acquisition script; [yfinance's maintainer documentation](https://github.com/ranaroussi/yfinance) describes the unofficial source and usage limits. Session comparison uses [exchange-calendars 4.11.2](https://pypi.org/project/exchange-calendars/4.11.2/). Raw observations are retained privately, not redistributed.

Fund mandates are not fixed economic-sector histories: XLF's 2016 real-estate separation and the 2018 communication-services reclassification changed exposures. The snapshot represents XLF's 2016 distribution as a split-like adjustment; this pilot uses the adjusted fund path and does not interpret that vendor record as a literal raw-share split. These are additional reasons not to transfer its results to the original stock-selection protocol.
