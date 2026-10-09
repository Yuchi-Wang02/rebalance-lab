# Data sources and connection plan

**No provider is connected and no market dataset has been validated.** This document separates documentation that was actually read from candidate datasets and untested access. The machine-readable catalog is [data-sources.json](../configs/data-sources.json).

The recommended order is: use an existing institutional entitlement if one is available; otherwise verify the required commercial data components before choosing a subscription. Use Yahoo/yfinance only for a no-cost diagnostic. Norgate is a conditional Windows export route, not a native connection for this Linux workspace. No purchase, signup, credential request, or authenticated data download has been performed.

## 1. What was verified

Source inspection date: 2026-10-08, America/New_York. Network observations describe this environment at inspection time, not permanent availability.

| Route | Documentation actually read | Market API/sample | Authenticated full coverage | Point-in-time integrity |
|---|---|---|---|---|
| Yahoo/yfinance | Maintainer README and download source | Yahoo chart request failed at proxy CONNECT with 403 | Not established | Not established |
| WRDS/CRSP | Official WRDS SDK README and connection source | No database query | No entitlement or coverage verified | Membership, revisions and delisting contract not established |
| Nasdaq Data Link / Sharadar | Official SDK README, configuration and pagination source | No table request completed | No entitlement or coverage verified | Table-specific contracts not established |
| Norgate | Provider-published Python package description | No NDU connection or export | No subscription verified | Historical membership is documented; announcement-time correctness and historical cap coverage are not established |

Official product documentation hosts for Nasdaq, WRDS, CRSP and Norgate returned `Tunnel connection failed: 403 Forbidden` through the existing HTTPS proxy. The yfinance documentation host and an FMP documentation candidate did too. These responses occurred before an origin response; they do **not** prove a missing subscription, an invalid URL, an unavailable dataset, or bad credentials. Public maintainer documentation on allowed GitHub and PyPI hosts was readable. No proxy, TLS, authentication or network restriction was bypassed.

“Historical data,” “survivorship-bias-free” and “point-in-time” are different claims. A table indexed by a past date does not establish when a record first became available or whether later revisions replaced the original value.

## 2. Shared acquisition contract

Provider exports belong in ignored `data/raw/<provider>/<snapshot-id>/`; normalized tables belong in ignored `data/processed/<snapshot-id>/`. These are planned locations, not evidence that data exists. Keep original files immutable. Publish only the manifest and outputs permitted by the data license.

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

The chart request to `https://query1.finance.yahoo.com/v8/finance/chart/SPMO?range=5d&interval=1d` failed at the proxy. No bars were returned. The SDK may contact additional Yahoo hosts for data or session handling; permit only required documented destinations and retry after a meaningful network change. Do not treat a connection failure as a reason to switch to undocumented relay services.

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

Do not hard-code a remembered legacy membership or return table name and assume it is the current entitled product. The publicly attempted [WRDS S&P 500 membership guide](https://wrds-www.wharton.upenn.edu/pages/grid-items/downloading-sp-500-index-constituents/) and [CRSP documentation portal](https://www.crsp.org/products/documentation/) were blocked before origin response, so their present contents were not verified.

Before implementation, establish whether the selected return field already incorporates delisting returns, or whether a separate delisting event/return must be combined. Never apply both treatments. Verify share-count units, opening-price availability, permanent-ID joins, ETF coverage and membership timing from that release's dictionary and a small exported sample. Institutional access alone does not prove historical announcement-time or revision-vintage correctness.

## 5. Route C: Nasdaq Data Link / Sharadar components

**Candidate commercial HTTPS route when institutional access is unavailable.** The official SDK interface is verified; product coverage and point-in-time claims are not. Do not select or purchase a plan until the component gaps below are resolved.

Verified sources:

- [Official Python client README](https://github.com/Nasdaq/data-link-python/blob/main/README.md) documents `nasdaqdatalink.get_table`, the `NASDAQ_DATA_LINK_API_KEY` environment binding, and that unauthenticated calls may return limited/sample data.
- [Official configuration source](https://github.com/Nasdaq/data-link-python/blob/main/nasdaqdatalink/api_config.py) specifies the API base `https://data.nasdaq.com/api/v3` and TLS verification enabled.
- [Official table pagination source](https://github.com/Nasdaq/data-link-python/blob/main/nasdaqdatalink/get_table.py) handles cursor pagination through `paginate=True`; an initial page alone is not complete data.

The following are **candidate product/table mappings to validate**, not inspected field contracts:

| Candidate table | Intended component | Required confirmation |
|---|---|---|
| `SHARADAR/SEP` | Daily stock prices | Universe coverage, retained delisted securities, split/dividend adjustment, raw-open availability and exact dates |
| `SHARADAR/DAILY` | Historical daily market-cap observations | Field units, class versus issuer cap, shares timing, revisions and availability timestamp |
| `SHARADAR/SF1` | Supporting fundamentals/share observations where needed | Dimension semantics, as-reported versus restated values, filing/publication timestamps and availability lag |
| `SHARADAR/TICKERS` | Identifier metadata and coverage inventory | Permanent-ID and historical-ticker coverage; this is not by itself proof of index membership history |

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

Once the origin is reachable, obtain the table dictionary and confirm the filters before using this example. Store access keys only in supported secure settings; never paste a real key into the example, output, request log or repository. A valid API key does not establish entitlement to all four tables.

**Unresolved membership dependency:** obtain a licensed S&P historical constituent/event source, or evaluate an alternate membership-events provider. An [FMP historical S&P 500 constituents documentation candidate](https://financialmodelingprep.com/developer/docs/stable/historical-sp-500-constituents) was also proxy-blocked; its schema, API path, history completeness, announcement dates and subscription tier are unverified. It is not a connected fallback. An event feed must reconstruct a validated starting snapshot and all subsequent changes; today's constituents plus an incomplete events list is insufficient.

The attempted [Sharadar collection documentation](https://docs.data.nasdaq.com/docs/collections-sharadar) and [SEP product documentation](https://data.nasdaq.com/databases/SEP/documentation) did not reach the origin. No claim about full historical coverage, raw prices, field units or PIT correctness is grounded in those unread pages.

## 6. Route D: Norgate Windows export

**Conditional route if an appropriate subscription and supported Windows machine already exist.** The provider's [PyPI package description](https://pypi.org/project/norgatedata/) was read in full through its [package metadata endpoint](https://pypi.org/pypi/norgatedata/json).

The inspected documentation explicitly states:

- Norgate Data Updater (NDU) must be installed and running on Windows; the package requires an active subscription. It documents Windows-VM and WSL arrangements, not a stand-alone native Linux NDU service.
- Historical index constituents require a Stocks Platinum or Diamond subscription. The documented `index_constituent_timeseries` example includes `S&P 500`.
- `assetid` is a unique unchanging Norgate ID. Use it rather than ticker alone.
- Price adjustment defaults to `TOTALRETURN`; available modes include `NONE`, `CAPITAL`, `CAPITALSPECIAL` and `TOTALRETURN`. Padding can repeat old closes and must be explicitly disabled for this experiment.
- Its dividend column is dated **the day before ex-date**, depends on the chosen adjustment mode, and omits dividends already included by that adjustment. It is not a pay-date cash ledger.
- `fundamental(symbol, "mktcap")` and `sharesoutstanding` are explicitly documented as **current fundamentals**. They do not establish a historical point-in-time market-cap series.

On an authorized supported Windows machine, export an asset-ID-based universe including relevant delisted securities, index membership series, price series with separate explicit `NONE` and `CAPITAL` modes, actions and extraction metadata. For example, the documented entrypoints are `price_timeseries(..., stock_price_adjustment_setting=..., padding_setting=PaddingType.NONE)` and `index_constituent_timeseries(assetid, "S&P 500", ...)`. Verify all arguments against the installed package version before export.

Import the permitted export into this Linux workspace. Do not install NDU here or assume that installing the Python package creates a working data service. **The historical cap requirement and dividend payment dates still need another validated source or an explicitly narrower protocol.** Effective membership history alone also does not prove original announcement timestamps.

## 7. Decision and next action

The full experiment is not data-ready. The next useful milestone is a documented schema/coverage sample, not a backtest result:

1. Retry only affected public checks after supported network settings have changed; record whether failure is proxy, origin, authentication or entitlement.
2. If existing institutional exports are available, audit WRDS/CRSP components first. Otherwise verify Sharadar product contracts plus a historical membership source before selecting a commercial route.
3. Run the Yahoo diagnostic only as a price-ingestion check. It must not silently become a current-constituent backtest.
4. Use Norgate only as an authorized Windows export option with its historical-cap gap explicitly resolved.
5. Populate and validate the shared contract before the strategy engine consumes any market data. Keep documented, sampled, entitled, coverage-audited and PIT-audited statuses separate.

No route should be described as “connected,” “complete” or “point-in-time verified” solely because its package imports or its documentation is reachable.
