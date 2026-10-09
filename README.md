# SPMO Fast Lab

**Can momentum move faster without paying away the edge?**

A reproducible research project about faster portfolio rotation within the S&P 500. The aim is to test a plausible idea—not to advertise an ETF, recommend trades, or assume that more trading produces better returns.

**Current release: protocol v0.2, a synthetic engine prototype, reproducible price diagnostics and website preview. No market backtest has been run.** The engine runs the four strategies and four cost assumptions on fictional inputs to inspect signals, execution and accounting. Formal engine acceptance and the historical-data audit remain pending. Separately, direct Yahoo requests returned 711 daily observations each for SPMO and SPY, from December 1, 2023 through October 2, 2026; structural checks and offline replay passed, while exchange-calendar completeness and price-adjustment semantics remain unverified.

## The research question

Holding the investment universe, portfolio construction, and cost model constant, does monthly selection improve net results over semiannual selection? Does the answer change when a shorter-horizon momentum blend replaces a single 12–1 signal?

| | 12–1 momentum | 50/30/20 blend of 12–1, 6–1, 3–1 |
|---|---|---|
| Semiannual selection | **S12** | **SMIX** |
| Monthly selection | **M12** | **MMIX** |

All four arms use the same Top 75 rule, positive-score eligibility, score × square-root historical security market capitalization, and 8% target security cap. Buffers, moving-average entry filters, and weekly exits are deferred. This makes the primary comparison easier to interpret than changing several rules at once.

- **Primary contrast:** M12 minus S12, after trading costs.
- **Prespecified replication:** MMIX minus SMIX.
- **Descriptive interaction:** the difference between those two frequency effects.
- **Real-world context:** actual SPMO and SPY. Neither is a controlled test of selection frequency.

These are proposed research rules, not an official replication of the SPMO index. Read the [full experiment protocol](docs/experiment-design.md).

## A proper YTD starting point

The original investigation ends on **October 2, 2026**, and that cutoff remains fixed. Each portfolio is initialized from cash at the first trading open of 2025 and runs through 2025 to establish its own holdings. Its December 31, 2025 closing NAV is then normalized to 100 for the 2026 YTD measurement.

This avoids granting the semiannual strategy an extra January 2026 formation. Request data from **December 1, 2023** to cover the first signal's warmup. Initialization costs remain in the 2025 ledger; they are not charged again at the reporting boundary. The 2026 period is **retrospective and exploratory**, because its market developments informed the idea.

## Where the data will come from

| Route | Practical connection | What it can support | Remaining gate |
|---|---|---|---|
| Free diagnostic | [Direct Yahoo chart ingestion](docs/data-pipeline.md); [yfinance](https://pypi.org/project/yfinance/) is an optional client | Fixed-window SPMO/SPY price/action capture, quality checks and offline replay | Not a historical constituent, delisting, or point-in-time capitalization solution; adjustment semantics and usage rights require review |
| Institutional research | [WRDS](https://wrds-www.wharton.upenn.edu/) / licensed CRSP export | Candidate integrated identifiers, membership, returns, actions and share histories | Entitlement, exact tables, opening prices, vintage semantics and coverage must be verified; the SDK uses PostgreSQL, not HTTPS |
| Licensed API components | [Nasdaq Data Link](https://data.nasdaq.com/) / SHARADAR candidates | HTTPS table extraction for candidate prices, fundamentals and identifiers | Table contracts and subscription unverified; a separate audited historical-membership source is still required |
| Windows-assisted export | [Norgate Data](https://pypi.org/project/norgatedata/) | Documented historical-constituent and price APIs with appropriate subscription | Requires Windows updater; documented market-cap fundamentals are current values, not a historical PIT cap series |

**Recommended next step:** audit a small institutional export if access already exists. Otherwise obtain a licensed-data coverage sample before committing to a provider. The free diagnostic now works, but it cannot supply all inputs to the experiment. No subscription purchase or institutional access is assumed.

The [data connection guide](docs/data-sources.md) gives links, SDK entry points, authentication requirements, expected outputs, and unresolved gaps. The [data contract](docs/feasibility.md) defines what must pass before a result can be published. The [pipeline guide](docs/data-pipeline.md) documents the executable diagnostic and its limits. Successful price ingestion is not a strategy result.

## The public site

The [static site source](site/index.html) is designed for curious ETF investors first and quantitative reviewers second. It explains the hypothesis, lets visitors explore the four-arm design, illustrates cost arithmetic, and makes data readiness visible. It intentionally has no invented equity curves.

![SPMO Fast Lab website preview: research question and scheduled selection calendar](docs/assets/site-preview.png)

[Audience and page strategy](docs/site-strategy.md) explains the design. [Pages deployment instructions](docs/publishing.md) distinguish a local preview from a verified public deployment. A deployment workflow is included; hosting still depends on repository Pages permissions and settings.

## Run the available checks

Python 3.12+; no third-party dependencies are needed for the engine, checks or static site.

```bash
python3 scripts/validate_design.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --check site/app.js
```

These offline commands check protocol/status invariants and links, exercise synthetic engine and ingestion/replay cases, and check site JavaScript syntax. Node is needed only for the JavaScript check. No provider account or network request is required.

Run the complete fictional experiment:

```bash
python3 scripts/run_synthetic.py --output-dir results/generated/synthetic --public-summary site/data/engine-status.json
```

Each invocation creates a new run directory with all 16 strategy/cost combinations and a reproducibility manifest. The public receipt contains engineering checks, counts and hashes, with no performance figures. The [engine guide](docs/engine.md) explains the implementation boundary and outputs. Synthetic results test software behavior; they do not estimate investment performance.

Run `python3 scripts/ingest_diagnostic.py` to acquire a new private diagnostic snapshot. See the [pipeline guide](docs/data-pipeline.md) for replay and public-summary export commands. The separate `python3 scripts/check_source_access.py` probes documentation reachability only; it does not prove subscription access.

To inspect the site locally, run `python3 -m http.server 8000 --directory site` from the repository root and use a local browser. Cloud tasks use the existing checkout; an extra Git worktree is unnecessary.

## Repository map

| Path | Purpose |
|---|---|
| [Experiment protocol](docs/experiment-design.md) | Hypotheses, exact rules, timing, evaluation and limitations |
| [Data connection guide](docs/data-sources.md) | Concrete provider routes and verification status |
| [Feasibility and data contract](docs/feasibility.md) | Fields, quality gates, implementation stages and output schema |
| [Evidence record](docs/evidence.md) | What was actually inspected and what remains unverified |
| [Experiment configuration](configs/experiment.v1.json) | Machine-readable protocol v0.2; filename retained for existing links |
| [Source registry](configs/data-sources.json) | Provider documentation, connection routes and gaps |
| [Diagnostic pipeline](docs/data-pipeline.md) | Fixed-window acquisition, quality checks, hash verification and offline replay |
| [Synthetic engine guide](docs/engine.md) | Offline fictional experiment, accounting rules, reproducibility and remaining acceptance work |
| [Public diagnostic summary](site/data/ingestion-summary.json) | Observed dates, aggregate quality counts and provenance; no market bars |
| [Research status](results/status.json) | Explicit machine-readable absence of market results |
| [Website](site/index.html) | Static, dependency-free public presentation |

## Release gates

1. **Protocol and source plan:** documented in this release; parameters remain proposed until frozen before a market run.
2. **Data acceptance:** benchmark price diagnostics are implemented; permanent-ID mapping, historical membership, original prices, corporate actions, capitalization vintages and benchmark reconstruction remain pending.
3. **Engine acceptance:** the synthetic prototype exercises signals, accounting and execution. Formal acceptance still requires broader event coverage, independent reconciliation and audited market inputs.
4. **Historical experiment:** all four arms and all prespecified cost scenarios, with ledgers and reproducible manifests.
5. **Forward observation:** signals saved before execution after the final protocol/implementation freeze. Never relabel retrospective results as live observations.

Returns, drawdowns and costs will be published together, including unfavorable results. Raw chat, credentials and data without redistribution rights stay out of Git. See [the evidence boundary](docs/evidence.md).
