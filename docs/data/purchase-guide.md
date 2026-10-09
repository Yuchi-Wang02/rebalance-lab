# Where to obtain the original experiment's data

**Pilot update:** authorized Sharadar membership, issuer metrics and corporate-action records now support a completed [100-issuer stock pilot](../studies/stock-pilot.md), paired with free Yahoo price proxies. No additional price subscription was needed for that limited experiment. The requirements below concern the original full-universe protocol; they are not instructions to buy more data before inspecting the published pilot.

**Recommendation: request a Sharadar sample and a quote for the exact tables below first.** Its own `SP500` table is a newly verified candidate for historical membership. An additional membership supplier is conditional, not automatically required. If an existing institutional WRDS subscription is available, inspect that entitlement in parallel. **Norgate Platinum is a priced alternative for membership and prices, but buying it alone will not complete this experiment.**

Checked **October 8, 2026, America/New_York**. The [procurement evidence](../../results/data-purchase-audit.json) records official sources, hashes and the limits of each observation. No account was created, subscription purchased or provider contacted. The completed [ETF pilot](../studies/sector-etf-pilot.md) is separate from these requirements.

## 1. First commercial lead: Sharadar on Nasdaq Data Link

Start at the official [Sharadar publisher page](https://data.nasdaq.com/publishers/SHARADAR). Ask which current subscription includes these exact tables; do not assume that buying equity prices alone includes them all.

| Table | Intended role | Evidence obtained |
|---|---|---|
| `SHARADAR/SEP` | Stock prices, including former constituents | Official metadata: “Sharadar Equity Prices” |
| `SHARADAR/DAILY` | Historical capitalization | Official metadata: “Daily Metrics”; class scope and historical availability still need a sample |
| `SHARADAR/SP500` | Historical S&P 500 membership | Official metadata: **“S&P500 Current and Historical Constituents”** |
| `SHARADAR/ACTIONS` | Corporate actions | Official metadata: “Corporate Actions”; payment/settlement coverage still needs a sample |
| `SHARADAR/TICKERS` | Identifier mappings | Official metadata: “Tickers and Metadata” |
| `SHARADAR/SF1`, if needed | Filing-linked shares and availability evidence | Official metadata: “Core US Fundamentals” |
| `SHARADAR/SFP`, if needed | SPMO/SPY benchmark prices | Official metadata: “Sharadar Fund Prices”; actual ETF coverage still needs confirmation |

All seven metadata endpoints returned HTTP 200. All except TICKERS are marked premium. Metadata exposes names, filters and keys but **no field definitions or market rows**. Requests for actual SP500, ACTIONS and SFP samples returned HTTP 403 requiring a valid API key. A free account or key must not be confused with a premium-data entitlement.

The [equity-price](https://data.nasdaq.com/databases/SEP), [fundamental](https://data.nasdaq.com/databases/SF1) and [fund-price](https://data.nasdaq.com/databases/SFP) pages were reachable. Their JavaScript application did not expose readable prices here, and its public application asset was blocked by this environment's proxy. **Current Sharadar prices and exact bundle contents are therefore unverified. No estimated subscription price is quoted.**

Before paying, request a small authorized export for AAPL, GOOG/GOOGL, ANSS, JNPR, a 2026 membership change, SPMO and SPY. These cases distinguish a useful research feed from a prices-only subscription. Verify:

- Coverage from **December 1, 2023 through October 2, 2026**, including securities that disappeared during the period.
- Raw opening prices and documented split adjustment; class-specific historical capitalization and information-availability dates.
- Complete membership changes, with effective dates distinguished from announcement dates.
- Dividend ex/payment dates, merger cash-and-stock consideration, successor IDs and actual settlement timing. A generic action date is insufficient.
- Private export rights and permission to publish aggregate research results on GitHub Pages.

This is a concrete candidate for a single-provider route, not a finding that every requirement is already covered. If a critical field is absent, identify its supplemental source before buying the main package.

## 2. Priced alternative: Norgate US Stocks Platinum

The official [package comparison](https://norgatedata.com/stockmarketpackages.php) displayed:

| Package | Six months, USD | Twelve months, USD | Relevant distinction |
|---|---:|---:|---|
| **US Stocks Platinum** | **346.50** | **630.00** | Current and delisted securities, historical index constituents; price history back to 1990 |
| US Stocks Diamond | 433.13 | 787.50 | Extends price history back to 1950 |

For our December 2023 start, Diamond adds no necessary history. Silver/Gold lack the required combination of historical constituents and delisted coverage. Use the official [order form](https://norgatedata.com/orderform.php) if this component is selected; these are observed USD prices, with final checkout terms controlling.

The [three-week trial](https://norgatedata.com/freetrial.php) includes only **two years** of history. It can test installation and formats, but an October 2026 trial cannot cover our December 2023 warmup. The provider explicitly says it does not supply additional trial history or custom samples outside that window.

Norgate Data Updater requires Windows. Its documented route here is a Windows export followed by private Linux analysis. Its current [FAQ](https://norgatedata.com/faq.php) and [EULA](https://norgatedata.com/subscribe/eula.php) permit personal private cloud analysis during the subscription; raw data cannot be published. They require deletion of licensed exports, normalized data, metadata and backups when the subscription ends, while qualifying derived research results may be retained.

**Why this is not the first standalone purchase:** the [data FAQ](https://norgatedata.com/data-package-faq.php) says historical fundamentals, merger/acquisition terms and economic delisting proceeds are unavailable. Current market capitalization combines share classes. Dividend records do not establish payment dates, and historical corrections are not versioned. Historical class capitalization and event settlement would still require another source. The existing raw-price protocol must not silently replace terminal consideration with a sale at the last quote.

## 3. Institutional route: WRDS with named underlying datasets

If a university, employer or lab already subscribes, contact its data librarian first. Ask specifically for **CRSP daily stock data, distribution and delisting records**, plus the entitled **historical S&P membership source** such as the applicable Compustat/S&P offering. WRDS is the delivery platform; access to one product does not establish access to all of them.

Official entry points are [WRDS contact](https://wrds-www.wharton.upenn.edu/pages/about/contact-wrds/), [CRSP on WRDS](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/center-for-research-in-security-prices-crsp/) and [S&P Global / Compustat on WRDS](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/sp-global-market-intelligence/). Institutional pricing was not displayed in the inspected material; request a quote if access is not already held.

An actual [public CRSP demonstration download](https://wrds-www.wharton.upenn.edu/demo/crsp/data/) returned **24 monthly records for two securities in 2006**. The demo form lists identifiers, share counts, distributions, payment dates and delisting fields. This is useful schema evidence; it neither supplies the required daily/current history nor proves a subscription's complete field coverage. Raw demo rows are not republished here.

## Ready-to-send sample and quote request

> I am conducting personal research on S&P 500 momentum portfolios and need data from 2023-12-01 through 2026-10-02, including former constituents. Please quote the smallest subscription covering historical constituents, unadjusted daily OHLC, stable security-class identifiers, historically available class-level shares or market capitalization, and corporate actions with dividend payment dates and merger/delisting cash or stock settlement. For Sharadar, please confirm entitlement to SEP, DAILY, SP500, ACTIONS and TICKERS, with SF1/SFP if needed. Please provide a small authorized sample and field dictionary covering AAPL, GOOG/GOOGL, ANSS's 2025 merger, JNPR's 2025 cash acquisition, a 2026 index membership change, SPMO and SPY. Distinguish effective dates from publication dates and explain historical revisions. I need private CSV/API export and permission to publish aggregate results and charts, without redistributing raw data.

Send that request through the provider's official sales/support channel after reviewing its current terms. It has **not** been sent on the user's behalf. Store any issued key in secure environment settings, never in chat or Git. Once an authorized sample exists, the next step is the [documented acceptance check](acceptance-sample.md), followed by full extraction and the original stock experiment.
