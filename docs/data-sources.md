# Data sources and connection plan

**The SPMO/SPY price diagnostic is executable; the original stock experiment has no validated market dataset.** A separate [sector ETF pilot](pilot-retrospective.md) has acquired and audited a public adjusted-price snapshot; its narrower data convention does not satisfy the original stock contract. This document separates documentation that was actually read, public endpoint diagnostics, and untested authenticated access. The machine-readable catalog is [data-sources.json](../configs/data-sources.json); commands and replay instructions are in the [pipeline guide](data-pipeline.md).

**Updated buying decision:** see the [purchase guide](data-purchase-guide.md) and [official-source evidence](../results/data-purchase-audit.json). The October 8 follow-up verified `SHARADAR/SP500`, `ACTIONS` and `SFP`; the earlier assumption that Sharadar necessarily needs a separate membership supplier is corrected below. Norgate Platinum is USD 346.50 for six months or USD 630 for twelve months, but is not a complete solution by itself.

The recommended order is: use an existing institutional entitlement if one is available; otherwise verify the required commercial data components before choosing a subscription. Use Yahoo/yfinance only for a no-cost diagnostic. Norgate is a conditional Windows export route, not a native connection for this Linux workspace. No purchase, signup, credential request, or authenticated data download has been performed.

## 1. What was verified

Source documentation was inspected on 2026-10-08, America/New_York. The fixed-window diagnostic was acquired on 2026-10-09 UTC. Rechecks followed an applied network configuration change. These observations describe this environment at inspection time, not permanent availability.

| Route | Documentation actually read | Market API/sample | Authenticated full coverage | Point-in-time integrity |
|---|---|---|---|---|
| Yahoo/yfinance | Maintainer README and download source | Direct chart capture: 711 daily rows each for SPMO/SPY, zero missing/invalid OHLC; hash-verified offline replay | Not established; yfinance SDK not used | Not established |
| WRDS/CRSP | Official WRDS SDK and public demo; full manual entrypoint redirects to login | Fixed public monthly demo: 24 records for IBM/MSFT in 2006; no entitled query | No entitlement or coverage verified | Membership, revisions and delisting contract not established |
| Nasdaq Data Link / Sharadar | Official SDK plus public metadata for SEP, DAILY, SF1, TICKERS, SP500, ACTIONS and SFP | Seven metadata endpoints HTTP 200; actual sample and dictionary requests require an API key | No entitlement or price/fundamental rows verified | Field definitions, coverage and revision/availability semantics not established |
| Norgate | Provider-published package description and public data-content page | No NDU connection or export | No subscription verified | Historical membership coverage is documented; announcement-time correctness is not established; documented fundamentals are current-only |

Initial requests to several provider sites failed with proxy CONNECT 403. After the supported network change, Yahoo, Nasdaq, WRDS and Norgate were reachable. Results must be classified by layer: the old Nasdaq collection and WRDS membership-guide URLs returned origin 404; WRDS manuals redirected to login; Nasdaq's product page returned an HTML application shell; its indicator dictionary returned origin 403 with API error `QEPx04` requiring a valid API key. An initial concurrent TICKERS metadata request returned origin 429 (`QELx04`); a later sequential request succeeded. FMP documentation still failed at proxy CONNECT 403, before any origin response. No proxy, TLS, authentication or network restriction was bypassed.

The initial Yahoo probe and provider metadata evidence were held in temporary files. The repeatable diagnostic now stores private raw and derived snapshots in ignored data directories. Only an [aggregate summary](../site/data/ingestion-summary.json) is committed; no market bars are published. Successful acquisition and replay do not establish permission to redistribute vendor data or complete historical research coverage.

“Historical data,” “survivorship-bias-free” and “point-in-time” are different claims. A table indexed by a past date does not establish when a record first became available or whether later revisions replaced the original value.

## 2. Shared acquisition contract

Provider exports belong in ignored `data/raw/<provider>/<snapshot-id>/`; normalized tables belong in ignored `data/processed/<provider>/<snapshot-id>/`. Yahoo diagnostic snapshots now use this layout; the broader research tables below are still planned. Keep original files immutable. Publish only metadata and outputs permitted by the data license.

Every snapshot needs a manifest with provider/product/version, requested and returned dates, retrieval timestamp, schema and units, adjustment settings, timezone, row counts, file hashes, license restrictions, and unresolved fields. Never place API keys, passwords or credential-bearing request URLs in manifests or Git history.

| Normalized component | Required content | Acquisition and validation rule |
|---|---|---|
| `security_master` | Permanent security ID, issuer ID, historical ticker intervals, security class and currency | Ticker is a display label, not a permanent join key; resolve changes and multiple share classes |
| `membership` | Index ID, security ID, effective interval, announcement/known-at timestamp and source | Obtain history, not today's list; an effective date alone does not prove announcement-time availability |
| `prices` | Session, raw open, raw close, currency and tradeability status | A column named Open is not automatically unadjusted; verify split and dividend treatment before mapping |
| `signal_prices` | Split-adjusted close excluding all cash-dividend reinvestment, adjustment provenance | Derive consistently from raw prices and corporate actions or use a documented equivalent; do not use total-return prices without changing the signal definition |
| `market_caps` | Historical security-class total cap in USD, observation date, known-at timestamp and units | Verify share units, class allocation and publication lag; current cap or current shares cannot be backfilled |
| `corporate_actions` | Split factors, dividends, ex-date, pay-date, mergers, removals, delisting payments and status | Do not interpret an ex-date or a vendor's entitlement date as a cash payment date |
| `benchmark_prices_actions` | SPMO and SPY prices and actions in the same conventions | Verify ETF coverage explicitly; a US equity feed is not proof of ETF coverage |
| `session_calendar` | Exchange sessions, timezone, opens and closes | Validate the common executable start, signal lags, missing sessions and at least 253 price observations through the first signal |

`retrieved_at` records when we downloaded a file; it cannot be substituted for a historical `known_at`. If only effective-date history is available, either obtain announcement evidence or declare a narrower historical-membership approximation. Do not label that approximation as fully point-in-time.

For any chosen route, begin with a small schema and coverage sample: SPMO, SPY, a continuing constituent, a dated addition/removal, a split event, and a delisted or acquired security. Check fields and accounting before requesting the entire historical universe. A successful one-symbol sample is still not a completed data audit.

## 3. Route A: Yahoo/yfinance diagnostic

**Use:** establish whether ordinary prices, benchmark series and split/dividend events can be acquired and parsed. This route alone does not supply the complete historical universe, reliable historical class-level caps, announcement timestamps, or verified terminal delisting proceeds required by the full experiment.

Verified sources:

- [Maintainer README](https://github.com/ranaroussi/yfinance/blob/main/README.md): yfinance is not affiliated with or vetted by Yahoo; its stated purpose is research/education, and the README points to Yahoo's usage terms and personal-use restrictions.
- [Download implementation and parameter documentation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/multi.py): automatic OHLC adjustment defaults to true; action download and keeping missing rows must be chosen explicitly.

Illustrative acquisition call, **not executed here**:

```python
import yfinance as yf

sample = yf.download(
    ["SPMO", "SPY"],
    start="2023-12-01",  # includes warmup before the 2025 burn-in
    end="2026-10-03",  # end is exclusive
    interval="1d",
    auto_adjust=False,
    back_adjust=False,
    actions=True,
    repair=False,
    keepna=True,
    threads=False,
)
```

Retain vendor column names and adjustment metadata. `auto_adjust=False` disables the library's automatic OHLC adjustment; it does **not** establish that Yahoo's supplied Open is a true historical unadjusted executable price. Verify split behavior against a known split and do not silently map the result to `raw_open`. Keep vendor Close, Adj Close, dividend and split fields separate. Repair routines must be explicitly approved by the research protocol and logged, rather than silently changing observations.

The initial [five-day SPMO request](https://query1.finance.yahoo.com/v8/finance/chart/SPMO?range=5d&interval=1d) returned five timestamps but only four complete OHLC bars; the missing observation was not filled. It has been superseded for pipeline development by `scripts/ingest_diagnostic.py`, which makes direct unauthenticated requests to `query1.finance.yahoo.com/v8/finance/chart/<symbol>` with explicit dates and separate split/dividend events. It does not execute the illustrative yfinance call above.

The fixed request returned **711 observations per ETF from 2023-12-01 through 2026-10-02**, with zero missing or invalid OHLC records and no structural/value errors. Each response included 12 dividend events. Original bytes were retained with SHA-256 hashes; offline replay reproduced all normalized files and the quality report. SPMO/SPY observed dates agreed. These facts do not prove exchange-calendar completeness, action completeness, payment-date correctness, raw-price adjustment conventions or benchmark reconciliation. The [saved summary](../site/data/ingestion-summary.json) records the snapshot and parser hashes.

Do not publish downloaded Yahoo data merely because the client code has an open-source license. Data usage and redistribution rights are separate.

## 4. Route B: existing institutional WRDS/CRSP access

**Recommended first check if the researcher already has institutional access.** Candidate components are historical index membership, permanent security identifiers, daily stock prices/shares, corporate actions and delisting information. Dataset entitlement, current release, table names, ETF coverage and exact field semantics remain to be verified in the entitled account.

Verified sources:

- [Official WRDS README](https://github.com/wharton/wrds/blob/main/README.md) documents `wrds.Connection()`, `list_libraries`, `list_tables`, `describe_table` and `get_table`.
- [Official connection source](https://github.com/wharton/wrds/blob/main/wrds/sql.py) uses PostgreSQL at `wrds-pgdata.wharton.upenn.edu:9737` and enables SSL.

Connection options:

1. **Default for this cloud: authorized export/import.** In an already entitled WRDS session, identify the applicable CRSP release and export the required tables plus its data dictionary, query parameters and export timestamp. Transfer the permitted export into the private raw-data location and retain a manifest.
2. **Direct SDK only when supported.** Confirm approved PostgreSQL routing and institutional authentication before using `wrds.Connection()`. This is not an HTTPS API. Adding a web hostname to an HTTPS allowlist does not establish TCP port 9737 connectivity, and an HTTPS proxy-secret binding is not automatically a PostgreSQL password mechanism. Keep transport verification enabled.

The SDK's documented discovery sequence is:

```python
# Only after authorized credentials and transport are available.
import wrds

with wrds.Connection() as db:
    libraries = db.list_libraries()
    tables = db.list_tables(library="crsp")
    # Discover the entitled release, then describe its specific tables.
```

Do not hard-code a remembered legacy membership or return table name and assume it is the current entitled product. The [WRDS CRSP stock/index manual entrypoint](https://wrds-www.wharton.upenn.edu/pages/support/manuals-and-overviews/crsp/stocks-and-indices/) is reachable but redirects to a login page; the underlying manual was not read. The previously attempted membership-guide URL returned origin 404 after the network change and is not a verified guide. The [CRSP documentation portal](https://www.crsp.org/products/documentation/) had an earlier proxy failure and its current contents were not verified in this review.

Before implementation, establish whether the selected return field already incorporates delisting returns, or whether a separate delisting event/return must be combined. Never apply both treatments. Verify share-count units, opening-price availability, permanent-ID joins, ETF coverage and membership timing from that release's dictionary and a small exported sample. Institutional access alone does not prove historical announcement-time or revision-vintage correctness.

## 5. Route C: Nasdaq Data Link / Sharadar components

**Candidate commercial HTTPS route when institutional access is unavailable.** The official SDK interface and basic public table metadata are verified; field contracts, product coverage and point-in-time claims are not. Do not select or purchase a plan until the component gaps below are resolved.

Verified sources:

- [Official Python client README](https://github.com/Nasdaq/data-link-python/blob/main/README.md) documents `nasdaqdatalink.get_table`, the `NASDAQ_DATA_LINK_API_KEY` environment binding, and that unauthenticated calls may return limited/sample data.
- [Official configuration source](https://github.com/Nasdaq/data-link-python/blob/main/nasdaqdatalink/api_config.py) specifies the API base `https://data.nasdaq.com/api/v3` and TLS verification enabled.
- [Official table pagination source](https://github.com/Nasdaq/data-link-python/blob/main/nasdaqdatalink/get_table.py) handles cursor pagination through `paginate=True`; an initial page alone is not complete data.

The following public metadata endpoints returned HTTP 200. The follow-up adds SP500, ACTIONS and SFP to the original four. They establish names, premium flags, filters and keys. All seven responses had an empty `columns` array and null description, so they do not establish the underlying field contracts.

| Verified metadata endpoint | Name / premium flag | Filters | Primary key |
|---|---|---|---|
| [SEP](https://data.nasdaq.com/api/v3/datatables/SHARADAR/SEP/metadata.json) | Sharadar Equity Prices / true | date, lastupdated, ticker | ticker, date |
| [DAILY](https://data.nasdaq.com/api/v3/datatables/SHARADAR/DAILY/metadata.json) | Daily Metrics / true | date, lastupdated, ticker | ticker, date |
| [SF1](https://data.nasdaq.com/api/v3/datatables/SHARADAR/SF1/metadata.json) | Core US Fundamentals / true | calendardate, datekey, dimension, lastupdated, reportperiod, ticker | ticker, dimension, datekey, reportperiod |
| [TICKERS](https://data.nasdaq.com/api/v3/datatables/SHARADAR/TICKERS/metadata.json) | Tickers and Metadata / false | lastupdated, permaticker, table, ticker | table, permaticker, ticker |
| [SP500](https://data.nasdaq.com/api/v3/datatables/SHARADAR/SP500/metadata.json) | S&P500 Current and Historical Constituents / true | action, contraticker, date, ticker | date, ticker, action |
| [ACTIONS](https://data.nasdaq.com/api/v3/datatables/SHARADAR/ACTIONS/metadata.json) | Corporate Actions / true | action, contraticker, date, ticker | date, ticker, name, action, contraname, contraticker |
| [SFP](https://data.nasdaq.com/api/v3/datatables/SHARADAR/SFP/metadata.json) | Sharadar Fund Prices / true | date, lastupdated, ticker | ticker, date |

The following remain **intended component mappings to validate**, not inspected field contracts:

| Candidate table | Intended component | Required confirmation |
|---|---|---|
| `SHARADAR/SEP` | Daily stock prices | Universe coverage, retained delisted securities, split/dividend adjustment, raw-open availability and exact dates |
| `SHARADAR/DAILY` | Historical daily market-cap observations | Field units, class versus issuer cap, shares timing, revisions and availability timestamp |
| `SHARADAR/SF1` | Supporting fundamentals/share observations where needed | Dimension semantics, as-reported versus restated values, filing/publication timestamps and availability lag |
| `SHARADAR/TICKERS` | Identifier metadata and coverage inventory | Permanent-ID and historical-ticker coverage; this is not by itself proof of index membership history |
| `SHARADAR/SP500` | Historical index membership | Complete initial state and changes; effective dates versus original announcement timing |
| `SHARADAR/ACTIONS` | Corporate actions | Dividend payment dates, final merger/delisting consideration and settlement; an event date alone is insufficient |
| `SHARADAR/SFP` | ETF benchmark prices | Actual SPMO/SPY coverage and adjustment conventions |

SPMO/SPY coverage must be checked separately; do not assume SEP includes both ETFs. SF1 is not required merely because it is available: use it only when it supplies a necessary, validated field.

Illustrative table call, **not executed and not schema-validated here**:

```python
import nasdaqdatalink

# The SDK reads NASDAQ_DATA_LINK_API_KEY from secure environment settings.
sample = nasdaqdatalink.get_table(
    "SHARADAR/SEP",
    ticker="AAPL",
    date={"gte": "2023-12-01", "lte": "2026-10-02"},
    paginate=True,
)
```

The origin is reachable and SEP's ticker/date filters are listed in public metadata. The [SEP indicator dictionary request](https://data.nasdaq.com/api/v3/datatables/SHARADAR/INDICATORS.json?table=SEP&qopts.per_page=100) returned origin 403 with `QEPx04`: a valid API key is required. Its field definitions were therefore not read. Obtain the entitled dictionary and a small authorized data sample before using the example. Store access keys only in supported secure settings; never paste a real key into the example, output, request log or repository. A valid key does not establish entitlement to premium tables; conversely, metadata saying `premium=false` does not guarantee keyless data access.

**Membership candidate now identified:** `SHARADAR/SP500` is a premium table named “S&P500 Current and Historical Constituents.” First request its dictionary and an authorized sample. A separate supplier is needed only if its coverage or timing is insufficient. Its date filter does not prove announcement-time availability. Reconstruct a validated starting snapshot and all subsequent changes; today’s constituents plus an incomplete events list is insufficient.

The old Sharadar collection-documentation URL returned origin 404. The [SEP product page](https://data.nasdaq.com/databases/SEP/documentation) returned HTTP 200, but its HTML was an application shell without the required table definitions. Neither response establishes full historical coverage, raw prices, field units or PIT correctness. No price or fundamental records were downloaded from Nasdaq.

## 6. Route D: Norgate Windows export

**Conditional route if an appropriate subscription and supported Windows machine already exist.** The provider's [PyPI package description](https://pypi.org/project/norgatedata/) was read through its [package metadata endpoint](https://pypi.org/pypi/norgatedata/json). Its [public data-content page](https://norgatedata.com/data-content-tables.php) also returned HTTP 200 and was inspected after the network change.

The inspected documentation explicitly states:

- Norgate Data Updater (NDU) must be installed and running on Windows; the package requires an active subscription. It documents Windows-VM and WSL arrangements, not a stand-alone native Linux NDU service.
- Historical index constituents require a Stocks Platinum or Diamond subscription. The documented `index_constituent_timeseries` example includes `S&P 500`; the content table lists S&P 500 membership from March 1957. This is a provider coverage statement, not an audited export.
- `assetid` is a unique unchanging Norgate ID. Use it rather than ticker alone.
- Price adjustment defaults to `TOTALRETURN`; available modes include `NONE`, `CAPITAL`, `CAPITALSPECIAL` and `TOTALRETURN`. Padding can repeat old closes and must be explicitly disabled for this experiment.
- Its dividend column is dated **the day before ex-date**, depends on the chosen adjustment mode, and omits dividends already included by that adjustment. It is not a pay-date cash ledger.
- `fundamental(symbol, "mktcap")` and `sharesoutstanding` are explicitly documented as **current fundamentals**. The content page states that these fields contain last-reported values and that historical fundamentals are unavailable. They cannot supply this experiment's historical market-cap series.
- The content page defines Open as the first price from any venue/ECN. This is not necessarily the listing exchange's opening auction; retain the definition in execution-model limitations.

On an authorized supported Windows machine, export an asset-ID-based universe including relevant delisted securities, index membership series, price series with separate explicit `NONE` and `CAPITAL` modes, actions and extraction metadata. For example, the documented entrypoints are `price_timeseries(..., stock_price_adjustment_setting=..., padding_setting=PaddingType.NONE)` and `index_constituent_timeseries(assetid, "S&P 500", ...)`. Verify all arguments against the installed package version before export.

Import the permitted export into this Linux workspace. Do not install NDU here or assume that installing the Python package creates a working data service. **The historical cap requirement and dividend payment dates still need another validated source or an explicitly narrower protocol.** Effective membership history alone also does not prove original announcement timestamps.

## 7. Decision and next action

The full experiment is not data-ready. The next useful milestone is a documented schema/coverage sample, not a backtest result:

1. Preserve the completed public probes and their limits. Further attempts at an authenticated dictionary or dataset require supported credentials/entitlements; FMP's unresolved failure remains a network prerequisite, not evidence of subscription status.
2. If existing institutional exports are available, audit WRDS/CRSP components first. Otherwise request a sample and quote for Sharadar SEP, DAILY, SP500, ACTIONS and TICKERS, adding SF1/SFP when needed; verify the exact entitlement and field coverage before buying.
3. Use the implemented Yahoo diagnostic for price-ingestion development. Next audit exchange sessions and adjustment/action semantics against authoritative evidence; do not silently turn it into a current-constituent backtest.
4. Use Norgate only as an authorized Windows export option with its historical-cap gap explicitly resolved.
5. Populate and validate the shared contract before the strategy engine consumes any market data. Keep documented, sampled, entitled, coverage-audited and PIT-audited statuses separate.

No route should be described as “connected,” “complete” or “point-in-time verified” solely because its package imports or its documentation is reachable.
