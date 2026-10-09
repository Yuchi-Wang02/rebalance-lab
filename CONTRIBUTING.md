# Contributing to Rebalance Lab

Help make the evidence easier to inspect, reproduce, and challenge. Useful contributions include data-quality findings, independent accounting checks, clearer explanations, and accessible visualizations.

## Start with a specific study

Read the [research index](docs/README.md), then the study's limitations and saved artifacts. The stock and sector ETF studies have different universes, periods, and accounting assumptions. A change to one does not validate the other. The original full-universe stock protocol is not completed.

## Reproduce before interpreting

These checks run without paid data or API credentials:

```bash
python3 scripts/validate_design.py
python3 scripts/validate_pilot_artifacts.py
python3 scripts/validate_stock_pilot_artifacts.py
python3 -m unittest discover -s tests -p 'test_*.py' -q
node --check site/app.js
node --check site/pilot.js
node --check site/stocks.js
```

They check saved artifacts and software behavior. They do not download the private research inputs or independently establish that vendor observations are correct. See the [publishing guide](docs/project/publishing.md) for a local site preview and the [data guide](docs/data/sources.md) for source access.

## Keep results auditable

- Report the study, measurement dates, signal, rebalance schedule, and cost per side with any performance claim. Label cumulative returns and annualized growth separately.
- Preserve frozen configurations and recorded hashes. A methodology change needs a separately named experiment and a new run receipt; do not silently replace historical results.
- Include all specified comparison arms and cost cases. A favorable year or calendar phase is not a substitute for the primary comparison.
- Keep credentials, licensed observations, private source files, and account information out of commits and issue attachments. Publish only artifacts you have permission to redistribute.
- For a visual change, check narrow and wide screens, keyboard navigation, data-loading failures, and the source links. Keep visible limitations alongside the findings.

## Propose a change

Open an issue with the relevant source, reproduction steps, and expected behavior. For a pull request, explain what changes, why, and how it was checked. Evidence that contradicts a headline is especially welcome.
