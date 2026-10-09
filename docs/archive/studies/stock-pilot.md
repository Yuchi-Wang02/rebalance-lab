> Archived research document. Historical scope and status are retained; see the [current validation case](../../studies/validation-study.md).

# Stock pilot: faster rotation helped in 2026, but not in 2025

The fixed-cohort stock pilot produces a useful mixed result. At 5 basis points per side, monthly 12–1 selection led its semiannual counterpart by **8.84 percentage points in 2026 through October 2**, after trailing by **6.93 points in 2025**. Across the full account history, its advantage was only **1.23 points**; at 25 basis points per side that full-period difference became **−0.74 points**.

These are retrospective results under the pilot's vendor-price assumptions. They do not establish that monthly rotation will outperform, and they do not validate the original 75-stock experiment. Corporate-action adjustment remains a material qualification, especially for the blended semiannual portfolio.

Explore the [stock pilot page](../../../site/stocks.html), [complete aggregate results](../../../site/data/stock-pilot-summary.json), [portfolio paths](../../../site/data/stock-pilot-nav.json), and [reconstruction sensitivity](../../../site/data/stock-pilot-sensitivity.json). Those saved artifacts, rather than rounded figures in this article, are the numerical record.

## What was tested

The [pre-acquisition design freeze](../../../configs/stock-pilot.design-freeze.json) starts with the historical S&P 500 membership snapshot at December 31, 2024. It ranks the directly covered issuers by that date's Sharadar `DAILY` capitalization and retains the largest 100, using one fundamental share-class representative per issuer. It does not substitute a different stock when future price coverage is inconvenient. New index entrants are not added to this fixed cohort; a recorded removal would require an exit at the next open after the inactive close. The [current configuration](../../../configs/stock-pilot.v1.json) records a later correction to the price-series description after composite corporate-action adjustments were identified. That correction did not change prices, signals, weights or numerical strategy rules.

Each strategy selects up to 20 positive-score stocks from that cohort. Targets use the momentum score multiplied by the square root of dated issuer capitalization, with an 8% target security cap. That cap applies at selection; subsequent price drift can produce larger weights. Issuer capitalization and the reduced universe/position count are explicit departures from the original historical-universe, class-capitalization, 75-stock protocol.

| Portfolio | Scheduled selection | Signal |
|---|---|---|
| S12 | March and September month-end | 12–1 momentum |
| M12 | Every month-end | 12–1 momentum |
| SMIX | March and September month-end | 50% 12–1, 30% 6–1, 20% 3–1 |
| MMIX | Every month-end | The same blended signal |

Signals omit the most recent 21 sessions and use the configured risk adjustment. The initial signal is December 31, 2024; the account starts with $1 million cash and trades at the next session's opening proxy. The 2025 formation and burn-in history is shown separately. The 2026 interval starts from the existing December 31, 2025 closing portfolio and ends October 2, 2026: holdings are not reset and initial purchase costs are not charged again.

All four strategies were rerun at 0, 5, 10 and 25 basis points per side, producing 16 strategy paths. SPY and SPMO have eight additional buy-and-hold context paths under the same cost grid. They are product comparisons, not controls that isolate selection frequency. The original [research protocol](../methods/original-stock-protocol.md) and its separate [calendar-sensitivity study](../methods/calendar-sensitivity.md) remain unchanged; the stock pilot does not claim that the six calendar phases were tested on these market inputs.

## Results at 5 basis points per side

Returns below include the modeled trading fees. They use vendor-adjusted accounting units, so “return” here means the pilot's adjusted-price return proxy. Drawdown is the worst daily-close decline from a running peak within each stated interval. Turnover is summed absolute executed buy-plus-sell notional divided by pretrade NAV at each event; there is no division by two. The 2025 column includes the initial purchase, while the 2026 buy-and-hold benchmark columns have no new trades.

| Portfolio | 2025 return | 2025 drawdown | 2025 turnover | 2026 YTD return | 2026 YTD drawdown | 2026 YTD turnover |
|---|---:|---:|---:|---:|---:|---:|
| S12 | 20.49% | −18.93% | 2.78× | 27.05% | −14.62% | 2.56× |
| M12 | 13.56% | −22.02% | 7.38× | 35.89% | −10.50% | 4.42× |
| SMIX | 16.04% | −18.22% | 3.01× | 15.09% | −13.80% | 2.90× |
| MMIX | 11.81% | −23.19% | 8.14× | 22.54% | −12.60% | 5.70× |
| SPY context | 17.00% | −18.76% | 1.00× | 13.75% | −8.88% | 0.00× |
| SPMO context | 25.48% | −20.13% | 1.00× | 29.19% | −15.64% | 0.00× |

The 12–1 monthly portfolio's 2026 advantage coincided with a shallower drawdown and approximately **1.86× additional turnover**. Its 2025 result went the other way: a lower return, deeper drawdown, and approximately **4.60× additional turnover**. The blended pair also switched from a negative frequency difference in 2025 to a positive one in 2026. These shared observations are within-study comparisons, not independent replication.

The full-period 5 bps returns were 53.08% for S12, 54.32% for M12, 33.55% for SMIX, and 37.00% for MMIX. Full-period returns compound the two intervals; annual return differences cannot simply be added. SPY and SPMO's corresponding proxy returns were 33.08% and 62.10%.

## What the cost grid changes

The primary spread below is M12 minus S12, in percentage points. Each cell comes from a separately simulated account at that fee rate, rather than subtracting a flat fee estimate from one path.

| Cost per side | 2025 spread | 2026 YTD spread | Full-period spread |
|---|---:|---:|---:|
| 0 bps | −6.68 | +8.98 | +1.74 |
| 5 bps | −6.93 | +8.84 | +1.23 |
| 10 bps | −7.18 | +8.70 | +0.73 |
| 25 bps | −7.93 | +8.29 | −0.74 |

The full-period primary spread changes sign between the tested 10 and 25 bps scenarios. This brackets a crossing in the tested model; it does not measure real execution costs or identify a precise investable break-even fee. The blended pair's full-period spread remains positive across this grid, falling from +4.01 points at 0 bps to +1.29 at 25 bps. The brief history and common data assumptions prevent either observation from establishing persistent superiority.

## Inputs, reconstruction and unresolved events

The paid inputs came from [Nasdaq Data Link / Sharadar](https://data.nasdaq.com/publishers/SHARADAR): historical membership, `DAILY` capitalization, `TICKERS` metadata, and `ACTIONS` records. Price observations came from Yahoo chart endpoints. Access to paid inputs does not itself prove their historical information-availability semantics.

The saved pilot audit covers **102 price series across 711 common sessions**, or **72,522 rows**, plus **44,000 dated capitalization rows**. The baseline snapshot contained 503 securities; three secondary share classes were excluded from issuer ranking. There were 70 recorded membership changes during the holding period and **zero removals from the selected 100-issuer cohort**, so this realization does not demonstrate the required-exit behavior on a removed cohort member. The common calendar uses `XNYS` from `exchange_calendars` version 4.11.2. The audit's pass flag applies to this narrow pilot contract, not the original protocol.

There is one sourced price reconstruction. Yahoo's daily FISV row for November 12, 2025 was null; seven observed hourly bars supplied the regular-session open, high, low and last observed close. The original null row was retained, and an extra current-quote row outside the requested session was quarantined rather than admitted as historical data. The official closing-auction price is not independently verified. The [audit policy](../../../configs/stock-pilot-audit.v1.json) restricts this repair to that symbol and date.

The saved sensitivity reruns all 16 strategy paths after changing only that reconstructed signal/adjusted close by −1% and +1%, with the observed open held fixed. Both cases produced **zero changed target paths and zero NAV differences**. No strategy held FISV on the repaired date. This is a specific robustness check, not a confidence interval or proof of the reconstructed close's correctness.

Four source spin-off events still require particular care: HON on October 30, 2025; CMCSA on January 5, 2026; HON on June 29, 2026; and SPGI on July 1, 2026. The source price responses include composite adjustment ratios in Yahoo's split-event field: 1061:1000, 1067:1000, 1907:2000 and 1057:1000 respectively. A field named “splits” does not make those observations a verified split-only series.

Only SMIX held HON immediately before the June 29 event, across all four fee scenarios, at approximately **2.04% of NAV**. The other three events did not have a held position in the strategy paths at their preceding close, but adjusted price history can still affect later signal rankings. An empty exposure list does not independently verify an entitlement date or the provider's adjustment treatment.

Yahoo closes therefore supply a **vendor corporate-action-adjusted price proxy**, not a verified split-only signal series. Accounting uses adjusted closes and an adjusted open derived from the same-date adjusted-close/close ratio. Those units are not raw shares or a verified distribution ledger. The pilot does not reconstruct cash dividend payment dates, distributed securities, or complete spin-off entitlements. Adding a separate cash credit could double-count adjustments already embedded by the vendor. In particular, the HON exposure must not be read as evidence that a dividend or spin-off ledger reconciled correctly. Spin-off adjustment and entitlement completeness remain unverified, so affected results remain provisional.

Capitalization is a dated issuer observation rather than a certified point-in-time publication vintage. Membership effective dates are assumed known at the corresponding close; original announcement timestamps have not been verified. These limitations affect historical realism even when the calculations replay exactly.

## Reproduction and publication boundaries

The internal run checks passed for all 16 strategy/cost paths, including the common cohort, next-session execution, fee arithmetic, nonnegative cash, finite NAV and continuing reporting anchor. A separate implementation then recalculated all **24 strategy/benchmark paths, 10,560 daily account states, 21,600 signal records and 5,588 orders**. Maximum relative NAV error was **2.21 × 10⁻¹⁵**. The [independent receipt](../../../site/data/stock-pilot-validation.json) binds 123 source hashes, configuration, normalized inputs, outputs and code. Agreement establishes computational reproduction under these inputs; it does not establish source accuracy, corporate-action completeness or formal acceptance.

Keep the licensed captures, source responses, normalized security-level inputs and detailed ledgers in ignored private data directories. Public artifacts contain derived portfolio series, aggregate metrics, quality findings and provenance hashes. API credentials and raw paid data are not part of the publication.

For an authorized fresh acquisition, `scripts/stock_pilot_sharadar.py` captures the paid inputs and `scripts/stock_pilot_prices.py` captures exactly the frozen price-symbol list. Their `--help` output documents required private input/output paths. Do not choose a replacement cohort after inspecting failed symbols or results.

To replay preserved inputs, set the path variables to the corresponding private captures and choose a new, nonexistent output directory:

```bash
.venv/bin/python scripts/run_stock_pilot.py \
  --sharadar-dir "$PILOT_PAID_DIR" \
  --yahoo-dir "$PILOT_PRICE_DIR" \
  --membership-snapshot "$PILOT_MEMBERSHIP_SNAPSHOT" \
  --membership-events "$PILOT_MEMBERSHIP_EVENTS" \
  --fisv-intraday-source "$PILOT_FISV_SOURCE" \
  --output-dir "$PILOT_RUN_DIR" \
  --publish-dir site/data

.venv/bin/python scripts/stock_pilot_sensitivity.py "$PILOT_RUN_DIR"
.venv/bin/python scripts/validate_stock_pilot_independent.py --run-dir "$PILOT_RUN_DIR"
```

The [configuration](../../../configs/stock-pilot.v1.json), [source-repair policy](../../../configs/stock-pilot-audit.v1.json), source hashes and code hashes identify the assumptions behind the saved result. Replaying them can check implementation consistency. Extending the finding requires resolving the material source assumptions and testing a separately specified longer history, not treating a favorable 2026 interval as a forecast.
