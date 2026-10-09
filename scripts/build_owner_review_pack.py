#!/usr/bin/env python3
"""Prepare private owner exercises and conditional career drafts; record no answers."""
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output/private/owner-review"
SOURCE=ROOT/"results/generated/etf-mechanisms/20261009T050633543130Z-d96bbf03d531"


def write(name,text):
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/name
    if not path.exists():path.write_text(text.strip()+"\n",encoding="utf-8")


def build():
    account=json.loads(gzip.decompress((SOURCE/"M12-5bps.json.gz").read_bytes()))
    trade=next(t for t in account["trades"] if t["session"]=="2001-01-02")
    day_index=next(i for i,r in enumerate(account["daily"]) if r["session"]==trade["session"])
    cash_before=account["daily"][day_index-1]["cash"]
    cash_after=account["daily"][day_index]["cash"]
    order_table="| ETF | Signed executed notional, proxy USD |\n|---|---:|\n"+"\n".join(f"| {r['symbol']} | {r['notional']:+,.6f} |" for r in trade["orders"])
    write("01-owner-checkpoints.md",f'''# Rebalance Lab：三次本人复核

状态：**尚未完成；不等于人类科学验证。** 每次约 15-20 分钟。可以查方法和代码，但先用自己的话作答；不懂的地方直接标明。把你的回答和实际计算保存后，才更新掌握状态。

## 第一次：规则与账户

1. 画出 12-1 信号的两个价格端点。最近 21 个交易日从哪里排除？为什么同样涨幅的两个 ETF 会因波动率不同得到不同分数？
2. 只有两只 ETF 合格时，各占多少？现金多少？为什么这不等于等权满仓？
3. 手算下面一笔真实保存交易的 gross notional、费用、交易后 NAV、现金和 turnover。成本是每边 5 bps，交易前 opening NAV 为 **{trade['pretrade_nav']:,.6f}**，交易前现金为 **{cash_before:,.6f}**。信号日 **{trade['decision_session']}**；执行日 **{trade['session']}**。负数是卖出，正数是买入。订单金额已保留 6 位小数，现金允许小于 0.00001 的舍入差。

{order_table}

填写：gross notional = ____；fee = ____；post-fee NAV = ____；post-trade cash = ____；two-sided turnover = ____。
现金核对式：期初现金＋卖出金额－买入金额－费用＝____。

4. 调整价格 proxy unit 和真实 ETF 股份有何区别？为什么第二实现不能证明这笔成交真的可实现？

本人解释：____

实际完成的计算／证据：____

仍需学习或不同意的规则：____

## 第二次：结果与不确定性

1. 打开 calendar × cost 图，在同一信号和费用下指出两个相反符号的结果。哪些条件变了，哪些没变？
2. 月度在 13/25 个完整年度领先，为什么完整区间 CAGR 仍能落后？年度胜率能否代替收益差的检验？
3. 六个 sleeve 在初始化各 1/6，为什么 2001 年报告起点不一定还是各 1/6？为什么不能平均六个 CAGR？写出正确的 pooled NAV 与报告收益公式。
4. 用自己的话解释 -0.49 pp/year 和 [-3.03,+2.11]。区间跨零意味着什么、不意味着什么？为什么抽样要让两条策略保留同一批月份？

本人解释：____

重新运行／检查的文件和结果：____

仍需学习：____

## 第三次：判断与讲述

1. 用三句话分别写“证据支持”“证据不足”“下一项最有价值的检查”。不要把 calendar sensitivity 写成全部差异的因果解释。
2. 解释源数据哈希、第二实现、外部独立验证三者分别增加什么信心。
3. 说明你实际作出的决定、AI完成的实现、你亲自做过的核对，以及还没理解的部分。
4. 不看讲述稿，用 90 秒讲项目，并接受问题：为什么分批组合的回撤更深，你还要保留这个结果？

本人判断：____

实际讲述记录：____

最终贡献说明：____

通过标准：能明确解释和演示，允许有范围清楚的未知；不能用“测试通过”代替自己的回答。见独立文件 `02-reviewer-guide.md` 核对关键数学，但不要把参考答案复制成你的回答。
''')
    write("02-reviewer-guide.md",f'''# 复核参考与证据入口

只作核对参考，不代表本人已经回答或通过。

第一次真实交易：gross notional **{trade['traded_notional']:,.6f}**；fee **{trade['cost']:,.6f}**；post-fee NAV **{trade['posttrade_nav']:,.6f}**；turnover **{trade['turnover']:.9f}**，约 70.53%。费用＝gross × 0.0005。交易后 NAV＝交易前 NAV－费用。这里卖买均计费用。
交易后现金 **{cash_after:,.6f}**；按带符号订单核对为 cash_before − sum(signed orders) − fee。此交易以卖出筹资支付买入与费用，保留的小数会造成很小的舍入残差。

两个合格 ETF 各占 1/3，另 1/3 是现金。波动率调整是排名规则，组合本身没有波动率目标。close→next open 的时间顺序避免用尚未完成的 close 决定同一 close 的成交；adjusted open 仍是代理值。

第二次：月度和半年共享相同日期和资产，但半年更新月份不同。六种 phase 不独立。CAGR用期末／期初财富的几何增长，年度胜出数量忽略差异大小。T_NAV(t)=sum(NAV_sleeve(t))/6；报告期增长因子=T_NAV(end)/T_NAV(anchor)。不要改成 mean(NAV_end/NAV_anchor)。CI跨零不证明等价，也不证明频率差异不存在。

第三次：证据支持所观察到的日历敏感性；不支持普遍频率排名、唯一因果归因或分批风险消除。下一项检查可选择一个明确数据或执行风险，但不能替其他条件都发“通过”证书。第二实现是同一 agent 编写，仍可能共同误解规则。

技术证据：

- 方法：{(ROOT/'docs/methods/validation-study.md').as_posix()}
- 设计决定：{(ROOT/'docs/methods/design-decisions.md').as_posix()}
- Memo：{(ROOT/'docs/validation/validation-memo.md').as_posix()}
- Notebook：{(ROOT/'notebooks/validation-study.ipynb').as_posix()}
- 公共结果：{(ROOT/'site/data/validation-study-summary.json').as_posix()}
- 真实交易来源：{(SOURCE/'M12-5bps.json.gz').as_posix()}
''')
    write("03-project-and-career-drafts.md",'''# Project summary and conditional career drafts

**Status:** research artifacts are AI-assisted. The owner selected the audience, scope, principal story and review process. Technical explanation checkpoints remain pending. First-person technical claims below are drafts to be confirmed by actual owner review, not current certifications.

## One-page English project summary

**Rebalance Lab - A Validation Study of Momentum Rebalancing**

**Question.** Does more frequent momentum selection improve net performance, and how much does the conclusion depend on the chosen semiannual calendar?

**Design.** Nine sector ETFs, 2001-2025, two signals, six semiannual calendars and four modeled costs. Add six autonomous sleeves with equal formation capital, then preserve their drift, fees and reporting boundaries. Use 300 paired monthly returns for stationary bootstrap uncertainty and monthly risk measures.

**Finding.** At 5 bps, the primary CAGR difference ranges from -0.92 to +0.53 pp/year across calendars. The fixed March/September comparison is -0.49, with 95% CI [-3.03,+2.11]. The tranche returns 8.24% CAGR but has -40.91% maximum drawdown; monthly minus tranche is -0.22, CI [-2.44,+2.33].

**Validation.** Source and protocol manifests; next-session execution; fee-conserving accounts; full phase/cost disclosure; separate accounting and statistical implementations; failure-injection tests. Same-agent authorship and same input source are disclosed.

**Judgment.** Calendar-sensitive historical evidence, without an optimal-frequency claim. Neither zero-spanning intervals nor consistent code reproduction establishes equivalence, authentic source prices or executable fills.

**Owner role.** Selected the validation orientation and required bounded conclusions. AI assisted implementation and drafting. Actual owner calculations and interpretation are added only after the three checkpoints.

## CV draft - only after owner explanation checks

- Evaluated momentum rebalancing across nine sector ETFs over 2001-2025, reporting all six semiannual calendars and four costs; tested a six-sleeve comparison and paired bootstrap uncertainty rather than selecting a favorable schedule.
- Directed an AI-assisted validation workflow with preserved source manifests, separate accounting/statistical implementations and explicit residual-risk documentation; [insert only the actual checks personally completed].

Avoid: "built an independently validated strategy," "eliminated timing luck," "proved monthly rebalancing underperforms," or a personal engine-development claim unless actual contribution evidence supports it.

## 90-second narrative - review before using

My focus is whether a result remains credible after its assumptions and evaluation method are checked. Rebalance Lab applies that approach to a financial strategy claim: does more frequent momentum selection improve performance?

The study covers nine sector ETFs over 25 complete years. The important finding is that the sign of monthly versus semiannual performance changes when the semiannual calendar changes. I therefore kept every calendar and cost scenario instead of choosing the best one.

We also tested a portfolio split across all six calendars. It had 8.24% CAGR, but a deeper drawdown than the primary alternatives. The paired uncertainty intervals crossed zero. That meant the conclusion needed to stay bounded: sensitivity in this history, not a generally superior frequency or a guaranteed fix.

AI assisted the implementation. The workflow includes a second accounting implementation and a separate statistical check, with their shared authorship disclosed. My contribution is [state the actual design decisions and checks completed]. This is the approach I want to bring to model evaluation: define the claim, inspect the evidence, challenge the implementation and explain what remains uncertain.

## Three-minute expansion

Add four concrete examples to the short narrative: the 21-session skip and its endpoints; one fee-conserving next-open trade; why equal sleeve capital at formation is not equal capital at the reporting anchor; and why same-agent independent code still has a specification-risk boundary. End by naming the highest-value unresolved source or execution check, not by promising an adaptive strategy.

## Ten interview questions / Chinese explanation cues

1. **What claim did you test?** 明确策略、窗口、成本、comparison，避免说所有金融策略。
2. **Why 12-1 momentum?** 展示价格端点和skip，不把惯例包装成最优参数。
3. **Why volatility-scaled scores?** 排名与风险目标不同；分母也是估计量。
4. **Why next-open execution?** 信息可用时点和成交代理限制分别解释。
5. **What does tranching change?** 分散日历分配，不保证分散共同持仓风险。
6. **Why not average CAGRs?** 财富可加总，几何增长率不可直接加总。
7. **Why paired block bootstrap?** 保留策略间共同时期和部分时间依赖；假设仍有边界。
8. **What is the difference between DD, TE and beta?** DD是每日峰谷损失；TE是月度主动收益波动；beta是市场超额收益敏感度。
9. **How independent was your validation?** 不共享项目计算实现，不等于独立作者或独立数据。
10. **What did you personally do?** 只列实际决定、手算、复现和判断；清楚承认agent实现和未知部分。

## How this supports the broader positioning

This financial case shows a repeatable way of judging evidence. Accounting/control training can motivate careful definitions, reconciliation and exception handling, but it is not a claim of professional audit certification. Other project findings should be separately verified before entering a combined portfolio story.
''')
    status=OUT/"owner-review-status.json"
    if not status.exists():status.write_text(json.dumps({"schema_version":1,"owner_mastery_verified":False,"checkpoint_1":{"status":"pending","actual_answer":None},"checkpoint_2":{"status":"pending","actual_answer":None},"checkpoint_3":{"status":"pending","actual_answer":None}},indent=2)+"\n")
    print("Prepared three private checkpoint worksheets, reviewer guide and conditional career drafts; no owner answers recorded.")


if __name__=="__main__":build()
