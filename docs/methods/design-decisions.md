# Design decisions and questions for the owner

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
