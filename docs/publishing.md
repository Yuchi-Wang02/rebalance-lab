# Preview and publish the research site

The website is plain HTML, CSS and JavaScript under `site/`; there is no frontend package installation or build step.

## Local checks

From the repository root:

```bash
python3 scripts/validate_design.py
python3 -m http.server 8000 --directory site
```

Inspect the local server in a browser. Stop it when finished. A local preview does not establish a public deployment, and this cloud onboarding chat does not provide public loopback preview links.

## GitHub Pages

The repository includes `.github/workflows/pages.yml`, which validates the design, uploads only `site/`, and deploys the Pages artifact after a push to `main` or a manual workflow dispatch. It uses GitHub's official Pages actions and repository-scoped permissions.

The repository's **Settings → Pages → Build and deployment → Source** must be **GitHub Actions**. Enabling that setting requires sufficient repository permissions and a GitHub plan that supports Pages for the repository's visibility. Do not change repository visibility simply to make hosting work.

Expected project-site location after a successful deployment: `https://yuchi-wang02.github.io/SPMO-ETF-test/`. This is a target address, not proof that the site is live. Confirm the workflow's deploy result and make an HTTP request to the published page before advertising it as available.

The workflow publishes presentation files, not raw research data. Repository secrets, provider exports, source receipts and the prior chat must not be copied into `site/`.

## Runtime notes

Future tasks should use the existing `/workspace/SPMO-ETF-test` checkout rather than creating another worktree. The files and Python runtime can persist in an environment snapshot; a local HTTP server does not. Start a new server only when a task needs a preview. No server is required to read or validate the design.
