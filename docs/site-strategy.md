# Audience and GitHub Pages strategy

## Positioning

**A transparent research notebook made approachable—not a fund sales page.** The memorable question is: “Can momentum move faster without paying away the edge?” Visitors should leave understanding the experiment and its evidence level, even before results exist.

## Who it serves

| Audience | Their question | What the page should deliver |
|---|---|---|
| Primary: curious ETF investors who want evidence | Why change the rebalance schedule, and what could go wrong? | A clear hypothesis, the 2×2 comparison, visible cost tradeoff and honest research status |
| Secondary: quantitative developers, researchers and technical reviewers | Can I inspect or reproduce the method? | Exact protocol, data provenance, connection constraints, code/configuration links and future ledgers |
| Optional: collaborators or hiring reviewers | Does this project show disciplined research and implementation? | Traceable decisions, accessible interaction, reproducibility checks and negative-result reporting |

The site is not intended as a buy/sell signal service, personalized portfolio recommendation or claim to offer an ETF. Avoid inflated investor-marketing language such as “proven alpha” or “beat the market.”

## The visitor journey

1. **Understand the question:** large editorial headline, a short plain-English explanation, and a visible “design stage” status.
2. **Understand the experiment:** an interactive four-cell matrix. Selecting a cell reveals what changes and what stays fixed. Annual selection cadence is shown as a calendar, not as a fabricated return curve.
3. **Understand the price of activity:** a labeled cost calculator showing direct fee arithmetic at a fixed reference NAV. It is neither an empirical forecast nor a full backtest.
4. **Understand the evidence:** a provider map distinguishes documentation, connection, entitlement and data-audit gates. Give concrete source links rather than vague “data from the internet.”
5. **Go deeper:** link to the protocol, source registry, data contract and repository. A roadmap explains which work is complete and what unlocks results.

## Visual language

Use an ivory background, dark navy text, a restrained green research accent and warm amber for tradeoffs. A large serif headline creates an editorial identity; a system sans-serif supports readable methods. Use generous whitespace and a small number of strong diagrams rather than dashboard clutter. All assets are local and no external font, analytics or runtime framework is required.

## Interaction and accessibility

The experiment matrix and cost controls must work by keyboard and on narrow screens. Provide visible focus, descriptive labels, semantic headings, reduced-motion support and adequate contrast. Keep the substantive story available in HTML; JavaScript adds exploration rather than hiding the source content.

## What appears after results exist

Only after data and engine gates pass, add synchronized gross/net wealth and drawdown plots, a four-arm comparison table, cost-sensitivity results and downloadable licensed/derived artifacts. Every figure must identify its window, cost scenario, data version and experimental status. Avoid a prominent “winning” chart selected from many unreported attempts.

Before that stage, do not fill chart slots with invented equity curves or zero-return placeholders. Design quality should come from the question, the explanatory graphics and the clarity of the work—not from false evidence.

## Lightweight success checks

Without adding tracking by default, test whether a reader can find the main hypothesis, identify the controlled pair, name a data limitation and reach the protocol within a few clicks. Technical quality checks cover responsive layouts, keyboard use, source/repository links and functioning controls. Traffic and stars are not evidence that the strategy works.
