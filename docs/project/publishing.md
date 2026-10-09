# Preview and publish the research site

The website is plain HTML, CSS and JavaScript under `site/`; there is no frontend package installation or build step.

## Local checks

From the repository root:

```bash
python3 scripts/validate_design.py
python3 scripts/validate_pilot_artifacts.py
python3 scripts/validate_stock_pilot_artifacts.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --check site/app.js
node --check site/pilot.js
node --check site/stocks.js
python3 -m http.server 8000 --directory site
```

Inspect the local server in a browser. Stop it when finished. A local preview does not establish a public deployment, and this cloud onboarding chat does not provide public loopback preview links.

## GitHub Pages

The independent **Research checks** workflow validates the protocol, ingestion/engine tests and JavaScript syntax on pushes and pull requests. It executes the 16 primary synthetic paths and the separate six-phase sensitivity exercise in the runner's temporary directory. It does not require Pages activation or live provider requests.

The **Validate and publish research site** workflow validates the design and uploads only `site/` after a push to `main` or a manual dispatch. It then checks Pages configuration through GitHub's API. If no site exists, the build keeps its downloadable static artifact, adds an explicit activation notice, and skips deployment. If the source is GitHub Actions, it deploys using GitHub's official Pages action. Other publishing sources are left unchanged; unexpected API errors fail visibly.

A successful artifact build with **deploy skipped** means the site is ready for hosting, not that it is public. The ingestion summary under `site/data/` contains aggregate diagnostics only. No workflow acquires or uploads raw market data.

The repository's **Settings → Pages → Build and deployment → Source** must be **GitHub Actions**. Enabling that setting requires sufficient repository permissions and a GitHub plan that supports Pages for the repository's visibility. Do not change repository visibility simply to make hosting work.

The project site is live at [https://yuchi-wang02.github.io/SPMO-ETF-test/](https://yuchi-wang02.github.io/SPMO-ETF-test/), with the [interactive experiment report](https://yuchi-wang02.github.io/SPMO-ETF-test/pilot.html) alongside it. The deployment and public files were verified on October 9, 2026; see the evidence below. For later changes, confirm the new workflow's deploy result and check the published files again.

The workflow publishes presentation files, not raw research data. Repository secrets, provider exports, source receipts and the prior chat must not be copied into `site/`.

## Runtime notes

Future tasks should use the existing `/workspace/SPMO-ETF-test` checkout rather than creating another worktree. The files and Python runtime can persist in an environment snapshot; a local HTTP server does not. Start a new server only when a task needs a preview. No server is required to read or validate the design.

## Rebalance Lab presentation revision

The October 9, 2026 presentation revision reorganizes the repository around the two published pilot studies, with an English homepage, cost exploration, and a separate research index. The public name is **Rebalance Lab**. The current live address stays unchanged because GitHub rejected repository-name, description and topic updates from the connected integration. See the exact [owner settings and rename procedure](repository-settings.md).

The revision preserves all numerical configurations, engines and published research data. Before publication, 122 unit tests, the three research validators, JavaScript syntax checks and moved-document links passed. Chromium checks covered six homepage widths and all four stock cost choices, plus both report pages. Additional checks exercised keyboard selection, unavailable summaries and malformed data; unsupported values were not substituted. The README screenshot comes from the local browser preview.

The historical deployment receipt below predates this presentation revision. A new push still requires successful Research checks, successful Pages deployment, and comparison of the newly hosted files with the local files.

## Verified deployment and activation history

On **October 9, 2026 at 02:25 UTC**, the Pages API reported `build_type=workflow`. [Workflow run 37874047025, attempt 2](https://github.com/Yuchi-Wang02/SPMO-ETF-test/actions/runs/37874047025/attempts/2) then completed both build and deployment successfully for commit `66fdfa288f6f61757860458e200716027bee34da`.

At **02:25:51 UTC**, verified HTTPS requests returned **HTTP 200** for the homepage, report page, both JavaScript files, the summary and validation JSON files, all three result CSVs and all three report figures. Each of these 12 public files had the same SHA-256 hash as its local source. This confirms that the deployed site contains the validated experiment artifacts.

Desktop/mobile rendering and all eight signal/cost combinations were checked against the local site before deployment. Direct Chromium navigation to the public site was blocked by the cloud browser's proxy-certificate trust configuration; TLS verification was not disabled. Public availability and content equality were verified separately through HTTPS. The README image remains a screenshot of the tested local site.

Earlier activation attempts returned GitHub HTTP 403, **Resource not accessible by integration**. That initial setup blocker is resolved: the repository now uses **Settings → Pages → Source → GitHub Actions**. The workflow still handles an unconfigured repository explicitly without attempting to change its settings. No extra token, repository visibility change or provider data key was needed for this deployment.

Publishing this site does not complete the original stock experiment. The completed ETF pilot and the remaining historical-stock data requirements retain their separate status.
