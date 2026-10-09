# Rebalance Lab research index

[Open the research site](https://yuchi-wang02.github.io/SPMO-ETF-test/) or [return to the repository](../README.md). Start with a result, then follow its own method and evidence. These studies answer related questions under different assumptions; they are not interchangeable versions of one backtest.

## Read the results

| Study | Start here | Inspect the saved evidence |
|---|---|---|
| Fixed 100-issuer cohort, selecting 20 stocks | [Stock findings](studies/stock-pilot.md) · [interactive report](https://yuchi-wang02.github.io/SPMO-ETF-test/stocks.html) | [Summary](../site/data/stock-pilot-summary.json) · [reconstruction sensitivity](../site/data/stock-pilot-sensitivity.json) · [independent replay](../site/data/stock-pilot-validation.json) |
| Nine sector ETFs, selecting up to three | [ETF findings](studies/sector-etf-pilot.md) · [interactive report](https://yuchi-wang02.github.io/SPMO-ETF-test/pilot.html) | [Summary](../site/data/etf-pilot-summary.json) · [all long-period comparisons](../site/data/etf-pilot-full_period.csv) · [annual comparisons](../site/data/etf-pilot-annual.csv) · [2026 comparisons](../site/data/etf-pilot-ytd2026.csv) |

The stock study reports 2025 formation/burn-in and 2026 through October 2 separately, with continuous accounts. The ETF study reports the 25 complete years 2001–2025 and keeps its 2026 partial year separate. Read costs, drawdowns, trading activity and source limitations alongside returns.

## Understand the methods

| Material | Purpose |
|---|---|
| [Stock pre-acquisition freeze](../configs/stock-pilot.design-freeze.json) | The baseline cohort, signal, schedule and portfolio rules before price acquisition |
| [Current stock specification](../configs/stock-pilot.v1.json) and [source-audit policy](../configs/stock-pilot-audit.v1.json) | Corrected vendor-price description, one permitted reconstruction, and accounting limits |
| [Sector ETF protocol](methods/sector-etf-protocol.md) and [configuration](../configs/sector-etf-pilot.v1.json) | ETF universe, three-slot rule, reporting windows, six calendars and cost grid |
| [Research blueprint](methods/research-blueprint.md) | The original question, comparison hierarchy and planned stronger evidence |
| [Original stock protocol](methods/original-stock-protocol.md) and [configuration](../configs/experiment.v1.json) | The uncompleted 75-stock study with its stricter data and accounting contract |
| [Original calendar sensitivity](methods/calendar-sensitivity.md) | The separate six-phase synthetic implementation; not a completed market run of the original protocol |

The original protocol is preserved for review. The stock and ETF pilots explicitly change some of its assumptions and retain their own identifiers, configurations and results.

## Reproduce and check

Install the pinned [market-workflow dependencies](../requirements-pilot.txt) in a virtual environment. The repository [README](../README.md#run-the-project) gives setup and test commands. A private snapshot is required to replay its exact source values; a new acquisition may contain revised data.

| Workflow | Instructions and code |
|---|---|
| Stock acquisition and replay | [Stock report commands](studies/stock-pilot.md#reproduction-and-publication-boundaries) · [paid capture](../scripts/stock_pilot_sharadar.py) · [price capture](../scripts/stock_pilot_prices.py) · [runner](../scripts/run_stock_pilot.py) |
| Stock sensitivity and independent replay | [Sensitivity runner](../scripts/stock_pilot_sensitivity.py) · [independent verifier](../scripts/validate_stock_pilot_independent.py) · [saved receipt](../site/data/stock-pilot-validation.json) |
| ETF acquisition and replay | [ETF workflow](methods/sector-etf-protocol.md#execution-and-replay) · [data audit](../scripts/etf_pilot_data.py) · [runner](../scripts/run_etf_pilot.py) |
| ETF independent replay | [Validation findings and commands](validation/pilot-validation.md) · [independent verifier](../scripts/validate_etf_pilot_independent.py) · [saved receipt](../site/data/etf-pilot-validation.json) |
| Original synthetic engine | [Engine guide](validation/engine.md) · [primary fixture runner](../scripts/run_synthetic.py) · [calendar fixture runner](../scripts/run_calendar_sensitivity.py) |
| Price-ingestion diagnostics | [Pipeline guide](data/pipeline.md) · [diagnostic runner](../scripts/ingest_diagnostic.py) |
| Website | [Local preview and publishing](project/publishing.md) · [presentation design](project/site-strategy.md) |

An independent replay checks computation on the same preserved inputs. It does not substitute for independent price, corporate-action or historical-availability evidence. Synthetic tests validate software behavior and do not establish market performance.

## Inspect data and limitations

- [Original-data audit](data/original-data-audit.md): observed access, missing fields and why the original protocol remains incomplete.
- [Source guide](data/sources.md): provider links, access routes and verified limitations.
- [Data acceptance sample](data/acceptance-sample.md): event-led checks before a full historical dataset is accepted.
- [Feasibility and data contract](data/feasibility.md): required identifiers, membership, prices, capitalization and corporate actions.
- [Purchase guide](data/purchase-guide.md): candidate commercial routes and questions to resolve before buying additional coverage.

Public files contain permitted derived portfolio series, aggregate results, code and provenance. Licensed source exports, raw vendor observations, credentials and detailed private ledgers stay outside Git.

## Follow the research history

- [Evidence record](validation/evidence.md) records source and implementation checks as they happened.
- The original [protocol](methods/original-stock-protocol.md) and [synthetic engine guide](validation/engine.md) explain the starting design and its remaining acceptance requirements.
- The [stock freeze](../configs/stock-pilot.design-freeze.json) and [ETF freeze commit](https://github.com/Yuchi-Wang02/SPMO-ETF-test/commit/8bb2e11) preserve each pilot's earlier specification. A retrospective freeze is not prospective registration.
- [Machine-readable status](../results/status.json) records the studies separately.

## Contribute and maintain

- [Contributing guide](../CONTRIBUTING.md): propose a research question, report a problem or prepare a reproducible change.
- [Repository settings](project/repository-settings.md): the proposed repository name, description and topics, with the owner action still needed to apply them.
- [Publishing guide](project/publishing.md): preview and verify the deployed site.

The public identity is **Rebalance Lab**. Historical artifact names remain stable so configurations and source hashes stay traceable.
