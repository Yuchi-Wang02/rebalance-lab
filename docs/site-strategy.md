# Audience and GitHub Pages strategy

## Positioning and audience

**Does faster momentum actually pay?** The site explains a controlled comparison of returns, risk and trading costs. Its primary audience is ETF investors who want evidence and can understand expenses and drawdowns without learning the implementation first. Researchers and quantitative developers should be able to inspect every rule and reproduce the evidence through a second layer.

The website is an approachable research story. Its credibility comes from clear comparisons, visible limits and complete reporting of negative as well as positive outcomes. A synthetic test result is engineering evidence; a price download is acquisition evidence. Neither belongs in a headline implying investment performance.

## The page's reading order

1. **Question.** Lead with “Does faster momentum actually pay?” and a short explanation that more frequent selection may find leaders sooner but creates extra trading. State that market results are currently unavailable.
2. **Primary pair.** Show monthly M12 beside March/September S12, both using the same 12–1 signal and common portfolio rules. An explanatory schedule helps readers see the intervention. Put the full four-arm matrix in expandable methods; the blended pair is within-study robustness, not independent replication.
3. **Assessment criteria.** Explain net-return difference, drawdown, additional traded notional and cash exposure. Until a market run exists, display definitions and the planned comparison, with no numeric return placeholders or invented equity curves.
4. **Cost.** Explain the 0/5/10/25 bps-per-side reruns and how buys and sells both incur costs. A simple fee illustration can teach units, but must be labeled as arithmetic, not a forecast, ledger simulation or strategy break-even calculation.
5. **Readiness.** Show three separate evidence gates: historical inputs accepted, engine reconciled, and every prespecified market comparison completed. State the present evidence and next dependency for each gate. Do not add an overall percentage complete.
6. **Full method and reproduction.** Expand the four arms, calendar sensitivity, data sources, adjustment/availability limits, test receipts and provenance. Link the [research blueprint](research-blueprint.md), [protocol](experiment-design.md), [sample acceptance plan](data-acceptance-sample.md), [calendar guide](calendar-sensitivity.md), source catalog and code.

Provider cards, raw-file hashes and test counts serve inspection after the reader understands the research question. They should not crowd out the main comparison. Visible summaries remain understandable without opening the technical details.

## What appears when results exist

Lead with the primary 5 bps net-return spread beside both drawdowns and extra traded notional. Show synchronized net wealth and drawdown plots on the same period, with cost controls selecting independently rerun paths. Include cash exposure so that lower drawdown is interpreted in context. Each figure identifies its dates, cost convention, data version and retrospective status.

Publish the complete four-arm/all-cost table. Show all six semiannual phases in a sensitivity view, marking March/September as primary and labeling their mean/range as descriptive. Do not select the best phase or call the six correlated paths independent tests. A longer-history view should show all eligible complete years and annual paired differences under its separately frozen protocol; the fixed 2026 case study stays clearly labeled.

Explain important differences with auditable holdings, trades and fees where the evidence allows. Avoid attributing returns to a particular trade without an explicit attribution method. A negative main result deserves the same visual prominence and reproducibility materials as a positive one. Downloads include only artifacts the project may redistribute.

## Visual and interaction design

Use an ivory background, dark navy text, restrained green for evidence and warm amber for unresolved tradeoffs. A serif question headline and readable system sans-serif body create a quiet editorial identity. Favor a few explanatory graphics and generous space over a dense dashboard. Keep assets local and avoid external fonts, analytics or a runtime framework.

The main question, pair, criteria and status must be in semantic HTML. JavaScript adds optional exploration. Expandable sections and controls need descriptive labels, visible focus, keyboard operation, narrow-screen layouts and reduced-motion support. Loading or malformed data summaries must produce an honest unavailable state rather than zero values or a false pass.

## Review the experience

A reader should quickly identify the primary pair, say what is held constant, describe the cost tradeoff and find why market results are not yet available. A technical reviewer should reach exact definitions, timing assumptions, source evidence and reproduction commands without searching the entire repository.

Check mobile and desktop layouts, keyboard use, contrast, direct section links, loading/error states and source links. These are usability checks, separate from investment evidence. Traffic, stars and passing software tests do not establish strategy success.
