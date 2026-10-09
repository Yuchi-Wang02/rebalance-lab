# Independent validation of the market pilot

The separate sector ETF pilot passed an independent portfolio replay of **all 60 paths**: 56 strategy paths and four SPY benchmark paths. This verifies implementation consistency on the preserved market-data snapshot. It does not independently certify Yahoo's historical data or complete the original stock experiment.

| Check | Result |
|---|---|
| Daily account observations compared | 403,740, including formation and burn-in |
| Maximum relative NAV difference | `1.1335e-14` |
| Maximum absolute cash difference | `$0.00000003353` |
| Selected funds and decision/fill dates | All matched |
| Analytically solved fees and traded notional | All matched within numerical tolerance |
| Full-period, annual and partial-year metrics | All matched |
| Public comparisons and plotted wealth/drawdown points | Matched the preserved daily ledgers |
| SPY buy-and-hold identity | Matched the adjusted-close return at all four costs |
| Provenance | Configuration, code, raw captures and saved result hashes matched |

The [machine-readable receipt](../site/data/etf-pilot-validation.json) binds these checks to the exact public summary, run manifest, input snapshot and verifier code. The reviewed run is `20261009T021722928426Z-9e9cb830b3cb`.

## What makes this a separate check

The [verifier](../scripts/validate_etf_pilot_independent.py) imports no engine, signal or accounting code from the project. It calculates sample volatility directly, ranks positive momentum scores, recreates month-end decisions and next-session executions, and rebuilds each account's cash and adjusted units. It solves the post-fee target equation analytically over its linear intervals; the main engine uses numerical bisection. The small differences above reflect floating-point arithmetic.

The replay checks daily NAV, cash and held units; every selected portfolio and execution date; fees and two-sided turnover; annual observations; the 25-year CAGR; daily maximum drawdown; and mean cash exposure. It also confirms that 2026 returns remain unannualized and accounts continue through the reporting boundary. Independent arithmetic does not remove the shared input-data assumptions.

## Findings and limits

Two presentation inconsistencies were corrected before the saved market run: full-period CAGR and annualized trading activity now use the declared 25 calendar years, while 2026 partial-year annualized fields are null. No material portfolio-accounting discrepancy remained in the independent replay.

The primary result is a negative monthly-minus-March/September CAGR spread of approximately **0.49 percentage points per year at 5 bps per side**. Monthly selection had a smaller maximum drawdown and more trading. It led in 13 of 25 annual observations, which does not turn a lower compounded return into an overall win. Across all six prespecified phases, monthly selection led in three under the 12–1 signal and one under the blended signal. These are dependent comparisons, not independent replications or significance tests.

Vendor adjustment assumptions remain material. An inspection around XLF's September 2016 real-estate distribution found continuous adjusted prices; Yahoo represents the event as a `1231:1000` split. This is a vendor adjustment convention, not evidence of a literal XLF share split or independently verified distribution accounting. The funds' sector definitions also changed over the sample. The strategy therefore trades historical fund exposures using a total-return proxy, not constant sector portfolios or a raw-share dividend ledger.

## Reproduce the check

After acquiring and saving a snapshot with the documented [pilot workflow](sector-etf-pilot.md), pass its preserved run directory:

```bash
python3 scripts/validate_etf_pilot_independent.py \
  --run-dir results/generated/etf-pilot/<run-id> \
  --summary site/data/etf-pilot-summary.json \
  --public-summary site/data/etf-pilot-validation.json \
  --private-report results/generated/etf-pilot-independent-validation.json
```

The verifier fails before writing a new receipt when hashes or calculations disagree. Raw observations and the full daily account files remain excluded from Git; a new live download may contain vendor revisions and therefore will have a different snapshot hash.
