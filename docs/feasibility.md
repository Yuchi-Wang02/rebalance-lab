# Feasibility, data contract, and release gates

Protocol v0.2 is a research specification. **No backtest engine is implemented and no full research dataset has passed an audit. A small unauthenticated Yahoo price request succeeded; that diagnostic does not satisfy the experiment’s data contract.** There are no performance results. Reading provider documentation or passing configuration checks does not change that status.

Daily research on several hundred securities is technically manageable. The limiting work is obtaining historical constituents, usable opening prices, corporate actions, and historical shares with defensible availability dates. See the [source and connection plan](data-sources.md) for candidate providers, access requirements, and unresolved coverage. A licensed export imported into this cloud workspace may be more practical than a native connection; provider access and redistribution rights must be verified separately.

## What the data must support

The [experiment design](experiment-design.md) defines four arms: S12 and M12 use 12–1 momentum; SMIX and MMIX use the 50/30/20 blend. Within each signal pair, only the selection frequency changes. The primary contrast is M12−S12; MMIX−SMIX is the prespecified replication. Actual SPMO and SPY provide product context, not evidence that frequency alone caused a difference.

All four arms select the top 75 eligible positive-score securities, with no selection buffer, trend filter, or weekly risk overlay. Weights are proportional to `positive score × sqrt(security-class total market capitalization)`. Normalize the selected weights and iteratively redistribute amounts above the 8% security cap; retain only amounts that cannot be allocated within the cap. There is **no N/75 equity budget**. With no eligible securities, hold cash. A supplier data gap is an audit failure, not permission to omit a security quietly.

The performance window is **2025-12-31 close through 2026-10-02 close**, with established holdings:

- Seed every account with cash at the initial signal on **2024-12-31** and trade at the first exchange-session open in 2025.
- Run the complete protocol through 2025 to establish each arm's own holdings and cash. Request prices from **2023-12-01** and verify at least **253 market-session price points** through the initial signal. The requested start date alone does not prove coverage.
- At 2025 year-end, retain holdings, cash, receivables, and pending events; normalize NAV for measurement without liquidating or rebuilding the portfolio. A December signal may produce its usual January trade.
- Report opening holdings and cash for the measured year. Burn-in costs are already reflected in the anchor NAV; do not charge them again as 2026 costs. End at the final close without a hypothetical liquidation.

This is a retrospective 2026 experiment. Earlier knowledge of that year's market influenced the research question; a correct historical-data process does not make the window genuinely unseen out-of-sample evidence.

## Historical data contract

Use stable `security_id` values, not current tickers, to join tables. Store timestamps with time zones, preferably UTC; interpret sessions using the exchange calendar and `America/New_York`. Distinguish `effective_at` from `known_at`: a record must be known by the decision time and effective for the state being reconstructed. `downloaded_at` is provenance, not proof of historical availability.

| Dataset | Minimum fields | Acceptance condition |
|---|---|---|
| Security master | `security_id`, ticker history, exchange, share class, issuer ID, currency, validity intervals | Resolve symbol changes, code reuse, multiple share classes, mergers, and delisted securities without accidental joins. |
| Index membership | `security_id`, `effective_from`, `effective_to`, `known_at`, source/version | Rebuild the historical S&P 500 universe. Preserve removals; do not backfill today's members. Membership history does not by itself prove announcement-time availability. |
| Raw prices | `security_id`, session, unadjusted OHLC, volume, currency, availability time, price/status flags | Unique security/session keys; valid currency and units; distinguish trades, quotes, halts, and missing observations. A bid/ask midpoint or stale last price is not an executable opening trade. |
| Corporate actions | Event ID, security ID, type, effective/known times, split ratio; dividend amount, ex-date and payment date; merger/spinoff terms | Reconstruct shares, receivables, and cash without double adjustments. Identify revisions and unresolved terms. |
| Delistings | Last trade date, event date, reason, final cash or security consideration, settlement date, source | Keep failed and removed securities. Do not delete them or assume liquidation at the last observed close. |
| Historical shares / capitalization | Security-class shares outstanding or same-basis total cap, effective/known times, currency, source | Use only contemporaneously available information. Match split units and class coverage; track staleness. Do not substitute free-float cap or company-wide cap assigned repeatedly to each class. |
| ETF reference data | SPMO/SPY raw prices and distributions, or a documented total-return series; return convention and source | Identify market-price versus NAV returns and reinvestment timing. Use the same close-to-close measurement dates. A closing total-return series cannot supply raw opening fills. |
| Exchange calendar | Session, opening/closing timestamps, holiday and early-close flags, version | Use actual sessions, including daylight-saving changes. Lookbacks count market sessions, not the last available rows for an individual stock. |

An API field named “historical market cap” does not establish point-in-time correctness. Check whether shares were revised retrospectively, whether class-level shares are available, and what timestamp determines availability. A last-publicly-reported-shares construction must state its publication lag and staleness policy; it must not be presented as a verified daily outstanding-share series.

## Prices, cash, and trading assumptions

Signals use **split-adjusted closing prices excluding cash-dividend reinvestment**, calculated after the scheduled close. Trades use the **next session's raw opening price**. Build and validate the signal series from documented price and action inputs; do not mix a total-return adjusted close with a raw opening price.

The ledger uses raw prices and actual share quantities. Splits change quantities; dividends create a receivable on the ex-date and spendable cash on payment. Count each dividend exactly once. Follow the common dividend reinvestment and event-order rules in the [protocol](experiment-design.md); a vendor total-return convention is a separately identified reference if its timing differs.

Opening fills are an idealized fractional-share model, not verified execution capacity. Base costs are **5 bps per side**, with **0/5/10/25 bps** reported for every arm. Apply costs to absolute executed notional, including initial formation and reinvestment trades. Keep cash nonnegative, charge only actual fills, and do not finance purchases with an unfilled sale. Cash earns zero interest by assumption; results are pre-tax USD without leverage or shorting.

Halts and missing opening prices produce unfilled orders, not fabricated fills. A carried last price may serve only as a flagged valuation estimate. Delistings and mergers require event-specific settlement; unresolved material values block a precise performance claim. Record target-versus-actual holdings and use the protocol's cancellation/retry rules consistently.

ETF prices already reflect the fund's operating expenses; do not subtract the expense ratio a second time. Report which external trading costs and dividend conventions apply to any simulated ETF account versus the published ETF reference series.

## Permitted research tiers

| Tier | Permitted use | Release restriction |
|---|---|---|
| Audited historical-data research | Four-arm protocol using accepted historical membership, prices, actions, and shares | Publish comparisons only after the data and ledger gates pass. Disclose remaining approximations and this window's retrospective status. |
| Named equal-weight variant | A separate experiment if usable historical shares cannot be obtained | It removes the capitalization requirement, not the historical-universe or corporate-action requirements. It cannot silently replace the original four arms or inherit their conclusions. |
| Engineering prototype | Debug interfaces with current members or incomplete historical inputs | Label `data_track=prototype` on every output. Today's members introduce survivorship bias; today's cap introduces look-ahead bias. Do not rank strategy performance from this tier. |
| Synthetic fixture | Test deterministic accounting and timing cases | Label `data_track=synthetic`. Passing synthetic checks does not validate market data or profitability. |

No tier may disguise missing data as zero returns. Preserve unavailable states and explain the specific requirement that prevents progression.

## Work and acceptance gates

| Gate | Deliverable | Required evidence |
|---|---|---|
| 1. Freeze specification | Versioned four-arm configuration and common event rules | Pairwise frequency controls differ only in their schedule; time, signal, selection, weighting, and cash rules are deterministic. |
| 2. Establish access | Source registry, authorized extraction/import steps, small sample | Confirm account entitlement, historical coverage, field semantics, platform compatibility, and publication rights. Documentation access is not dataset access. |
| 3. Audit inputs | Normalized tables, source hashes, coverage and exception reports | Required burn-in and signal history are present; membership, identifiers, opening prices, actions, and historical cap reconcile. No unexplained critical gaps or silent omissions. |
| 4. Validate engine | Deterministic accounting and timing checks | Splits conserve value; dividends and fees are counted once; future information is inaccessible; cash and quantities reconcile; halted orders cannot fill. None of these engine checks is implemented yet. |
| 5. Reconcile market run | Inspectable fills, positions, NAV, and reference comparisons | Trace representative trades and events to sources. Explain material differences between reconstructed ETF returns and published reference conventions. |
| 6. Publish results | All four arms and cost scenarios, diagnostics, limitations | Reproduce from the same code/config/data versions. Present primary, replication, and interaction contrasts without selecting only favorable outcomes. |

A future paper track begins after a frozen version is published, with signals recorded before their intended fills. It must not backfill predictions or relabel the retrospective 2026 run as prospective validation.

## Output contract

These are planned outputs, not existing results. A `run_id` identifies **one arm × one cost scenario × one data snapshot × one code/config version**. Every combination receives a distinct ID; the manifest maps it to `strategy_id`. Keep burn-in and measurement periods separately identified.

| Artifact | Key fields / purpose |
|---|---|
| `run_manifest.json` | Run/strategy IDs, protocol and code versions, config hash, data track, source-manifest hash, burn-in and measurement dates, cost scenario, currency, audit status, warnings. |
| `source_manifest.csv` | Provider, dataset/version, source URI without credentials, extraction time, coverage, availability semantics, license/reference, redistribution permission, raw-file SHA-256. |
| `data_quality.csv` | Check ID, dataset/security/session, severity, finding, resolution; distinguish normal economic events from supplier gaps. |
| `signals.csv` | Run ID, decision time, security ID, eligibility, active signal components, score/rank, historical cap and availability time, target weight, reason. |
| `orders_fills.csv` | Run/order IDs, decision and execution times, security, side, requested/filled quantity, raw fill price, notional, cost, status/reason. |
| `corporate_action_ledger.csv` | Run/security/event IDs, effective and cash-availability times, quantity, receivable and cash changes, source. |
| `holdings_daily.csv` | Run ID, session, security ID, quantity, raw mark, market value, weight, valuation status. |
| `nav_daily.csv` | Run/strategy IDs, session, period label, cash, receivables, securities value, NAV, return, cumulative costs, valuation status. |
| `metrics.csv` / `monthly_returns.csv` | Run ID, metric/period, definition, value, observation count; net return, drawdown, traded notional, costs, cash and concentration diagnostics. |

Define precision and rounding before implementation. Keep trading turnover explicit: purchases plus sales divided by pretrade NAV; label any half-turnover convention separately. Report missing metrics as unavailable, not as zero performance.

## GitHub publication

Publish English methodology, configuration, source instructions, code when implemented, synthetic fixtures, and permitted aggregate results. Access to data is not permission to redistribute it. Retain hashes and acquisition instructions when raw files must remain private. Exclude credentials, signed download URLs, personal information, and conversation exports.

Maintain separate status flags for source documentation reviewed, connection established, data acquired, audit passed, engine validated, and market run completed. Configuration checks establish only their stated finite constraints; they cannot certify this experiment's performance.
