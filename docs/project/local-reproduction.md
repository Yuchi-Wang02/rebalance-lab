# Local checks on Windows

The public repository includes the saved study results, configurations and code needed for offline consistency checks. The licensed source captures and full private account ledgers are separate. Passing these commands verifies the saved artifacts and software behavior; it does not independently verify vendor observations or rerun the market studies from source data.

## Runtime and encoding

Use Python 3.12 or later and Node.js for the JavaScript syntax checks. The CI workflow uses Python 3.12. Run the commands from the repository root in PowerShell, with `python` pointing to the intended interpreter. A virtual environment's interpreter can be substituted directly for `python`.

Use Python's `-X utf8` option on Windows. Several existing scripts read UTF-8 research documents using the interpreter's default encoding, which can otherwise be a Windows code page. The option changes the runtime encoding without editing frozen research code. The ingestion tests also need the IANA `America/New_York` timezone; a Windows Python installation without that timezone database needs the `tzdata` package in the selected environment.

The Windows CI environment installs `tzdata==2026.4`. To prepare the same dependency locally, run `python -m pip install tzdata==2026.4` in the selected virtual environment.

## Offline checks

```powershell
python -X utf8 scripts/validate_design.py
python -X utf8 scripts/validate_pilot_artifacts.py
python -X utf8 scripts/validate_stock_pilot_artifacts.py
python -X utf8 -m unittest discover -s tests -p 'test_*.py' -q
node --check site/app.js
node --check site/pilot.js
node --check site/stocks.js
node --test tests/test_pilot_ui.mjs
```

Run each command and check its exit status. The design checker covers declared protocol invariants and local links. The two artifact checkers reconcile saved outputs with their recorded scope and provenance. The unit suite uses synthetic inputs and captured fixtures. The JavaScript commands check syntax; browser layout, controls, keyboard access and loading failures need separate inspection.

These checks do not require market-data credentials or make new market-data requests. Optional packages in `requirements-pilot.txt` support the market-data and plotting workflows and are separate from this offline check sequence.

## Preserve exact research bytes

The historical receipts hash exact file bytes. The repository's [`.gitattributes`](../../.gitattributes) keeps text files at LF line endings on every platform, including when the machine's Git setting is `core.autocrlf=true`. Code, configurations and public results must retain their original hashes; a line-ending conversion is enough to make a byte-level provenance check fail.

Inspect representative files with:

```powershell
git ls-files --eol configs/stock-pilot.v1.json scripts/run_stock_pilot.py site/data/stock-pilot-summary.json
```

The working-tree column should show `w/lf`. A checkout created before the attributes policy may still show `w/crlf`, because adding attributes does not rewrite existing files. Preserve any local edits and use a separate fresh checkout with the attributes policy, or restore only files independently confirmed unchanged apart from line endings. Replacing historical receipt hashes would remove the evidence of the original run instead of repairing the checkout.

A failing provenance check identifies a mismatch to investigate. It does not, by itself, establish that a study's calculation or underlying vendor data is wrong.

## Preview the saved site

```powershell
python -X utf8 -m http.server 8000 --bind 127.0.0.1 --directory site
```

Open [the local site](http://127.0.0.1:8000/) while the command is running. It serves the checked-in result snapshots; it does not refresh prices or publish changes. Stop the server with `Ctrl+C`.

Source-data replay requires the corresponding private captures and a fresh output directory. See the [stock study](../studies/stock-pilot.md), [ETF validation guide](../validation/pilot-validation.md), and [source-access guide](../data/sources.md) for the separate replay requirements.
