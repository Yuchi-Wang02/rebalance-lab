# Evidence record and claim boundaries

Source review: October 8, 2026 (America/New_York). Reproducible diagnostic run: October 9, 2026 UTC.

## Synthetic engine validation

The October 9 implementation adds the four-arm synthetic engine. A deterministic fictional fixture exercised all 16 strategy/cost combinations. All 9 run-level checks passed; 76 offline tests covered ingestion, signals, portfolio accounting, point-in-time selection and reporting boundaries. Independent accounting checks also reconciled mixed action scenarios against the asset-value identity. These are engineering results, not market performance.

The [public engineering receipt](../site/data/engine-status.json) records code, configuration and fixture hashes, scenario counts and individual checks without publishing fictional return figures. The [engine guide](engine.md) documents the runnable command and remaining acceptance work. Detailed synthetic ledgers stay in ignored generated-output directories. All 98 files covered by the local run manifest had matching checksums, and daily NAV reconciled to cash plus receivables plus securities value for every path.

## What has been inspected

The user-supplied prior discussion was read successfully. It requested an SPMO-like strategy with more active rotation, followed by a 2026 YTD investigation. The historical reply explicitly admitted that market-data retrieval failed and no actual return result was produced. Its old Notebook/ZIP and claimed synthetic-test count have not been recovered or verified in this repository.

The prior conversation is project context, not a market-data source. Unrelated personal investment discussion and the raw conversation are not republished here.

Official/provider-maintained package documentation and source repositories were inspected where reachable. The [connection guide](data-sources.md) and [machine-readable source registry](../configs/data-sources.json) record source-specific evidence. Documentation access must not be reported as authenticated table access, full data coverage, or point-in-time validation.

## Official strategy references and limitations

- [Invesco SPMO product page](https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html)
- [S&P Momentum Indices methodology PDF](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-momentum-indices.pdf)

The initial checks were refused at the HTTPS proxy CONNECT stage. After a supported network change, the S&P PDF returned HTTP 200 and was read successfully: **August 2026 edition**. The Invesco page also returned HTTP 200, but the retrieved text was primarily a navigation shell; current fund holdings and fee details were not independently established from it.

The S&P document confirms several important differences from our custom experiment:

| Topic | Inspected official methodology | Our experiment |
|---|---|---|
| Selection | Highest quintile with a 20% buffer rule; printed page 7 | Fixed Top 75, no buffer |
| Weighting | Float-adjusted capitalization × transformed momentum score; printed pages 3 and 8 | Security-class total cap square root × raw positive risk-adjusted score |
| Timing | Third Friday of March/September, with prior month-end reference dates; printed page 10 | March/September month-end signal, next-open fill for the slow control |
| Signal treatment | Risk-adjusted price momentum, cross-sectional z-score, winsorization and positive score transform; printed pages 18 and 20 | Explicit trading-session windows and unstandardized values; positive raw-score eligibility |

These are reasons to treat SPMO as a product benchmark, not to call our slow arm a replica. The August 2026 document cannot by itself establish every methodology version effective during the 2025 burn-in and earlier 2026 period. A future official-index replication would need applicable historical revisions and supporting documents. No current holdings, fees or fund performance figures are copied into research data.

Inspected PDF SHA-256: `1aeb5efbd5799f49512784f8cab7d0dc275519aabb2bae36fc9d35e64a7eac36`. Only its source URL, hash and factual method comparison are published here; the document is not redistributed.

## Latest access evidence

Nine credential-free documentation probes succeeded. The first Yahoo chart probe returned five timestamps and four complete OHLC bars. The subsequent fixed-window ingestion requested December 1, 2023 through October 2, 2026 and returned 711 rows for each of SPMO and SPY. Both had zero missing/invalid OHLC records, no structural/value errors and 12 vendor dividend events. Their observed dates agreed. Offline replay verified original hashes and reproduced the normalized files and quality report exactly.

The [aggregate summary](../site/data/ingestion-summary.json) records run identities, dates, counts, parser/response hashes and unresolved warnings. The [pipeline guide](data-pipeline.md) explains reproduction. Raw observations remain in ignored private directories. This is not a licensed full-universe extract, an exchange-calendar/point-in-time audit, a validated benchmark-return series or input to a reported backtest. It does not extend the October 2 cutoff.

The source registry distinguishes this sample from authenticated downloads and records more specific product/schema limitations. GitHub API connectivity also recovered; Pages activation nevertheless returned an origin authorization error for the connected integration. Network reachability and application permission are separate gates.

## Distinct states

| State | What it establishes | Current position |
|---|---|---|
| Documentation reviewed | A specific guide or SDK states a capability or requirement | Available for selected sources; see registry |
| Endpoint reachable | A particular request reached a server | Documentation, Yahoo chart captures and selected metadata requests succeeded; not proof of a subscription |
| Diagnostic reproduced | Fixed inputs pass structural checks and replay produces the same files | SPMO/SPY diagnostic passed; calendar, adjustments and point-in-time semantics remain unaudited |
| Licensed extraction completed | Entitled data were retrieved for a named query/window | Not completed |
| Data audit completed | IDs, time semantics, coverage and actions passed acceptance | Not completed |
| Engine prototype tested | Deterministic tests establish specified accounting and timing behavior | Synthetic implementation and all 16 paths exercised; formal market-engine acceptance remains pending |
| Historical experiment completed | Audited data and frozen code produced the full result set | Not run |
| Site deployed | A public Pages deployment succeeded and its URL was checked | Determined separately from research readiness |

The local design validator checks selected invariants and links only. A rendered page or successful Git push cannot establish investment performance. The source probe never supplies credentials and must not interpret a proxy refusal as evidence that a provider lacks the dataset.

## Publication boundaries

Publish methods, code, permitted aggregate outputs and reproducibility manifests. Do not commit credentials, private account details, raw chat, or market data whose redistribution rights have not been established. A software package's open-source license is not a license to redistribute the provider's financial data.
