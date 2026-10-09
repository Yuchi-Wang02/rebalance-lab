# Original stock experiment: data-access audit

**The original four-arm stock experiment is not complete. Its acquisition status is `acquisition_not_complete`.** This audit explains the observed input gaps; it contains no stock-strategy performance result. A separately declared ETF pilot can produce real market results, but cannot substitute for the original experiment.

The public probes below were repeated on **2026-10-09 at 02:16:30 UTC** using normal unauthenticated HTTPS requests. Exact URLs, response hashes, statuses and findings are in the [machine-readable audit](../../results/original-data-audit.json). HTTP success establishes access to that response, not a complete, accurate or point-in-time dataset. No finance-provider credential binding was found in the process environment; secret values were not inspected. No subscription was purchased, restriction bypassed or raw market time series committed.

## What is missing and why it matters

| Required input | Observation | Severity and consequence |
|---|---|---|
| Complete historical membership and timing | The accessible historical CSV ends on August 18, 2026. A later current snapshot contains a different set of members. Neither supplies a complete announcement-time event ledger. | **Critical.** Carrying the old list forward misses changes; applying the new list backward creates look-ahead. |
| Stable security identity | The historical CSV has only `date` and `tickers`. The current snapshot includes issuer CIKs, which are not share-class identifiers. | **Critical.** Ticker changes, reused tickers and multiple classes cannot be joined safely without additional mappings. |
| Historical class capitalization | Yahoo share histories lack availability/vintage fields. Alphabet's two tickers return the same latest share count, while its original filing distinguishes the classes. Selected SEC facts are accessible, but a complete class-level panel is not built. | **Critical.** Issuer shares assigned to each class distort weighting; backfilled later disclosures introduce look-ahead. |
| Prices for former constituents | The dated Yahoo ANSS chart request returns 404, although an official filing documents its 2025 acquisition. | **Critical.** Excluding unavailable former members introduces survivorship bias. |
| Cash and stock event ledger | Selected SEC merger terms are available; a complete dividend ex/pay-date and merger/delisting settlement ledger is not. | **Critical.** Wrong cash availability or successor holdings change reinvestment and subsequent trades. |
| Real event accounting | The current synthetic engine has not been accepted against every required real merger, spinoff and delisting case. | **Critical.** More source data alone would not complete engine acceptance. |

## Membership: accessible, but incomplete for this protocol

The [pinned fja05680 historical CSV](https://raw.githubusercontent.com/fja05680/sp500/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7/S%26P%20500%20Historical%20Components%20%26%20Changes%20%28Updated%29.csv) returned **HTTP 200**. It contains **2,720 snapshots from January 2, 1996 through August 18, 2026**, with only `date` and `tickers` columns. The repository has an [MIT license](https://github.com/fja05680/sp500/blob/a2430f2af0c79ddf0748e91de11bdeb1616ab5a7/LICENSE). Its SHA-256 is:

```text
36326709d46d6cd25834de5df457b16f5f96fad3a06b9beac28f7b88aa0b0d54
```

The [pinned datasets current CSV](https://raw.githubusercontent.com/datasets/s-and-p-500-companies/05a928d03abe805698f08446c355c3718c2d55dd/data/constituents.csv) also returned **HTTP 200**, with **503 rows**. The repository snapshot was updated September 21, 2026 and declares [PDDL for its data](https://github.com/datasets/s-and-p-500-companies/blob/05a928d03abe805698f08446c355c3718c2d55dd/datapackage.json). Compared with the final historical snapshot, it adds **BE, ILMN and P** and removes **BLDR, TAP and TTD**. This is evidence of a coverage gap, not evidence of each change's announcement or effective date. The current file's `Date added` column and a Git commit timestamp cannot reconstruct the missing event ledger.

The [direct Wikipedia request](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies) failed at **proxy CONNECT 403**, before an origin response. No alternate transport or access-control bypass was attempted.

## Capitalization: public filing evidence is useful, but not a finished panel

The exact dated Yahoo share-count requests in the JSON audit returned **HTTP 200** for AAPL, GOOG and GOOGL. The AAPL response contains 175 observations through August 5, 2026. Its record structure is `meta`, `timestamp` and `shares_out`, without a disclosure timestamp or revision vintage. The two Alphabet ticker responses have the same latest share count; treating that as each class's count is inconsistent with the issuer's class disclosures.

Public SEC sources provide genuine supporting evidence:

- [Apple companyfacts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json), **HTTP 200**, includes share facts with observation end, filing date and accession. Those fields support a conservative, explicitly lagged last-reported-share series; they do not establish actual shares outstanding on every trading day.
- [Alphabet's original Q2 2026 10-Q](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm), **HTTP 200**, reports July 15 class shares separately: **5.868 billion A, 0.835 billion B and 5.527 billion C**. Its inline XBRL uses separate class contexts. [SEC submissions](https://data.sec.gov/submissions/CIK0001652044.json), also **HTTP 200**, records acceptance at **2026-07-23T01:15:54Z**. Using the observation date as if the filing were already known would be wrong.

A full SEC-derived route would require historical issuer/security mappings, class-context parsing, original filing timestamps, restatement handling and coverage checks at every signal. That implementation and audit are not complete. A chosen last-reported-share convention must remain explicit; it must not be described as a verified daily economic capitalization series.

The [Sharadar DAILY sample request](https://data.nasdaq.com/api/v3/datatables/SHARADAR/DAILY.json?ticker=AAPL&date=2025-03-31&qopts.per_page=5) returned **origin HTTP 403**, error `QEPx04`, requiring a valid API key. The [FMP historical-cap request](https://financialmodelingprep.com/stable/historical-market-capitalization?symbol=AAPL) returned **origin HTTP 401**, “Invalid API KEY.” FMP is reachable in this recheck; the earlier network failure is not its current status. No authenticated coverage or entitlement was tested.

## Corporate actions: confirmed examples expose the accounting requirement

The dated [Yahoo ANSS chart request](https://query1.finance.yahoo.com/v8/finance/chart/ANSS?period1=1701388800&period2=1790985600&interval=1d&events=div%2Csplits) returned **origin HTTP 404**, “No data found, symbol may be delisted.” It does not provide the requested historical prices.

Two original SEC filings returned **HTTP 200**:

- [ANSS completion 8-K](https://www.sec.gov/Archives/edgar/data/1013462/000114036125026141/ef20052066_8k.htm): the acquisition completed July 17, 2025; each eligible common share became the right to **0.3399 SNPS shares plus $199.91 cash**, subject to the filing's terms.
- [Juniper completion 8-K](https://www.sec.gov/Archives/edgar/data/1043604/000119312525154400/d912160d8k.htm): the acquisition completed July 2, 2025; each eligible common share became the right to **$40 cash**, subject to the filing's terms.

These are useful final-term records, not permission to assume same-day spendable cash. Complete event coverage, consideration eligibility, actual settlement timing and independent share/cash/receivable reconciliation are still required. A merger completion date is not automatically a cash payment date. The [Nasdaq SPMO dividend endpoint](https://api.nasdaq.com/api/quote/SPMO/dividends?assetclass=etf) failed at **proxy CONNECT 403**; no payment-date records were obtained there.

## Minimum input that would unblock the original study

An **authorized export or entitled feed**, from one or several sources, needs to provide:

1. A verified initial S&P 500 security-class universe and complete changes through October 2, 2026, with stable IDs, ticker history, effective dates and historical announcement/known-at evidence.
2. Raw executable opens/closes and separately documented signal-price adjustments for current and former members, with all required exchange sessions and warmup from December 1, 2023.
3. Historical class-level capitalization or validated class shares plus prices, with units, observation dates, historical availability, vintage provenance and an explicit staleness convention at every signal.
4. Complete splits, dividends and merger/delisting records, including ex/pay dates, successor securities, final consideration and settlement timing sufficient to resolve relevant events.

No particular provider or new purchase is required. A permitted local export can satisfy the acquisition step. It must then pass the [event-led acceptance sample](acceptance-sample.md), full coverage checks and independent engine reconciliation before any original stock-strategy result is labeled complete. The separate ETF pilot should be evaluated on its own declared question, input conventions and limitations.
