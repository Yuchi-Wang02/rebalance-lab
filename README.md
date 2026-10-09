# Rebalance Lab

## Does trading more often pay?

**The answer changes with the period, the portfolio and the cost of trading.** Two published pilot experiments compare monthly momentum selection with a fixed March/September schedule. One found a small cumulative advantage for monthly selection; the longer study found lower annualized returns. Both publish the unfavorable comparisons alongside the favorable ones.

[![Research checks](https://github.com/Yuchi-Wang02/SPMO-ETF-test/actions/workflows/checks.yml/badge.svg)](https://github.com/Yuchi-Wang02/SPMO-ETF-test/actions/workflows/checks.yml)
[![Website deployment](https://github.com/Yuchi-Wang02/SPMO-ETF-test/actions/workflows/pages.yml/badge.svg)](https://github.com/Yuchi-Wang02/SPMO-ETF-test/actions/workflows/pages.yml)

[Explore the research](https://yuchi-wang02.github.io/SPMO-ETF-test/) · [Stock experiment](https://yuchi-wang02.github.io/SPMO-ETF-test/stocks.html) · [ETF experiment](https://yuchi-wang02.github.io/SPMO-ETF-test/pilot.html) · [Methods and reproduction](docs/README.md)

### Two experiments, two different answers

| Study | What was compared | Finding at 5 bps per side |
|---|---|---|
| [100-issuer stock cohort](docs/studies/stock-pilot.md) | Select 20 stocks from a fixed December 2024 cohort; 2025 through October 2, 2026 | Monthly led by **1.23 percentage points of cumulative return**. It trailed by **6.93 points in 2025**, then led by **8.84 points in 2026 YTD**. |
| [Nine sector ETFs](docs/studies/sector-etf-pilot.md) | Select up to three ETFs; 25 complete years, 2001–2025 | Monthly returned **8.02% CAGR**, versus **8.51%** for March/September: **−0.49 percentage points per year**. Its maximum drawdown was shallower, and trading activity was higher. |

![Rebalance Lab research homepage with the stock and sector ETF experiments](docs/assets/site-preview.png)

These studies use different universes, weights, price conventions and measurement periods. The stock figure is a cumulative-return difference; the ETF figure is an annualized-growth difference. They cannot be added or averaged into one result.

Five basis points means a modeled cost of **0.05% on each purchase or sale**. Every study also reports 0, 10 and 25 bps scenarios. In the stock study, the full-period monthly advantage became **−0.74 points at 25 bps**. In the ETF study, changing the semiannual months could change the comparison's sign. A favorable year or calendar does not establish a durable advantage.

### Inspect an answer, then inspect its limits

- **Stocks:** [interactive report](https://yuchi-wang02.github.io/SPMO-ETF-test/stocks.html), [written findings](docs/studies/stock-pilot.md), [aggregate results](site/data/stock-pilot-summary.json), [independent replay](site/data/stock-pilot-validation.json).
- **ETFs:** [interactive report](https://yuchi-wang02.github.io/SPMO-ETF-test/pilot.html), [written findings](docs/studies/sector-etf-pilot.md), [all calendar/cost comparisons](site/data/etf-pilot-full_period.csv), [independent replay](docs/validation/pilot-validation.md).

Both use vendor-adjusted price proxies. Independent implementations reproduce the saved calculations; they do not independently verify every source price or reconstruct dividend payment and spin-off entitlements. The stock study also uses a restricted baseline cohort, issuer capitalization without certified historical publication vintages, and one disclosed price reconstruction. These limitations stay attached to the results.

The [original 75-stock protocol](docs/methods/original-stock-protocol.md) remains a separate, uncompleted study. It requires accepted historical membership, class-level capitalization, dividend-excluding signals and a raw-share corporate-action ledger. Neither completed experiment meets that full contract. The [data audit](docs/data/original-data-audit.md) records the missing inputs.

### Find your way around

```text
site/                 Interactive research and published aggregates
  stocks.html         Fixed-cohort stock experiment
  pilot.html          Long-history sector ETF experiment
docs/
  studies/            Findings and interpretation
  methods/            Frozen rules and research design
  validation/         Replay evidence and engine checks
  data/               Sources, audits and acceptance requirements
  project/            Presentation and publishing
configs/              Machine-readable experiment specifications
scripts/              Acquisition, execution, validation and publication
tests/                Automated checks
```

The [research index](docs/README.md) connects each result to its own method and reproduction instructions. Historical artifact names remain traceable even though the public project is now Rebalance Lab.

### Run the project

The site is static HTML, CSS and JavaScript. Python powers the experiments; the market-data workflows use pinned dependencies.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-pilot.txt
.venv/bin/python scripts/validate_design.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000` for the local site. The [reproduction guide](docs/README.md#reproduce-and-check) links acquisition, private-input replay and independent-validation commands. Source hashes identify the captured data; a fresh vendor download can contain revisions. Raw market data, credentials and detailed private ledgers are excluded from Git.

Rebalance Lab publishes bounded historical evidence, including negative results. It offers no forecast or trading recommendation.
