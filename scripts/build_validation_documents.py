#!/usr/bin/env python3
"""Author the local validation narrative from the validated public summary."""
import hashlib
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TITLE="Rebalance Lab: A Validation Study of Momentum Rebalancing"
SUBTITLE="Calendar Timing, Trading Costs, and Reproducible Backtests"
SITE="https://yuchi-wang02.github.io/rebalance-lab/"
REPO="https://github.com/Yuchi-Wang02/rebalance-lab"
def write(name,body):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body.strip()+"\n",encoding="utf-8")
def pct(v):return f"{100*v:.2f}%"


def documents(s):
    runs={r["run_id"]:r for r in s["runs"]};ids=s["primary_ids"]
    m,a,t,b,spy=[runs[ids[k]] for k in ("monthly","semiannual","tranched","weight_reset","benchmark")]
    ci=[r for r in s["primary_intervals"] if r["primary_block"]]
    risk_rows=[]
    for label,r in [("Monthly",m),("March / September",a),("Six-sleeve tranche",t),("SPY context",spy)]:
        q=r["metrics"]["full_period"];risk=r["monthly_risk"]
        risk_rows.append(f"| {label} | {pct(q['cagr'])} | {pct(q['max_drawdown'])} | {risk['sharpe_monthly_annualized']:.3f} | {pct(risk['tracking_error_monthly_annualized'])} | {risk['beta_to_SPY_excess_returns']:.3f} | {q['annualized_two_sided_turnover']:.2f}x |")
    risk_table="| Portfolio | Net CAGR | Daily max drawdown | Sharpe | Tracking error | SPY beta | Traded NAV / year |\n|---|---:|---:|---:|---:|---:|---:|\n"+"\n".join(risk_rows)
    interval_table="| Monthly minus | CAGR difference, pp/year | Paired 95% interval |\n|---|---:|---:|\n"+"\n".join(f"| {label} | {r['cagr_difference_pp']:+.2f} | [{r['ci95_difference_pp'][0]:+.2f}, {r['ci95_difference_pp'][1]:+.2f}] |" for label,r in zip(["March / September","Six-sleeve tranche"],ci))
    write("README.md",f'''# {TITLE}

**The sign of the monthly-minus-semiannual performance difference changes across six rebalancing calendars.** In the 2001-2025 sector-ETF study, the 12-1 comparison at 5 bps per side ranges from **-0.92 to +0.53 percentage points of CAGR per year**. The designated March/September comparison is **-0.49 pp/year**.

![All six semiannual calendars and four cost scenarios](site/assets/validation-calendar-costs.svg)

*Monthly minus semiannual CAGR; positive favors monthly. The outlined March/September row is the designated reference. Both signals and every calendar/cost cell are reported.*

[Research site]({SITE}) · [Four-page validation brief](site/assets/rebalance-lab-validation-brief.pdf) · [One-page validation memo](site/assets/rebalance-lab-validation-memo.pdf) · [Executed notebook](notebooks/validation-study.ipynb)

## What this repository demonstrates

- Rules fixed before the extension runs, with prior exposure to the history disclosed.
- Signals formed at the close, with execution at the next exchange-session open.
- Separate self-financing accounts for 0, 5, 10 and 25 bps per executed side.
- All six semiannual phases reported, without choosing the best observed calendar.
- A second accounting implementation and a separate tranche/statistical reconciliation.

## Test the mitigation, then qualify the conclusion

Six semiannual sleeves receive one-sixth of initial capital and subsequently run without transfers or trade netting. This pooled portfolio returns **{pct(t['metrics']['full_period']['cagr'])} CAGR**, compared with **{pct(m['metrics']['full_period']['cagr'])}** for monthly and **{pct(a['metrics']['full_period']['cagr'])}** for March/September. Its **{pct(t['metrics']['full_period']['max_drawdown'])}** maximum drawdown is deeper than both primary alternatives.

{interval_table}

Intervals use 10,000 paired stationary bootstrap draws of 300 net monthly returns, with mean block length 12 months. Both include zero. The observed primary monthly disadvantage does not establish a general frequency ranking. The tranche diversifies the calendar allocation; this sample does not show that it eliminates risk or timing dependence.

## Read the evidence

| Material | Purpose |
|---|---|
| [Research report](docs/studies/validation-study.md) | Findings, risk, uncertainty and the A/B/C appendix |
| [Method protocol](docs/methods/validation-study.md) | Exact portfolio, tranche and inference rules |
| [Validation memo](docs/validation/validation-memo.md) | Scope, lineage, replication, judgment and residual risk |
| [Design decisions](docs/methods/design-decisions.md) | Five technical choices and their alternatives |
| [Reproduction guide](docs/reproduction.md) | Public-input analysis and private-snapshot engine replay |

The [stock pilot](docs/archive/studies/stock-pilot.md) is a companion case. The [original 75-stock protocol](docs/archive/methods/original-stock-protocol.md) is archived as incomplete research history after its data requirements could not be met.

## Reproduce locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-research.txt
.venv/Scripts/python scripts/validate_validation_artifacts.py
.venv/Scripts/python -m unittest discover -s tests -p 'test_*.py'
.venv/Scripts/python -m http.server 8000 --directory site
```

The example uses Windows paths. On macOS/Linux replace `.venv/Scripts/python` with `.venv/bin/python`. Full commands and input requirements are in the reproduction guide. No network request or credential is required for the public companion notebook.

## Evaluation focus and owner contribution

The project connects accounting and control habits with Business Analytics and AI: define the measurement, reconcile the account, inspect exceptions and state what the evidence supports. It is a financial case for model-validation and AI-evaluation readers.

The owner selected the audience, financial scope and validation focus; personally reconciled one historical trade using Python; and reviewed the calendar, uncertainty and evidence-boundary interpretations in writing. AI assisted the implementation, numerical checks and drafting. The exact signal-window explanation and an observed timed presentation remain pending; full owner reproduction of the notebook has not been verified. See the [dated contribution record](results/owner-review-progress.json).

## Limitations

This is a retrospective nine-sector-ETF study using vendor-adjusted price and next-open execution proxies, zero-interest cash and fixed modeled costs. Sector definitions changed over time. Bootstrap intervals are conditional on the observed history and resampling assumptions. Separate implementations reconcile arithmetic on the same inputs; the same AI agent authored them, so they do not establish independent reviewer agreement, source-price accuracy or achievable execution. Original code and documentation use the MIT license; raw vendor exports remain excluded.
''')
    write("docs/studies/validation-study.md",f'''# A validation study of momentum rebalancing

*Research version 1 - 9 October 2026. Retrospective study; primary window 2001-2025.*

## Question and judgment

Does more frequent selection and reweighting improve this long-only momentum portfolio? The designated monthly-minus-March/September CAGR difference is -0.49 pp/year, but its sign changes across the six semiannual schedules. The primary paired interval crosses zero. The evidence supports calendar sensitivity in this sample; it does not support an optimal frequency or a general causal explanation based on timing luck.

## Calendar and cost sensitivity

![Complete calendar and cost grid](../../site/assets/validation-calendar-costs.svg)

For 12-1 at 5 bps, monthly wins against three phases and loses against three. Differences range from -0.92 to +0.53 pp/year. At 25 bps, it trails all six. The blended recipe is a robustness check on the same history, not independent replication. Six phases share the monthly control, assets and dates. Calendar dispersion is a scenario range, not a confidence interval.

## A calendar-diversified comparison

The tranche holds six autonomous semiannual sleeves. All receive equal initial capital before the 3 January 2000 first execution. Sleeve capital then drifts; the 2000 year-end reporting anchor only normalizes the pooled NAV. There are no sleeve transfers, daily re-equalization, additional signal rules or cross-sleeve order netting. Cash, units, NAV, gross trading and fees are scaled and summed from the existing accounts.

![Wealth and daily drawdown](../../site/assets/validation-wealth-drawdown.svg)

{risk_table}

*5 bps per side. Sharpe, tracking error and beta use 300 monthly simple returns; tracking error and beta reference SPY. Cash earns zero even though RF is subtracted when evaluating excess return. Drawdown uses daily closes. Trading is gross buys plus sells, without halving. SPY is opportunity-cost context with different exposures, not a matched frequency control.*

The tranche's observed CAGR lies between the primary alternatives. Its maximum drawdown is {pct(t['metrics']['full_period']['max_drawdown'])}, compared with {pct(m['metrics']['full_period']['max_drawdown'])} monthly and {pct(a['metrics']['full_period']['max_drawdown'])} for March/September. Pooling calendars is not a guarantee of better growth or a shallower drawdown.

## Uncertainty

{interval_table}

![Paired bootstrap intervals](../../site/assets/validation-intervals.svg)

These are percentile intervals for a difference of compounded annual growth rates. The same monthly index sequence is sampled for all accounts, preserving their contemporaneous dependence. There are 10,000 draws; primary expected block length is 12 months, with 6 and 24 months reported below. Both primary intervals include zero. That is evidence of uncertainty, not proof that the policies are equivalent.

| Mean block, months | Monthly - Mar/Sep, 95% CI | Monthly - tranche, 95% CI |
|---:|---:|---:|
'''+"\n".join(f"| {length} | "+" | ".join(f"[{r['ci95_difference_pp'][0]:+.2f}, {r['ci95_difference_pp'][1]:+.2f}]" for r in s['primary_intervals'] if r['mean_block_months']==length)+" |" for length in [6,12,24])+f'''

The bootstrap resamples realized net portfolio returns; it does not replay selection on synthetic price histories. Its assumptions, nonstationarity and retrospective choices remain sources of risk. No best calendar or cost is selected from the grid.

![Cost sensitivity for two signals](../../site/assets/validation-costs.svg)

## Appendix: selection updates and weight resets

A refreshes selection and weights semiannually. B retains A's selected names and cash slots but resets weights monthly. C refreshes both monthly. At the primary signal, phase and cost, A/B/C CAGR is **{pct(a['metrics']['full_period']['cagr'])} / {pct(b['metrics']['full_period']['cagr'])} / {pct(m['metrics']['full_period']['cagr'])}**. B-A is +0.12 pp/year and C-B is -0.61 pp/year. These are sequential conditional comparisons, not a unique causal allocation of performance. The three mean-log-return HAC comparisons use 12 lags and Holm adjustment within that appendix family; their intervals and exact units are in the saved summary.

## Secondary 2026 case

Through 2 October 2026, monthly returns {pct(m['metrics']['ytd2026']['total_return'])}, March/September {pct(a['metrics']['ytd2026']['total_return'])}, and the tranche {pct(t['metrics']['ytd2026']['total_return'])}. These continuous-account partial-year returns are not annualized and are excluded from primary inference.

## Evidence and limits

The legacy ETF replay checks 60 accounts. The mechanism replay checks 108 accounts and 726,732 daily states. The extension reconciliation checks eight pooled paths, 53,832 daily states, 34,800 monthly rows and risk/bootstrap calculations. These checks address implementation consistency on a preserved snapshot. Same-agent authorship, vendor-price proxies, changing fund sectors, fixed costs, zero-interest cash, and nonstationarity remain limitations. See the [validation memo](../validation/validation-memo.md) and [reproduction guide](../reproduction.md).
''')
    write("docs/methods/validation-study.md",'''# Method protocol

## Data and timing

Nine original sector ETFs: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV and XLY; SPY is context. Preserved Yahoo chart responses cover their common sessions from 22 December 1998 through 2 October 2026. Signals and accounts start at the 31 December 1999 close; first execution is 3 January 2000. The primary anchor is 29 December 2000, the last common session of 2000, and the primary endpoint is 31 December 2025. No liquidation or capital reset occurs at reporting boundaries.

The signal for lookback L is `(P[t-21] / P[t-L] - 1) / (sample_sd(daily_returns_in_that_window) * sqrt(252))`. The primary recipe uses L=252. At t=1000, its prices are P[748] and P[979], and its volatility contains 231 simple daily returns r[749] through r[979], where r[k]=P[k]/P[k-1]-1. The most recent 21 returns r[980] through r[1000] enter neither numerator nor denominator. The mixed recipe weights the 252/126/63-session components 0.5/0.3/0.2. Scores must be positive; select up to three ranked ETFs. Each selected name receives one-third of post-fee NAV; unused slots stay as zero-interest cash.

Month-end closing decisions execute at the next exchange-session opening proxy. A monthly portfolio refreshes selection and weights monthly; each semiannual portfolio refreshes in its two designated signal months. Six phases cover Jan/Jul through Jun/Dec, with March/September retained as reference. Costs are 0/5/10/25 bps per side, each a separate self-financing account. Execution solves post-fee targets together with fees. Vendor adjusted closes and `Open * AdjClose / Close` are proxy units; no separate dividend cash is added.

## Six-sleeve tranche

For each signal and cost, six semiannual accounts each represent one-sixth of initial capital. Pooled NAV, cash, asset units, gross traded notional and fees are their scaled sums. The 2000 burn-in can create unequal sleeve capital before reporting starts; equalizing at the reporting anchor would change this protocol. No subsequent sleeve transfers or order netting are allowed. Pooled turnover on a trade date divides summed gross notional by pooled opening pretrade NAV, including non-trading sleeves marked at that opening.

## Inference and risk

Use exactly 300 aligned calendar-month net simple returns for 2001-2025. Primary differences are monthly minus March/September and monthly minus tranche, under 12-1 and 5 bps. Paired stationary bootstrap samples common monthly rows, with a geometric restart probability of 1/block_length and circular continuation. Seed 20261009; 10,000 draws; mean block lengths 12 (primary), 6 and 24. Calculate each sampled CAGR as `exp(12 * mean(log(1+r))) - 1`, then take percentile bounds of the paired CAGR differences. The calculation samples return paths, not prices or selection histories. No primary p-value claims or equivalence test are made.

Sharpe is `sqrt(12) * mean(R - RF) / sample_sd(R - RF)`. Tracking error is `sqrt(12) * sample_sd(R - R_SPY)`. Beta includes an intercept and regresses R-RF on R_SPY-RF. RF is the decimal monthly series from the captured Kenneth French factor archive; a revised historical series is not a point-in-time vintage. Daily volatility and maximum drawdown remain separate. Undefined zero-variance ratios are unavailable, never silently set to zero.

## Mechanism appendix

The already computed A/B/C extension is retained. A=semiannual selection/reset; B=semiannual selection/monthly reset with the complete target vector and cash slots frozen; C=monthly selection/reset. Same input and costs, one next-open fill at coinciding events. Conditional differences B-A and C-B telescope in log growth but do not identify unique causal mechanisms. Mean monthly log differences use Bartlett HAC12 with small-sample correction, normal intervals and Holm correction for three contrasts. Stationary bootstrap sensitivity remains attached to the appendix results.

## Registration and interpretation

The original history and calendar results were already inspected. The validation extension's rules were recorded and hashed before its tranche and interval calculation; this is retrospective freezing, not prospective registration or an untouched holdout. Freeze records and previous manifests remain preserved. No observed winning phase is promoted. Market-state, event, adaptive-rule and multi-factor studies are deferred.

[Machine-readable extension protocol](../../configs/sector-etf-validation.v1.json) · [Freeze record](../validation/etf-validation-protocol-freeze.json) · [Legacy ETF rules](../../configs/sector-etf-pilot.v1.json) · [Mechanism rules](../../configs/sector-etf-mechanisms.v1.json)
''')
    write("docs/validation/validation-memo.md",f'''# Validation memo

**Object:** Nine-sector-ETF momentum rebalancing, 2001-2025. **Date:** 9 October 2026. **Purpose:** assess a frequency claim and the reliability of its retrospective evidence. **Judgment:** calculation reconciled; general frequency superiority unsupported; remaining model and data risks disclosed.

## Scope

Compare monthly selection/reweighting with six semiannual calendars, four costs and two signals. Add six autonomous sleeves as a calendar-diversified comparison. The main study is 12-1 at 5 bps per side; 2026 YTD and A/B/C mechanisms are secondary. This is a financial research case, not a bank-approved model, live strategy or trading recommendation.

## Data lineage

Preserved vendor responses -> common-session adjusted open/close input -> fixed portfolio accounts -> independent accounting replay -> tranche sums -> monthly risk and paired intervals -> public derived CSVs and summary. Every capture, protocol and generated account has a SHA-256 manifest. Official French monthly RF is captured separately and joined to exactly 300 months. Hashes establish file identity, not independent authenticity of vendor observations.

## Independent implementation checks

The legacy verifier uses standard-library code and an analytic fee solution rather than the engine's bisection. It reconciles 60 paths. The mechanism verifier reconciles 108 paths and 726,732 daily states; maximum relative NAV error is 1.78e-14. A separate extension verifier imports no project calculation code and checks eight tranches, 53,832 daily states and 34,800 monthly rows, including Sharpe, tracking error, beta and bootstrap percentiles. Maximum relative tranche NAV error is {s['validation']['max_relative_tranche_NAV_error']:.2e}.

**Independence boundary:** the same AI agent authored the implementations and reviewed the outputs. Different calculations can expose implementation errors; they cannot exclude a shared misunderstanding of the specification. No external reviewer acceptance is claimed.

## Findings

- At 5 bps, changing only the semiannual calendar changes the 12-1 comparison's sign: -0.92 to +0.53 pp/year.
- Monthly minus March/September is -0.49 pp/year; paired 95% CI [-3.03, +2.11]. Monthly minus tranche is -0.22; CI [-2.44, +2.33]. Both span zero.
- Tranche CAGR is {pct(t['metrics']['full_period']['cagr'])}, but its daily maximum drawdown is {pct(t['metrics']['full_period']['max_drawdown'])}; calendar pooling does not guarantee lower risk.

## Limitations and residual risk

Historical results were inspected before this extension was specified. Adjusted units approximate total return and next-open execution, rather than a raw-share corporate-action ledger. Cash earns zero; costs are fixed and there is no spread, impact, capacity or tax model. ETF sector definitions changed. Bootstrap stationarity and block choice do not remove regime or design-selection risk. Source-price accuracy and real execution remain unverified. Written result and judgment reviews have been accepted; exact signal-window understanding and an observed oral presentation remain pending. Owner mastery is not certified.

## Disposition

Accept as a reproducible, bounded historical validation case. Do not use it to select an optimal schedule, assert causal timing attribution, certify executable returns or establish personal technical mastery. Publish all tested comparisons and keep computation completion, owner readiness and deployment status separate.

[Result summary](../../site/data/validation-study-summary.json) · [Extension receipt](../../site/data/validation-study-replay.json) · [Reproduction](../reproduction.md)
''')
    write("docs/methods/design-decisions.md",'''# Design decisions and questions for the owner

These explanations document the implemented design and its tradeoffs. They are AI-assisted technical notes, not reconstructed statements about what the owner thought when the original choices were made. The owner can endorse, revise or reject each rationale after review; actual responses are recorded separately.

## 1. Why skip the most recent 21 sessions?

**Rule:** return is P[t-21]/P[t-252]-1. At t=1000, use P[979]/P[748]-1; the far endpoint is measured from t, not from t-21. **Rationale:** measure a medium-horizon trend without including the latest month; this follows a common momentum convention and makes the research recipe explicit. **Cost:** a sudden trend reversal can be ignored for a month. **Alternative:** no skip or a shorter skip, specified as a separate test rather than selected from this sample. **Owner prompt:** show the two endpoint prices and explain exactly which returns are excluded.

## 2. Why divide by volatility?

**Rule:** divide each horizon's price return by sample daily-return volatility in the same endpoints, annualized by sqrt(252). For L=252, use the 231 returns from t-251 through t-21, with ddof=1; the latest 21 returns are excluded. **Rationale:** compare momentum relative to recent variability rather than rank only raw price gains. **Cost:** ranking depends on an estimated denominator and its window; low volatility can magnify a score. **Alternative:** raw momentum or an independently specified volatility window. This ranking adjustment does not make the portfolio volatility-targeted: holdings still use one-third slots. **Owner prompt:** explain how two ETFs with the same gain can receive different scores.

## 3. Why closing signals and next-open execution?

**Rule:** compute with the decision close and trade at the next exchange-session adjusted opening proxy. **Rationale:** the completed closing observation is available before the modeled fill. **Cost:** overnight gaps and opening frictions matter; the proxy is not an executable quote. **Alternative:** a later execution or a genuinely available intraday signal, with a different data contract. **Owner prompt:** identify a signal/fill date pair and explain what same-close execution would assume.

## 4. What can adjusted prices represent?

**Rule:** adjusted close for signals; Open times AdjClose/Close for execution. **Rationale:** a consistent vendor-adjusted total-return proxy without adding dividend cash twice. **Cost:** vendor revisions, dividend reinvestment conventions, distributions and spin-offs may diverge from a raw-share ledger; a retrospectively adjusted opening value is not an actual opening fill. **Alternative:** raw prices, share changes, ex/pay dates and a corporate-action ledger. **Owner prompt:** distinguish a proxy unit from a real ETF share and name one risk the replay cannot resolve.

## 5. Why is turnover buys plus sells, not divided by two?

**Rule:** sum absolute executed buy and sell notional, divide by pretrade NAV; aggregate over the period, then divide by 25 for annual activity. **Rationale:** the cost model charges each side, so both purchases and sales generate fees. **Cost:** the reported number differs from one-way industry turnover conventions. **Alternative:** also report one-way turnover under an explicit definition, without changing fee accounting. **Owner prompt:** selling $100 and buying $100 generates $200 gross traded notional and $0.10 fee at 5 bps per side, not $0.05.

## Further decision: what is diversified by tranching?

One-sixth allocation at formation spreads calendar exposure across six autonomous sleeves. Sleeve wealth subsequently drifts. It diversifies a scheduling choice, not necessarily common holdings, market risk or drawdowns. The observed -40.91% maximum drawdown stays in the result even though it weakens a favorable mitigation story.

## Personal contribution record

Confirmed in the conversation: the owner selected model-validation/AI-evaluation readers, the financial-project-only scope, calendar sensitivity as the principal story, and three short review checkpoints. Implementation, numerical checks and narrative drafts were AI-assisted. The owner personally reconciled one historical trade and submitted accepted written explanations of calendar sensitivity, paired uncertainty, pooled drawdown and the price-source/fill-evidence boundary. The exact signal-window explanation remains unresolved; observed oral timing and owner notebook execution are absent. The [dated public progress record](../../results/owner-review-progress.json) distinguishes these contributions from AI implementation. Historical rationales above are not attributed to the owner without an actual endorsement.

[Methods](validation-study.md) · [Validation memo](../validation/validation-memo.md)
''')
    write("docs/reproduction.md",'''# Reproduction and evidence guide

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
''')
    return risk_table,interval_table


def head(title,route):
    description="A retrospective financial validation case: calendar sensitivity, tranched momentum portfolios, paired uncertainty and reproducible accounting."
    return f'''<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{description}"><title>{title} · Rebalance Lab</title><link rel="canonical" href="{SITE+route}"><meta property="og:type" content="website"><meta property="og:site_name" content="Rebalance Lab"><meta property="og:title" content="{title}"><meta property="og:description" content="{description}"><meta property="og:url" content="{SITE+route}"><meta property="og:image" content="{SITE}assets/validation-preview.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="Momentum rebalancing validation: calendar sensitivity and paired uncertainty"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{description}"><meta name="twitter:image" content="{SITE}assets/validation-preview.png"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="styles.css"><link rel="stylesheet" href="validation.css"></head>'''


def shell(title,route,body,script=""):
    import re
    body=body.replace("or a risk-free mitigation.","or show that pooling eliminates risk.")
    body=re.sub(r'(<figure class="v-figure">)(<img [^>]+>)',r'\1<div class="v-plot" tabindex="0" role="region" aria-label="Scrollable research figure">\2</div>',body)
    body=body.replace('<figcaption>','<figcaption><span class="v-scroll-note">On a small screen, scroll the figure horizontally. </span>')
    return f'''<!doctype html><html lang="en">{head(title,route)}<body class="v-page"><a class="skip-link" href="#main">Skip to content</a><header class="v-header"><a class="brand" href="index.html">Rebalance <strong>Lab</strong></a><nav aria-label="Primary navigation"><a href="pilot.html">ETF validation</a><a href="methods.html">Methods &amp; evidence</a><a href="stocks.html">Stock companion</a><a href="{REPO}">Repository</a></nav></header><main id="main" class="v-main">{body}</main><footer class="v-footer"><span>Rebalance Lab · Research version 1 · 9 October 2026</span><span>Retrospective evidence · No trading recommendation</span></footer>{script}</body></html>'''


def website(s):
    runs={r["run_id"]:r for r in s["runs"]};ids=s["primary_ids"]
    m,a,t=[runs[ids[k]] for k in ("monthly","semiannual","tranched")]
    buttons='<div class="v-actions"><a class="button button-dark" href="assets/rebalance-lab-validation-brief.pdf">Read the four-page brief</a><a class="button" href="pilot.html">Inspect the ETF study</a></div>'
    finding='<p class="v-finding">The monthly–semiannual comparison changes sign when the semiannual calendar changes.</p><p class="v-intro">At 5 bps per side, the 12–1 CAGR difference ranges from <strong>−0.92 to +0.53 percentage points per year</strong> across six schedules. The designated March/September comparison is −0.49.</p>'
    checklist='<ol class="v-checklist"><li>Rules fixed before extension runs; prior history exposure disclosed.</li><li>Closing signals, next-session opening execution.</li><li>Four costs modeled in separate self-financing accounts.</li><li>Six calendars reported without selecting a winner.</li><li>Second implementations reconcile accounts and statistics.</li></ol>'
    limitations='Retrospective vendor-adjusted price and next-open proxies; fixed costs, zero-interest cash and changing ETF sectors. The same agent authored the separate implementations. Source prices and achievable fills remain unverified, and personal mastery requires actual owner review.'
    overview=f'''<section class="v-hero"><p class="eyebrow">Financial strategy validation · nine sector ETFs · 2001–2025</p><h1>A Validation Study of<br><em>Momentum Rebalancing</em></h1><p class="v-subtitle">{SUBTITLE}</p>{finding}{buttons}</section>
<figure class="v-figure"><img src="assets/validation-calendar-costs.svg" alt="Complete two-signal grid of six calendars and four costs; differences change sign."><figcaption>Monthly minus semiannual CAGR, pp/year. Positive favors monthly. The outlined March/September row remains the reference; all scenarios are reported.</figcaption></figure>
<section class="v-section"><p class="eyebrow">Claim → evidence → checks → judgment</p><h2>What this case demonstrates</h2>{checklist}</section>
<section class="v-section v-callout"><h2>Test the calendar-diversified alternative</h2><p>The six-sleeve tranche returns <strong>{pct(t['metrics']['full_period']['cagr'])} CAGR</strong>, versus {pct(m['metrics']['full_period']['cagr'])} monthly. Its maximum drawdown is deeper, at <strong>{pct(t['metrics']['full_period']['max_drawdown'])}</strong>. Both primary paired 95% intervals cross zero.</p><p class="v-judgment">The evidence supports sensitivity to the chosen calendar. It does not establish a general frequency ranking or a risk-free mitigation.</p><a href="pilot.html#uncertainty">Inspect estimates and uncertainty →</a></section>
<section class="v-section"><h2>Choose a reading depth</h2><div class="v-paths"><article><span>30 seconds</span><h3>The principal finding</h3><p>Calendar choice changes the sign of the comparison.</p><a href="assets/rebalance-lab-validation-brief.pdf">Validation brief →</a></article><article><span>2 minutes</span><h3>The full comparison</h3><p>Tranche paths, risk, costs and paired intervals.</p><a href="pilot.html">Study results →</a></article><article><span>5 minutes</span><h3>The evidence boundary</h3><p>Lineage, independent calculations and residual risk.</p><a href="methods.html">Methods &amp; memo →</a></article></div></section>
<section class="v-section"><h2>From accounting controls to model evaluation</h2><p>Accounting and Logistics Management training, followed by Business Analytics and AI study, provides the context for this project: careful measurement definitions, account reconciliation and evidence-based judgments.</p><p>This project asks what remains of a strategy claim after checking its assumptions, implementation and uncertainty. The same approach can be applied to model evaluations: define the claim, inspect the evidence, test failure modes and qualify the judgment.</p><p class="v-principle">“I test whether models and strategies actually work — and publish when they don’t.”</p><p class="v-note">The owner selected the validation focus, personally reconciled one trade and reviewed results and evidence limits in writing. AI assisted implementation and drafting. Exact signal-window explanation and observed oral presentation remain pending.</p></section>
<section class="v-section v-small"><h2>Companion and research history</h2><p><a href="stocks.html">The fixed-cohort stock pilot</a> is a separate case with a shorter window and different data assumptions. The original 75-stock design is archived as incomplete research history after its stricter data requirements could not be met.</p></section><section class="v-section v-small"><h2>Limitations</h2><p>{limitations}</p></section>'''
    write("site/index.html",shell("A Validation Study of Momentum Rebalancing","",overview))
    def table_row(label,r):
        q=r['metrics']['full_period'];v=r['monthly_risk']
        return f"<tr><th scope='row'>{label}</th><td>{pct(q['cagr'])}</td><td>{pct(q['max_drawdown'])}</td><td>{v['sharpe_monthly_annualized']:.3f}</td><td>{pct(v['tracking_error_monthly_annualized'])}</td><td>{v['beta_to_SPY_excess_returns']:.3f}</td><td>{q['annualized_two_sided_turnover']:.2f}×</td></tr>"
    risk=''.join(table_row(label,runs[ids[key]]) for label,key in [("Monthly","monthly"),("March / September","semiannual"),("Six-sleeve tranche","tranched"),("SPY context","benchmark")])
    ci=''.join(f"<tr><th scope='row'>{label}</th><td>{r['cagr_difference_pp']:+.2f}</td><td>[{r['ci95_difference_pp'][0]:+.2f}, {r['ci95_difference_pp'][1]:+.2f}]</td></tr>" for label,r in zip(["Monthly − March/September","Monthly − tranche"],[x for x in s['primary_intervals'] if x['primary_block']]))
    controls='''<div class="v-controls"><label>Signal <select id="validation-signal" disabled><option value="12-1">12–1 · primary</option><option value="mixed">Blended · robustness</option></select></label><label>Cost per side <select id="validation-cost" disabled><option value="0">0 bps</option><option value="5" selected>5 bps</option><option value="10">10 bps</option><option value="25">25 bps</option></select></label></div><div class="v-table" tabindex="0" role="region" aria-label="Calendar and tranche explorer"><table><caption id="validation-caption">Interactive saved comparisons</caption><thead><tr><th>Comparator</th><th>Comparator CAGR</th><th>Monthly − comparator</th><th>Comparator max DD</th></tr></thead><tbody id="validation-rows"><tr><td colspan="4">Loading validated results…</td></tr></tbody></table></div><p id="validation-data-status" role="status">Controls remain disabled until the complete saved result is checked.</p>'''
    study=f'''<section class="v-hero"><p class="eyebrow">ETF validation study · retrospective · 2001–2025</p><h1>Calendar Sensitivity<br><em>and Paired Uncertainty</em></h1>{finding}<div class="v-actions"><a class="button button-dark" href="assets/rebalance-lab-validation-brief.pdf">Download brief</a><a class="button" href="methods.html#memo">Validation memo</a></div></section>
<section class="v-section" id="calendars"><h2>Report every calendar and cost</h2><figure class="v-figure"><img src="assets/validation-calendar-costs.svg" alt="All 48 phase, cost and signal comparisons"><figcaption>Positive favors monthly; * March/September is the reference. Shared controls and overlapping histories do not constitute independent replications.</figcaption></figure>{controls}<noscript><p>JavaScript is disabled. The figures and primary tables below remain available; download the complete JSON/CSV for all scenarios.</p></noscript></section>
<section class="v-section" id="tranche"><h2>Pool six calendars without re-equalizing their capital</h2><p>Each semiannual sleeve receives one-sixth of initial capital. First trades occur on 3 January 2000. The sleeves then run autonomously: their capital drifts, no transfer occurs at the reporting anchor, and their trades are not netted against each other.</p><div class="v-timeline"><span>Equal initial cash</span><span>Six separate schedules</span><span>Sum net NAV and fees</span><span>Normalize pooled year-end NAV</span></div><figure class="v-figure"><img src="assets/validation-wealth-drawdown.svg" alt="Daily wealth and drawdown for monthly, March September, tranche and SPY"><figcaption>Each displayed path normalized at the 2000 closing anchor; 2001–2025, 5 bps. The tranche is deeper in maximum drawdown than both primary alternatives. SPY is exposure context.</figcaption></figure></section>
<section class="v-section"><h2>Returns, risk and activity</h2><div class="v-table" tabindex="0" role="region" aria-label="Primary portfolio risk metrics"><table><caption>12–1 signal · 5 bps per side · 2001–2025</caption><thead><tr><th>Portfolio</th><th>CAGR</th><th>Daily max DD</th><th>Sharpe</th><th>Tracking error</th><th>SPY beta</th><th>Traded NAV/year</th></tr></thead><tbody>{risk}</tbody></table></div><p class="v-note">Sharpe, tracking error and beta use 300 monthly simple returns and captured monthly RF. Tracking error and beta reference SPY. Drawdown uses daily closes. Trading counts buys plus sells. Cash earns zero.</p></section>
<section class="v-section" id="uncertainty"><h2>Show uncertainty beside the estimate</h2><div class="v-table" tabindex="0" role="region" aria-label="Paired CAGR confidence intervals"><table><caption>CAGR differences in percentage points per year</caption><thead><tr><th>Comparison</th><th>Estimate</th><th>Paired 95% interval</th></tr></thead><tbody>{ci}</tbody></table></div><figure class="v-figure"><img src="assets/validation-intervals.svg" alt="Both paired CAGR difference confidence intervals cross zero"><figcaption>10,000 paired stationary bootstrap draws of 300 net monthly returns; primary mean block length 12 months. Zero lies inside both intervals. This does not prove equivalence.</figcaption></figure><p>Six- and 24-month block sensitivity also crosses zero. The method samples realized portfolio returns, not asset-price histories or new selection decisions. Prior design choices and nonstationarity remain relevant.</p></section>
<section class="v-section"><h2>Costs remain part of the comparison</h2><figure class="v-figure"><img src="assets/validation-costs.svg" alt="Monthly minus fixed semiannual and tranche CAGR at four costs for both signals"><figcaption>Discrete modeled cost scenarios, each using its own net account paths. No interpolated break-even cost or executable fee forecast is inferred.</figcaption></figure></section>
<section class="v-section"><details><summary>A/B/C mechanism appendix</summary><p>A refreshes names and weights semiannually; B freezes names and cash slots but resets monthly; C refreshes both monthly. Primary CAGR: A {pct(a['metrics']['full_period']['cagr'])}, B {pct(runs[ids['weight_reset']]['metrics']['full_period']['cagr'])}, C {pct(m['metrics']['full_period']['cagr'])}. The sequential differences describe conditional comparisons and do not uniquely attribute performance to causes. Exact HAC and bootstrap units are retained in the saved summary.</p><a href="data/validation-study-summary.json">Inspect appendix calculations</a></details><details><summary>2026 partial-year case</summary><p>Through 2 October 2026: monthly {pct(m['metrics']['ytd2026']['total_return'])}, March/September {pct(a['metrics']['ytd2026']['total_return'])}, tranche {pct(t['metrics']['ytd2026']['total_return'])}. Continuous accounts; not annualized; excluded from primary inference.</p></details></section>
<section class="v-section v-callout"><h2>Validation judgment</h2><p>Accept the calculation as reconciled historical evidence. The sign of the frequency comparison is sensitive to the semiannual calendar, and the primary uncertainty intervals do not establish a general ranking. Tranching is a tested calendar-diversification construction with a disclosed drawdown tradeoff.</p><p>{limitations}</p><a href="methods.html">Inspect lineage, checks and design decisions →</a></section>
<section class="v-section"><h2>Download inspectable evidence</h2><div class="v-downloads"><a href="data/validation-study-summary.json">Validated result JSON</a><a href="data/validation-monthly-returns.csv">Monthly returns and RF</a><a href="data/validation-risk-metrics.csv">Risk metrics CSV</a><a href="data/validation-study-replay.json">Extension receipt</a><a href="downloads/validation-study.ipynb">Executed notebook</a><a href="notebook.html">Read notebook HTML</a><a href="assets/rebalance-lab-validation-memo.pdf">One-page memo</a></div></section>'''
    write("site/pilot.html",shell("Calendar Sensitivity and Paired Uncertainty","pilot.html",study,'<script src="validation.js" defer></script>'))
    import mistune
    md=mistune.create_markdown(plugins=["table"])
    sections=[]
    for anchor,name in [("memo","docs/validation/validation-memo.md"),("protocol","docs/methods/validation-study.md"),("decisions","docs/methods/design-decisions.md"),("reproduce","docs/reproduction.md")]:
        raw=(ROOT/name).read_text(encoding="utf-8")
        # Turn repository-relative links into their future GitHub destinations.
        import re
        def rewrite(match):
            value=match.group(1)
            if "://" in value or value.startswith("#"):return match.group(0)
            target=(ROOT/name).parent/value.split("#")[0]
            fragment="#"+value.split("#",1)[1] if "#" in value else ""
            return "]("+REPO+"/blob/main/"+target.resolve().relative_to(ROOT).as_posix()+fragment+")"
        raw=re.sub(r"\]\(([^)]+)\)",rewrite,raw)
        rendered=md(raw)
        rendered=re.sub(r'<(/?)h([1-5])>',lambda match:f'<{match[1]}h{int(match[2])+1}>',rendered)
        sections.append(f'<section class="v-section v-method" id="{anchor}">{rendered}</section>')
    intro='<section class="v-hero"><p class="eyebrow">Five-minute evidence path</p><h1>Methods, Checks<br><em>and Remaining Risk</em></h1><p class="v-intro">A separate implementation can test arithmetic on the same inputs. Its authorship, specification and source-data boundaries remain part of the judgment.</p><div class="v-actions"><a href="#memo">Validation memo</a><a href="#protocol">Method protocol</a><a href="#decisions">Design decisions</a><a href="#reproduce">Reproduce</a></div></section>'
    write("site/methods.html",shell("Methods, Checks and Remaining Risk","methods.html",intro+"".join(sections)))


if __name__=="__main__":
    import sys
    sys.path.insert(0,str(ROOT))
    from scripts.validate_validation_artifacts import check
    s=check();documents(s);website(s)
    print("Authored six core reading materials and three local site pages.")
