> Archived research document. Historical scope and status are retained; see the [current validation case](../../studies/validation-study.md).

# Reproducible price-ingestion diagnostic

The diagnostic fetches daily SPMO and SPY observations directly from Yahoo's public chart endpoint. It preserves the response, checks its structure and values, and can replay the same bytes offline. It does not implement the strategy or establish research-grade coverage. Python 3.12+ and its standard library are sufficient; yfinance is not used by this script.

## Acquire a fixed historical request

From the repository root:

```bash
python3 scripts/ingest_diagnostic.py
```

The default request uses the experiment configuration: **December 1, 2023 through October 2, 2026, inclusive**, for SPMO and SPY. The API's exclusive upper bound is October 3 at midnight in America/New_York. Date conversion uses the IANA timezone, including daylight-saving changes. Requests are sequential, with a timeout and response-size limit, and retain normal TLS/proxy verification.

For a smaller diagnostic:

```bash
python3 scripts/ingest_diagnostic.py --symbols SPMO SPY --start 2026-09-01 --end 2026-10-02
```

Each invocation creates a unique run ID and reports its raw and processed directories. Nothing overwrites an earlier run. The default locations are ignored by Git:

| File | Contents |
|---|---|
| `data/raw/yahoo/<run-id>/<symbol>.json` | Exact successful HTTP response bytes |
| `data/raw/yahoo/<run-id>/manifest.json` | Request identity, capture time, HTTP status, byte count, SHA-256, script SHA-256 and failures |
| `data/processed/yahoo/<run-id>/<symbol>.csv` | Vendor timestamps, New York dates, OHLC, volume and separate adjusted close |
| `data/processed/yahoo/<run-id>/<symbol>.events.json` and `.events.csv` | Separate vendor split/dividend events; event dates are not verified payment dates |
| `data/processed/yahoo/<run-id>/quality_report.json` | Missingness, observed bounds, structural/value errors and unresolved research warnings |
| `data/processed/yahoo/<run-id>/manifest.json` | Raw manifest hash and hashes of derived outputs |

`--data-dir` selects a different private output root. Keep that directory out of source control. Failed captures are recorded with safe error codes; server error bodies and credential-bearing URLs are not logged. An HTTP failure is not a successful response capture.

## Replay without network access

Use the raw directory reported by a completed invocation:

```bash
python3 scripts/ingest_diagnostic.py --raw-dir data/raw/yahoo/<run-id>
```

Replace `<run-id>` with the actual directory name. Replay verifies the saved request identity, each response's hash and byte count, then writes a new run from those same bytes. Explicit symbol/date overrides must match the saved request. Replay does not contact Yahoo and does not refresh observations. Hash checks detect changes relative to the stored manifest; they are not a provider signature or an independent authenticity guarantee.

The output manifests differ because the replay has its own run ID and capture provenance. Normalized CSV/event files and the quality report should reproduce exactly when the parser is unchanged. The public summary exporter verifies these hashes and the replay's source-manifest identity before reporting successful reproduction:

```bash
python3 scripts/export_ingestion_summary.py \
  --processed-dir data/processed/yahoo/<original-run-id> \
  --replay-dir data/processed/yahoo/<replay-run-id> \
  --output site/data/ingestion-summary.json
```

Only dates, counts, hashes, status and limitations are exported. Price, volume and event-value rows remain private. The site displays this saved snapshot; it does not make market-data requests or refresh on every visit.

## Meaning of the checks

The parser checks response shape, vendor identity, USD currency, daily interval, timezone, array lengths, finite positive prices, nonnegative volume, OHLC bounds, duplicate/nonmonotonic timestamps and dates, requested date limits, and event structure. Null values remain blank in CSV and cause diagnostic failure; they are never forward-filled. The report distinguishes field missingness from other invalid values. Agreement between the two symbols' observed dates is also checked.

Exit status **0** means these diagnostic checks passed. Exit status **1** means acquisition, parsing, data checks or replay verification failed; inspect the saved manifest and quality report. Invalid command-line syntax returns **2**. Passing is not permission for the strategy engine to consume the data.

The following remain unverified even after a successful replay:

- Exchange-calendar completeness, including exceptional closures. Matching SPMO/SPY dates and a large row count cannot prove there are no missing sessions.
- Yahoo OHLC adjustment conventions and executable raw opening prices. The CSV's `open` is a vendor field, not a verified `raw_open`.
- Dividend payment dates, corporate-action completeness and benchmark total-return reconstruction.
- Historical index membership, permanent IDs, security-class market-cap vintages and other point-in-time inputs for the four strategy arms.
- Rights to use and redistribute the underlying observations. This repository publishes the diagnostic code and aggregate checks, not vendor market bars.

`research_ready` always remains false. A fixed historical cutoff avoids silently adding the latest partial trading day to this experiment. Custom date requests can still include incomplete vendor bars; the script reports missing values rather than repairing them.

## Offline regression checks

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Fixtures exercise invalid schemas, missing fields, ordering, values, action separation, daylight-saving dates, immutable output creation and replay integrity. They use no provider credentials or network calls. These are ingestion tests, not portfolio-accounting or backtest tests.
