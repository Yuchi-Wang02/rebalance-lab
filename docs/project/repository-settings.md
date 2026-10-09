# Repository identity and owner settings

The public project name is **Rebalance Lab**. Its research question is **Does trading more often pay?** SPMO is a benchmark and part of the project's history; it is not the umbrella brand.

The website and documentation use this identity. The current repository slug remains `Yuchi-Wang02/SPMO-ETF-test`, and its live site remains <https://yuchi-wang02.github.io/SPMO-ETF-test/>.

## Settings prepared for the repository owner

| Field | Proposed value |
| --- | --- |
| Repository name | `rebalance-lab` |
| Description | Does trading more often pay? Reproducible momentum experiments with trading costs, calendar sensitivity, and transparent data limits. |
| Website before rename | `https://yuchi-wang02.github.io/SPMO-ETF-test/` |
| Website after rename and deployment | `https://yuchi-wang02.github.io/rebalance-lab/` |
| Topics | `portfolio-rebalancing`, `momentum-investing`, `quantitative-finance`, `backtesting`, `transaction-costs`, `empirical-finance`, `reproducible-research`, `financial-data`, `python`, `data-visualization`, `etf`, `github-pages` |

On October 9, 2026, GitHub reported the account's repository role as `ADMIN`, but rejected both the repository-settings request and the topics request with HTTP 403, `Resource not accessible by integration`. The connected app can publish repository content but its credential does not authorize these settings operations. These metadata changes have **not** been applied. No new credential is needed for reading or running this project.

The owner can set the description, website and topics using the repository's **About → Edit** control. The name is under **Settings → General → Repository name**. Do not change visibility or other repository settings as part of this rebrand.

## When the repository is renamed

1. Rename to `rebalance-lab` in GitHub's repository settings.
2. Replace the public repository and Pages URL prefixes in maintained Markdown and site files. Keep numerical configurations, source receipts and historical evidence unchanged.
3. Update the local remote: `git remote set-url origin https://github.com/Yuchi-Wang02/rebalance-lab.git`.
4. Run the checks in [CONTRIBUTING](../../CONTRIBUTING.md), push, and verify both the Pages deployment and the actual pages at the new address.
5. Update the About website field only after the new address works.

GitHub redirects old repository links after a rename, but an old project Pages URL is not guaranteed to redirect. Share the new verified site URL. Internal site navigation already uses relative links.
