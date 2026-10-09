# Research blueprint

**Question: does faster momentum rotation pay after trading costs?** The primary reader is an ETF investor who understands diversification and expenses but should not need to inspect Python to understand the comparison. The research record remains available to technical reviewers.

This is a plan for evaluating a strategy, not a market result. Price diagnostics and a synthetic engine exist; audited historical strategy inputs and formal engine acceptance remain outstanding. The [protocol](original-stock-protocol.md) and [primary configuration](../../configs/experiment.v1.json) retain the existing v0.2 trading rules.

## The main comparison

Compare **M12 against S12**: monthly versus March/September selection using the same 12–1 signal, historical universe, top-75 rule, score/capitalization weights, cap and execution assumptions. The only assigned difference within this pair is selection frequency. Its realized consequences can include different holdings, exposure, cash, trades and costs.

| Role | Comparison | What it can establish |
|---|---|---|
| Primary | M12 − S12 | The modeled frequency effect for the chosen signal, window and assumptions |
| Within-study robustness | MMIX − SMIX | Whether the frequency effect also appears with the prespecified blended signal |
| Interaction | (MMIX − SMIX) − (M12 − S12) | How the modeled frequency effect changes with the signal |
| Product context | All four arms beside SPMO and SPY | Practical scale and context, with differences beyond frequency disclosed |

The blended pair shares data, market conditions and much of its exposure with the primary pair. It is a robustness check within one study, not independent replication. The slower custom strategy is not a reconstruction of the official SPMO index methodology. No best-performing arm replaces the declared primary comparison.

## How to assess the tradeoff

Lead with the net-return difference in percentage points at the base **5 bps per side** assumption. Place it beside three measures readers can interpret:

- **Drawdown:** each account's worst daily-close peak-to-trough decline within the same reporting period, including the anchor. A return advantage can come with a deeper decline.
- **Extra trading:** the difference in summed absolute executed buy-plus-sell notional divided by pretrade NAV at each event. This is a two-sided activity measure, with no hidden division by two.
- **Cash exposure:** show the daily cash-weight path, its arithmetic mean over reporting sessions after the anchor, and its maximum. Receivables remain separate from spendable cash. This helps explain apparent return or drawdown differences.

Rerun all arms at **0, 5, 10 and 25 bps per side**. Costs alter cash and subsequent portfolio paths; use independently simulated accounts at each rate. If the observed grid brackets a sign change in the primary spread, report that bracket. If it does not, state that no crossing was observed in the tested range. A more precise break-even estimate needs a separately stated rerun/search procedure; simple linear fee subtraction is insufficient.

There is no new numerical risk hurdle or overall winner score. Report the return, drawdown, activity and exposure tradeoff, including a zero or negative advantage, before making a practical interpretation.

## What would make the evidence stronger

1. **Verify the data on a small event-led sample.** Check historical membership, identifiers, price units, class-level cap, availability times and corporate-action accounting against inspectable source records. The [sample plan](../data/acceptance-sample.md) defines the acceptance evidence. A larger price download cannot replace this step.
2. **Keep the fixed 2026 case study.** Preserve its existing warm-up, 2025 burn-in, December 2025 measurement anchor and October 2, 2026 cutoff. The market history informed the idea, so the result is retrospective even with correct data timing.
3. **Check all six semiannual phases.** Keep March/September primary and report every pair in the [supplementary configuration](../../configs/calendar-sensitivity.v1.json). A descriptive mean and range reveal schedule sensitivity; overlapping phases do not add independent evidence. See the [execution guide](calendar-sensitivity.md).
4. **Freeze a longer-history extension after coverage is known.** Prespecify the exact interval, complete calendar years, warm-up, burn-in, annual paired comparisons, costs and data versions before running it. Continue accounts across years; measure annual changes without resetting holdings. Report all eligible years and explain excluded coverage. No start date or result is invented in this plan.

The multi-year extension remains retrospective, and annual effects can be dependent. It may show persistence or fragility across episodes; it does not automatically establish statistical significance or an untouched holdout. A future forward-recorded study would require its own timestamped freeze.

## Publication order

The page should answer five questions in order: **What changes? How will we judge it? What does trading cost? What evidence exists now? Where can I inspect the method?** Use the primary pair first and let readers expand the complete four-arm design.

When market evidence exists, add matched net wealth and drawdown plots, all-cost comparisons and explanations tied to actual holdings/trades. Publish the complete comparison table and limitations alongside any attractive chart. Until then, use explanatory schedules and assessment definitions, with a direct statement that market results are unavailable. No numeric return placeholders, invented curves or overall completion percentage are needed.

Show three separate readiness gates: **historical inputs accepted**, **engine reconciled**, and **all prespecified market comparisons completed**. Provider details, hashes and test receipts belong in expandable reproduction material. Gate status should state the evidence and remaining dependency, not imply that passing software tests validates performance.
