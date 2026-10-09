# Rebalance Lab: audience and presentation

## Identity and promise

**Rebalance Lab** presents **Rebalancing Frequency in Momentum Portfolios**. The title names the research subject directly. The site compares monthly and semiannual portfolio formation, reporting returns, drawdowns, trading activity and transaction costs within each study's stated data and accounting limits. SPMO remains a relevant benchmark in the stock study and part of the research history, rather than the umbrella identity.

The primary readers are researchers, students and investment practitioners who need to understand the study design, measured results and limitations before inspecting the code. A technical reader can follow exact rules, source provenance, independent checks and reproduction instructions. The site serves these readers through two routes: **review the empirical findings** and **inspect or reproduce the analysis**.

## Lead with the observed answers

The homepage opens with the research subject and a concise empirical summary: observed frequency differences vary by period, portfolio and modeled trading cost. Its language should be precise and academic without implying peer review, publication acceptance or causal identification. It presents two equally visible study cards:

| Study | First result to show | Context that stays beside it |
|---|---|---|
| Stock cohort | Monthly led by 1.23 percentage points of cumulative return at 5 bps per side | Fixed 100-issuer cohort, 20 positions, 2025–October 2, 2026; −6.93 points in 2025 and +8.84 in 2026 YTD |
| Sector ETFs | Monthly trailed by 0.49 percentage points of CAGR per year at 5 bps per side | Nine ETFs, up to three positions, 2001–2025; shallower drawdown, higher trading activity and calendar sensitivity |

The two headline quantities use different units. Label “cumulative return difference” and “annualized growth difference” in full. Do not combine them into an average, a winner count, a confidence score or a claim that the studies independently validate each other. Both are retrospective and use vendor-price proxies.

The completed-study cards lead to their respective reports. A concise status panel explains that the stricter original 75-stock protocol remains incomplete, with a link to its data audit and research plan. It must not make visitors infer that no market experiment exists, or that a completed pilot satisfies the original contract.

## Build each report around a decision

Each report follows the same reading order while preserving its own methodology:

1. **Question and answer.** State the compared schedules, selected primary period, base cost and measured difference. Put the relevant limitation close to the number.
2. **Path and risk.** Show matched portfolio growth and drawdown for the same interval, with readable units and an accessible table. Keep benchmark exposure differences explicit.
3. **Cost and sensitivity.** Let readers choose among independently rerun cost scenarios. Display unfavorable years and all prespecified calendar phases where that study actually ran them.
4. **What changed.** Explain trading activity, cash exposure and holdings evidence where supported. Describe observed differences without attributing them to a market story that was not tested.
5. **Trust and reproduction.** Link the exact configuration, aggregate artifacts, independent replay, data limitations and instructions. Keep this reachable without making it the lead narrative.

Stock results keep the 2025 formation/burn-in and 2026 measurement periods distinct. Full-period growth compounds them; annual return spreads do not add. The ETF report keeps its 25 complete years separate from 2026 YTD. A shorter favorable interval must never replace the declared primary result.

## Keep the evidence boundaries visible

Use plain labels such as **historical experiment**, **vendor-adjusted price proxy**, **independently replayed**, and **original protocol incomplete**. Independent replay refers to calculations on preserved inputs, not independent validation of every source price, adjustment or historical information timestamp.

The stock study uses dated issuer capitalization and a fixed baseline cohort, with one disclosed FISV reconstruction and unverified corporate-action entitlements. The ETF study uses adjusted fund-price units and historical fund exposures whose sector definitions changed. These are material assumptions, not footnotes to hide behind a generic disclaimer.

Negative findings deserve the same space, color strength and downloadable evidence as positive findings. A green badge should mean a specific check passed, not that a strategy is recommended. Avoid an overall “percentage complete” or a blended readiness rating across studies. For the original protocol, track input acceptance, engine reconciliation and completed market comparisons separately.

## Information architecture

The site homepage is the research landing page. Existing `stocks.html` and `pilot.html` remain the report routes. The [research index](../README.md) groups the deeper record into results, methods, reproduction, data and history. The root repository README gives the same entry points and concise findings; it does not duplicate the complete reports.

Documentation is organized by reader task: `docs/studies/` for findings, `docs/methods/` for rules, `docs/validation/` for replay evidence, `docs/data/` for source and acceptance work, and `docs/project/` for presentation and publishing. Source artifacts retain their historical names and identifiers. The public identity is Rebalance Lab. The [repository](https://github.com/Yuchi-Wang02/rebalance-lab) was renamed through the owner's GitHub interface, and maintained links use the new [site address](https://yuchi-wang02.github.io/rebalance-lab/). Verify the deployed revision after publication before sharing it.

Provider descriptions, raw-file hashes, technical receipts and synthetic-test counts belong in the inspection layer. Researchers should first encounter the research question, comparison design, principal findings and limitations, with a clearly labeled method or reproduction link leading to the supporting evidence.

## Visual and interaction design

Use an editorial layout with strong typography, readable axes and space between decisions. Keep the restrained ivory, navy and green palette, with amber for unresolved assumptions. Give both experiments comparable visual weight. Use local assets and system fonts; avoid decorative market tickers, fabricated charts or promotional language.

The central question, study scope, headline units, limitations and navigation must be present in semantic HTML. JavaScript adds optional cost, period and comparison controls. Controls need descriptive labels, visible keyboard focus and a usable narrow-screen layout. Respect reduced motion. Loading, missing or malformed data must produce an explicit unavailable state rather than zero returns or a false pass.

## Review the experience

A first-time reader should be able to identify both studies, explain why their headline numbers differ in units, find an unfavorable comparison, and reach a method without searching the repository. A technical reviewer should locate the exact configuration, retained input hashes, replay evidence and remaining source limitations.

Check desktop and mobile layouts, keyboard navigation, accessible result tables, source links, loading/error states and consistency between displayed numbers and saved artifacts. Traffic, stars and test counts do not measure investment merit. The intended outcome is an understandable, inspectable research record.
