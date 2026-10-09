# Preview and publish the research site

The website is plain HTML, CSS and JavaScript under `site/`; there is no frontend package installation or build step.

## Local checks

From the repository root:

```bash
python3 scripts/validate_design.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --check site/app.js
python3 -m http.server 8000 --directory site
```

Inspect the local server in a browser. Stop it when finished. A local preview does not establish a public deployment, and this cloud onboarding chat does not provide public loopback preview links.

## GitHub Pages

The independent **Research checks** workflow validates the protocol, ingestion tests and JavaScript syntax on pushes and pull requests. It does not require Pages activation or live provider requests.

The **Validate and publish research site** workflow validates the design and uploads only `site/` after a push to `main` or a manual dispatch. It then checks Pages configuration through GitHub's API. If no site exists, the build keeps its downloadable static artifact, adds an explicit activation notice, and skips deployment. If the source is GitHub Actions, it deploys using GitHub's official Pages action. Other publishing sources are left unchanged; unexpected API errors fail visibly.

A successful artifact build with **deploy skipped** means the site is ready for hosting, not that it is public. The ingestion summary under `site/data/` contains aggregate diagnostics only. No workflow acquires or uploads raw market data.

The repository's **Settings → Pages → Build and deployment → Source** must be **GitHub Actions**. Enabling that setting requires sufficient repository permissions and a GitHub plan that supports Pages for the repository's visibility. Do not change repository visibility simply to make hosting work.

Expected project-site location after a successful deployment: `https://yuchi-wang02.github.io/SPMO-ETF-test/`. This is a target address, not proof that the site is live. Confirm the workflow's deploy result and make an HTTP request to the published page before advertising it as available.

The workflow publishes presentation files, not raw research data. Repository secrets, provider exports, source receipts and the prior chat must not be copied into `site/`.

## Runtime notes

Future tasks should use the existing `/workspace/SPMO-ETF-test` checkout rather than creating another worktree. The files and Python runtime can persist in an environment snapshot; a local HTTP server does not. Start a new server only when a task needs a preview. No server is required to read or validate the design.

## Current activation blocker

Earlier workflow runs passed configuration validation but failed initial Pages configuration because the repository did not have a Pages site. A direct attempt to create it returned GitHub HTTP 403, **Resource not accessible by integration**, even though repository metadata reports that the user has admin permission. User permission and the connected integration's granted permission are different. The current workflow handles the unconfigured state explicitly without attempting to create a site.

A repository administrator can finish activation in **Settings → Pages → Source → GitHub Actions**, then rerun **Validate and publish research site** from the Actions tab. No repository visibility change or provider data key is required. GitHub's [official configure-pages input contract](https://github.com/actions/configure-pages/blob/v5/action.yml) states that automatic initial enablement needs a token other than the workflow's default `GITHUB_TOKEN`, with the corresponding Pages/administration permissions. No extra token is requested or embedded here.

At the latest check the target Pages URL returned origin HTTP 404, so the public site is **not yet verified live**. The README image is a screenshot of the tested local site.
