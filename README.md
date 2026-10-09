# SPMO Fast Lab

**Does faster momentum actually pay?**

A controlled study of monthly versus twice-yearly momentum selection. Both portfolios use the same signal, investment universe, weighting rules and trading-cost assumptions. The question is whether updating the portfolio more often leaves investors better off after costs.

**Market findings pending: historical data audit.** The research protocol and synthetic engine are available. A real-market strategy backtest has not been run.

## Start with one comparison

| Portfolio | Selection schedule | Signal |
|---|---|---|
| **S12 — primary control** | March and September month-end | 12–1 risk-adjusted price momentum |
| **M12 — primary comparison** | Every month-end | The same 12–1 signal |

The primary outcome is **M12 minus S12 net return**, measured over the same dates. Common maintenance rules still process dividends, splits and required constituent exits between scheduled selections. These custom portfolios differ from the official SPMO index; actual SPMO and SPY provide product context.

## What would make a useful answer?

- **Benefit:** the net-return difference, including unfavorable periods.
- **Risk:** the drawdown difference over the same reporting period.
- **Trading burden:** the additional amount bought and sold, associated costs and cash exposure.

Show these together at **0 / 5 / 10 / 25 basis points per side**. A higher gross return alone does not establish that faster selection is worthwhile. No arbitrary composite score or unagreed risk threshold selects a winner.

## Check whether the finding survives

The additional SMIX/MMIX pair repeats the frequency comparison using a 50/30/20 blend of 12–1, 6–1 and 3–1 signals. It is **within-study robustness**, sharing the same market observations and many exposures.

A separate [calendar-sensitivity protocol](docs/calendar-sensitivity.md) fixes all six possible semiannual month pairs in advance. March/September remains the primary schedule; every other schedule is reported alongside it. The implementation cannot replace the primary result with the best-looking calendar.

The original **2026 period through October 2** remains a retrospective case study, with portfolios established during 2025. A broader historical study needs a separately fixed, coverage-audited set of complete years. It will show yearly paired differences as well as the overall path. The [research blueprint](docs/research-blueprint.md) explains the evidence hierarchy and extension rules.

## Evidence available today

| Gate | Current evidence | Next requirement |
|---|---|---|
| Historical inputs | SPMO/SPY price diagnostics and offline replay work | Audit constituent history, historical capitalization, prices and corporate actions |
| Engine reconciliation | Accounting and execution can be exercised on fictional data | Broader event support and independent reconciliation against accepted market/event records |
| Market comparisons | Not run; the primary and supplementary protocols are documented | Accept the inputs and engine, then complete all prespecified comparisons |

The [English website](site/index.html) explains the question first, then offers progressively deeper methods and reproduction details. Public GitHub Pages hosting still requires activation; the image below is a tested local preview.

![SPMO Fast Lab preview: the primary comparison and evidence-led research story](docs/assets/site-preview.png)

## The next data decision

First obtain a small, authorized [acceptance sample](docs/data-acceptance-sample.md) covering ordinary securities and difficult events: membership entry/exit, ticker changes, splits, dividends, multiple share classes and merger/delisting settlement. Historical class-level capitalization and information-availability dates must be demonstrated before a provider is treated as sufficient.

If institutional access already exists, inspect an entitled WRDS/CRSP export. Otherwise verify the required licensed components before choosing a commercial route. The [source guide](docs/data-sources.md) records what was actually inspected and each remaining gap. No subscription, credential or complete historical dataset is assumed.

<details>
<summary><strong>Inspect the full methods and implementation</strong></summary>

| Document | Purpose |
|---|---|
| [Research blueprint](docs/research-blueprint.md) | Main question, evidence hierarchy, time-window and interpretation rules |
| [Primary protocol](docs/experiment-design.md) | Exact signal, weighting, timing, cash and cost rules |
| [Calendar sensitivity](docs/calendar-sensitivity.md) | Six prespecified schedules, shared controls and complete reporting |
| [Data acceptance sample](docs/data-acceptance-sample.md) | Concrete sample request, required fields and reconciliation checks |
| [Data sources](docs/data-sources.md) | Provider links, connection routes and verified limitations |
| [Feasibility and data contract](docs/feasibility.md) | Full market-data and release requirements |
| [Engine guide](docs/engine.md) | Synthetic execution, accounting and remaining acceptance work |
| [Evidence record](docs/evidence.md) | Observed checks and claim boundaries |
| [Research status](results/status.json) | Machine-readable implementation and market-readiness status |
| [Site strategy](docs/site-strategy.md) | Audience, information hierarchy and accessibility |

</details>

<details>
<summary><strong>Run and reproduce the engineering checks</strong></summary>

Python 3.12+ is sufficient; the Python code has no third-party dependencies. Node is needed only for the JavaScript syntax check. Use the existing checkout in cloud tasks; no extra Git worktree is required.

```bash
python3 scripts/validate_design.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --check site/app.js
```

Run the primary fictional experiment or the separate calendar-sensitivity exercise:

```bash
python3 scripts/run_synthetic.py --output-dir results/generated/synthetic
python3 scripts/run_calendar_sensitivity.py --output-dir results/generated/calendar-sensitivity
```

Both create new immutable run directories. Primary and supplementary outputs have distinct experiment labels. The generated ledgers and fictional performance figures remain in ignored directories. Public receipts contain only checks, counts and provenance.

The [price pipeline guide](docs/data-pipeline.md) documents `python3 scripts/ingest_diagnostic.py`, raw-response hashing and offline replay. Its Yahoo observations remain separate from the synthetic engine and do not satisfy the historical-universe contract.

To inspect the static site, run `python3 -m http.server 8000 --directory site` from the repository root. [Publishing instructions](docs/publishing.md) explain Pages activation and how to verify an actual public deployment.

</details>

Publish methods, permitted results and reproducibility records together, including negative findings. Credentials, raw conversation and market data without redistribution rights stay out of Git.
