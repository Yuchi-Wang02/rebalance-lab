# Synthetic engine guide

The standard-library Python engine implements an **engineering prototype on fictional data**. It runs S12, M12, SMIX and MMIX at each prespecified cost rate: 0, 5, 10 and 25 basis points per side. This makes the 16 experiment paths inspectable before a market-data adapter exists. Synthetic outcomes are software diagnostics, not evidence that any strategy outperforms.

The implementation status is `synthetic_prototype`: an engine is implemented, but formal engine acceptance is false. No historical-data audit or market backtest has been completed. The [experiment protocol](experiment-design.md) remains the scientific specification, and the [data contract](feasibility.md) remains the market-release gate.

## Run it locally

Use Python 3.12 or newer from the repository root; no packages, credentials or network calls are required:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/run_synthetic.py --output-dir results/generated/synthetic --public-summary site/data/engine-status.json
```

The runner creates a new immutable run directory under the requested output directory. Repeating the command creates another directory instead of overwriting the previous run. Generated detailed outputs remain under the repository's ignored `results/generated/` directory. The optional public summary is a compact receipt of checks, run counts and hashes; it contains no performance figures. Inspect changes to that receipt before committing it.

The fixture uses invented security identifiers, prices, capitalization records and events. Its calendar is a sequence of weekdays with selected artificial closures, **not a verified exchange calendar**. The synthetic track cannot certify historical coverage, provider semantics, publication timing or investment results.

## What the prototype implements

| Component | Current responsibility |
|---|---|
| `spmo_lab/signals.py` | Common-calendar 12–1, 6–1 and 3–1 risk-adjusted signals, positive-score eligibility, Top 75 selection, security-ID tie breaks and capped proportional weights |
| `spmo_lab/ledger.py` | Fractional shares, cash, raw-price fills, transaction fees, split quantities, dividend receivables and payment, reinvestment, forced exits and unfilled orders |
| `spmo_lab/simulation.py` | Four strategy schedules, point-in-time input selection, close decisions and subsequent-open execution, burn-in and reporting periods |
| `scripts/run_synthetic.py` | Deterministic fixture generation, all 16 independent strategy/cost runs, engineering checks, output files and provenance |

Signals use the configured calendar rather than compressing an individual security's available rows. Only positive-weight horizons enter an arm's eligibility check. Portfolio targets retain the common 8% cap and do not create an `N/75` investment budget when fewer securities qualify.

The accounting sequence follows the protocol: corporate actions, forced membership exits, then scheduled rebalancing or dividend reinvestment. Dividends become receivables on the ex-date and spendable cash on the pay date; new dividend cash is eligible for reinvestment at the subsequent open. Unfilled regular orders expire, required exits can retry, and purchases cannot spend proceeds from failed sales. Transaction costs apply to actual executed notional.

All arms form portfolios at the first synthetic session after the December 31, 2024 signal and run through the 2025 burn-in. The December 31, 2025 closing state becomes the reporting anchor without a liquidation, extra trade or repeated initialization charge. A signal generated at that close can still execute at the next session's open. The reporting period ends October 2, 2026, without terminal liquidation.

## Inspectable outputs

The run directory contains a manifest with code, configuration and fixture hashes, plus separately identified results for each strategy/cost combination. JSON and CSV outputs allow inspection of synthetic decisions, fills, accounting and period labels. The public receipt records engineering checks and provenance separately from detailed fictional returns. Every result must retain `data_track=synthetic`.

Reproducibility depends on matching the input, configuration and code hashes, not merely repeating a directory name or using the same protocol version. Run identifiers distinguish executions; they are not performance rankings. Keep burn-in activity separate from reporting-period metrics when inspecting a path.

## Remaining market-release work

There is no vendor-input or real-return execution route. The Yahoo [diagnostic pipeline](data-pipeline.md) remains separate and supplies no strategy inputs. Connecting its price files directly to this engine would omit historical membership, capitalization vintages, action semantics and other required data.

Mergers, spinoffs and delisting settlements are unsupported and block input validation. Broader corporate-action coverage, explicit valuation treatment, audited exchange sessions, source availability semantics, and independent account reconciliation remain necessary for formal acceptance. SPMO/SPY account reconstruction and comparison with documented reference conventions also remain pending.

Passing a fictional scenario establishes only the checked software behavior. The project will retain `formal_engine_accepted=false`, `data_audit_completed=false`, `market_backtest_executed=false` and unavailable market returns until the corresponding gates pass.
