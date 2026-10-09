import calendar
import copy
import json
import math
from pathlib import Path
import unittest

try:
    import numpy as np
    from pilot.validation_study import aggregate_sleeves, monthly_path, risk_metrics, paired_cagr_intervals
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def fixture():
    dates = ["1999-12-31", "2000-01-03", "2000-12-29"]
    dates += [f"{y}-{m:02d}-{calendar.monthrange(y,m)[1]:02d}" for y in range(2001,2026) for m in range(1,13)]
    dates += ["2026-10-02"]
    prices = [100 * (1.005 ** i) for i in range(len(dates))]
    data = {"sessions":dates,"adjusted_open":{"A":prices}}
    sleeves = []
    for j in range(6):
        weight = 1-j*.12
        nav = 1000.0
        gross = nav * weight / (1 + weight*.0005)
        fee = gross*.0005
        quantity = gross/prices[1]
        cash = nav-gross-fee
        daily = [{"session":dates[0],"nav":1000.,"cash":1000.,"positions":{}}]
        daily += [{"session":d,"nav":cash+quantity*p,"cash":cash,"positions":{"A":quantity}} for d,p in zip(dates[1:],prices[1:])]
        sleeves.append({"run_id":f"S{j}","signal":"12-1","cost_bps_per_side":5,"daily":daily,
                        "trades":[{"session":dates[1],"pretrade_nav":1000.,"traded_notional":gross,"cost":fee}]})
    cfg={"report_anchor":"2000-12-29","primary_end":"2025-12-31","secondary_end":"2026-10-02"}
    return sleeves,data,cfg


@unittest.skipUnless(AVAILABLE,"analysis dependencies required")
class ValidationStudyTests(unittest.TestCase):
    def test_capital_sum_without_anchor_reset(self):
        sleeves,data,cfg=fixture()
        result=aggregate_sleeves(sleeves,data,cfg,"T")
        for j,day in enumerate(result["daily"]):
            self.assertAlmostEqual(day["nav"],sum(s["daily"][j]["nav"] for s in sleeves)/6)
            self.assertAlmostEqual(day["cash"],sum(s["daily"][j]["cash"] for s in sleeves)/6)
        self.assertFalse(any(t["session"]==cfg["report_anchor"] for t in result["trades"]))
        self.assertAlmostEqual(result["trades"][0]["cost"],sum(s["trades"][0]["cost"] for s in sleeves)/6)
        self.assertAlmostEqual(result["trades"][0]["turnover"],sum(s["trades"][0]["traded_notional"] for s in sleeves)/6000)
        expected=result["daily"][-2]["nav"]/result["daily"][2]["nav"]-1
        self.assertAlmostEqual(expected,result["metrics"]["full_period"]["total_return"])

    def test_identical_sleeves_restore_path(self):
        sleeves,data,cfg=fixture();same=[copy.deepcopy(sleeves[0]) for _ in range(6)]
        result=aggregate_sleeves(same,data,cfg,"T")
        for a,b in zip(result["daily"],same[0]["daily"]): self.assertAlmostEqual(a["nav"],b["nav"])

    def test_bad_dates_and_fees_fail(self):
        sleeves,data,cfg=fixture();broken=copy.deepcopy(sleeves);broken[2]["daily"][3]["session"]="2001-02-01"
        with self.assertRaises(ValueError): aggregate_sleeves(broken,data,cfg,"T")
        sleeves[0]["trades"][0]["cost"]+=1
        with self.assertRaises(ValueError): aggregate_sleeves(sleeves,data,cfg,"T")

    def test_monthly_missing_month_fails(self):
        sleeves,data,cfg=fixture();r=aggregate_sleeves(sleeves,data,cfg,"T")
        rows=monthly_path(r,cfg["report_anchor"],cfg["primary_end"])
        self.assertEqual(len(rows),300)
        self.assertAlmostEqual(rows[-1]["normalized_nav"],math.prod(1+x["simple_return"] for x in rows))
        r["daily"].pop(30)
        with self.assertRaises(ValueError): monthly_path(r,cfg["report_anchor"],cfg["primary_end"])

    def test_hand_risk_and_CAGR(self):
        market=np.array([.02,-.03,.04,.01]);rf=np.full(4,.001)
        values=rf+.002+1.5*(market-rf)
        out=risk_metrics(values,market,rf)
        mean=sum(values-rf)/4
        sd=math.sqrt(sum((v-mean)**2 for v in values-rf)/3)
        self.assertAlmostEqual(out["sharpe_monthly_annualized"],math.sqrt(12)*mean/sd)
        self.assertAlmostEqual(out["beta_to_SPY_excess_returns"],1.5)
        self.assertAlmostEqual(out["beta_intercept_per_month"],.002)
        active=values-market;active_mean=sum(active)/4
        self.assertAlmostEqual(out["tracking_error_monthly_annualized"],math.sqrt(12*sum((v-active_mean)**2 for v in active)/3))

    def test_identical_paired_intervals_and_seed(self):
        series=np.linspace(-.05,.07,300);values=np.column_stack([series,series])
        spec={"mean_block_months":12,"sensitivity_block_months":[6,24],"repetitions":100,"seed":20261009}
        first=paired_cagr_intervals(values,["M","T"],[("M-T","M","T")],spec)
        self.assertEqual(first,paired_cagr_intervals(values,["M","T"],[("M-T","M","T")],spec))
        for row in first:
            self.assertEqual(row["ci95_difference_pp"],[0.,0.]);self.assertEqual(row["cagr_difference_pp"],0.)


if __name__=="__main__": unittest.main()
