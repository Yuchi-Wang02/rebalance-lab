# Reproduction and evidence guide

## Public-input tier: no credentials or vendor download

Create a virtual environment and install `requirements-research.txt`. Use its Python for every command:

```bash
python scripts/validate_design.py
python scripts/validate_pilot_artifacts.py
python scripts/validate_stock_pilot_artifacts.py
python scripts/validate_validation_artifacts.py
python -m unittest discover -s tests -p 'test_*.py' -v
python -m pilot.validation_figures --summary site/data/validation-study-summary.json --output-dir site/assets
python scripts/build_validation_documents.py
python scripts/build_validation_pdfs.py
python scripts/build_validation_notebook.py
python -m http.server 8000 --directory site
```

The notebook includes editable plotting and statistical calculations. It loads public derived daily portfolio NAV and 34,800 monthly return rows, including captured RF; recomputes CAGR, risk metrics and primary bootstrap intervals; and checks those outputs against the validated summary. It does not reconstruct holdings from public asset prices. The notebook is executed and saved with outputs; HTML is supplied for reading without a kernel.

The summary identifies the protocol, freeze, original source manifests, generator code and replay receipts. Public data are portfolio aggregates, not raw vendor observations. RF comes from the official [French factor archive](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html). Current factor histories can be revised; capture identity is documented. [FF definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html) describe the RF series. The [stationary bootstrap paper](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870) is the methodological reference.

## Private-snapshot tier: exact engine and accounting replay

The preserved raw Yahoo responses, normalized input, source accounts and complete ledgers are excluded from Git. Exact replay requires the locally retained snapshots with matching manifest hashes. A new vendor acquisition can contain revised values and is a new run, not an exact reproduction. No paid API is required by the ETF extension.

```bash
python scripts/run_etf_mechanisms.py --input-run-dir results/generated/etf-pilot/20261009T021722928426Z-9e9cb830b3cb --output-dir results/generated/etf-mechanisms
python scripts/run_validation_study.py --run-dir results/generated/etf-mechanisms/20261009T050633543130Z-d96bbf03d531 --factor-dir data/raw/french-factors/20261009T050942196828Z-abb85a14 --validation results/generated/etf-mechanisms-validation/20261009T050633543130Z-d96bbf03d531.json --output-dir results/generated/validation-study/NEW-UNIQUE-RUN
python scripts/validate_validation_study_independent.py --source-dir results/generated/etf-mechanisms/20261009T050633543130Z-d96bbf03d531 --extension-dir results/generated/validation-study/20261009-v1 --factor-dir data/raw/french-factors/20261009T050942196828Z-abb85a14 --output results/generated/validation-study/REPLAY-RECEIPT.json
```

The first command creates a new timestamped mechanism directory. Its independent verifier must be run before using that directory as input, and the new hashes must be recorded in a newly versioned extension protocol. The second command above reproduces the existing frozen source run into a new output directory. It refuses overwritten output or stale source manifests. See the [archived mechanism method](archive/methods/sector-etf-mechanisms.md) for the source-account replay commands.

## Artifact generation and validation

The extension's private manifest is immutable. Local public preparation copies only permitted derived inputs and binds their hashes to the public summary. The extension receipt binds both the private and public summary identities. Runtime plot/report generation uses the validated summary; a completion record separately states whether outputs and owner checkpoints are complete.

The independent extension verifier imports no project calculation code. It recomputes sleeve sums, fees, opening NAV, monthly returns, risk ratios and bootstrap percentiles. Authorship is still the same agent. Tests include hand calculations and failure injection for shifted dates, missing months, wrong fees and stale summaries. Neither checks nor manifests certify vendor prices or tradability.

## Local review and publication

Open the generated site, four-page brief, one-page memo and executed notebook. Check desktop/mobile layouts and data-unavailable behavior. Record the three owner checkpoints separately. This release is prepared locally; a public URL already exists for the older version. Do not call the new version deployed until a separately authorized push/deploy completes and its live contents are verified.
