#!/usr/bin/env python3
"""Offline integrity and numerical checks for the public validation case."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,message):
    if not v: raise ValueError(message)
def near(a,b,message): require(math.isclose(a,b,rel_tol=3e-10,abs_tol=3e-10),message)


def check(root=ROOT):
    folder=root/"site/data";summary=folder/"validation-study-summary.json"
    s=json.loads(summary.read_text());v=json.loads((folder/"validation-study-replay.json").read_text())
    require(s["status"]=="computed_and_separately_reconciled" and v["passed"],"validation not passed")
    require(v["public_summary_sha256"]==sha(summary),"stale public summary")
    require(s["owner_mastery_verified"] is False,"owner mastery cannot be inferred")
    require(s["source_hashes"]["protocol_sha256"]==sha(root/"configs/sector-etf-validation.v1.json"),"protocol hash")
    freeze_path=root/"docs/validation/etf-validation-protocol-freeze.json"
    freeze=json.loads(freeze_path.read_text(encoding="utf-8"))
    require(s["source_hashes"]["freeze_sha256"]==sha(freeze_path) and freeze["protocol_sha256"]==s["source_hashes"]["protocol_sha256"],"freeze binding")
    require(freeze["source_history_already_inspected"] is True and freeze["prospective_registration"] is False,"retrospective disclosure")
    require(v["verifier_code_sha256"]==sha(root/"scripts/validate_validation_study_independent.py"),"verifier hash")
    require(s["public_preparation_code_sha256"]==sha(root/"scripts/prepare_validation_artifacts.py"),"preparation hash")
    for name,digest in s["code_sha256"].items(): require(sha(root/name)==digest,f"changed analysis code: {name}")
    for name,r in s["derived_inputs"].items(): require(sha(folder/name)==r["sha256"],f"changed derived input: {name}")
    accounts={r["run_id"]:r for r in s["runs"]};require(len(accounts)==116 and s["derived_tranche_count"]==8,"account count")
    expected=[f"{y}-{m:02d}" for y in range(2001,2026) for m in range(1,13)]
    with (folder/"validation-daily-nav.csv").open(encoding="utf-8",newline="") as f: daily=list(csv.DictReader(f))
    dates=[r["session"] for r in daily]
    require(dates==sorted(set(dates)) and dates[0]=="2000-12-29" and dates[-1]=="2025-12-31","daily reporting boundaries")
    month_ends={}
    for row in daily[1:]:month_ends[row["session"][:7]]=row["session"]
    require(list(month_ends)==expected,"daily reporting months")
    with (folder/"validation-monthly-returns.csv").open(encoding="utf-8",newline="") as f: raw=list(csv.DictReader(f))
    rows={i:[] for i in accounts}
    for r in raw:
        require(r["run_id"] in rows,"unknown monthly series");rows[r["run_id"]].append(r)
    for identity,data in rows.items():
        require([r["month"] for r in data]==expected,"missing, duplicate or shifted months")
        require([r["session"] for r in data]==list(month_ends.values()),"monthly session alignment")
        returns=[float(r["simple_return"]) for r in data];rf=[float(r["RF"]) for r in data]
        require(all(math.isfinite(x) and x>-1 for x in returns),"invalid return")
        require(all(math.isfinite(x) for x in rf),"invalid risk-free return")
        require(rf==[float(r["RF"]) for r in rows["SPY-5bps"]],"risk-free series alignment")
        growth=math.prod(1+x for x in returns)
        cumulative=1
        for row,monthly_return in zip(data,returns):
            cumulative*=1+monthly_return
            near(cumulative,float(row["normalized_nav"]),"intermediate monthly NAV compounding")
        near(growth,float(data[-1]["normalized_nav"]),"monthly NAV compounding")
        near(growth**(1/25)-1,accounts[identity]["metrics"]["full_period"]["cagr"],"reported CAGR")
        market=[float(r["simple_return"]) for r in rows[f"SPY-{int(accounts[identity]['cost_bps_per_side'])}bps"]]
        excess=[x-r for x,r in zip(returns,rf)];mx=[x-r for x,r in zip(market,rf)]
        risk=accounts[identity]["monthly_risk"]
        near(math.sqrt(12)*statistics.fmean(excess)/statistics.stdev(excess),risk["sharpe_monthly_annualized"],"reported Sharpe")
        near(math.sqrt(12)*statistics.stdev([a-b for a,b in zip(returns,market)]),risk["tracking_error_monthly_annualized"],"reported tracking error")
        exmean,mxmean=statistics.fmean(excess),statistics.fmean(mx)
        beta=sum((x-mxmean)*(y-exmean) for x,y in zip(mx,excess))/sum((x-mxmean)**2 for x in mx)
        near(beta,risk["beta_to_SPY_excess_returns"],"reported beta")
    for r in s["primary_intervals"]:
        near(100*(accounts[r["high_run_id"]]["metrics"]["full_period"]["cagr"]-accounts[r["low_run_id"]]["metrics"]["full_period"]["cagr"]),r["cagr_difference_pp"],"CI estimate binding")
        require(len(r["ci95_difference_pp"])==2 and r["ci95_difference_pp"][0]<=r["ci95_difference_pp"][1],"CI bounds")
        require(r["months"]==300 and r["repetitions"]==10000,"CI sample scope")
    cells=s["calendar_comparisons"]
    require(len(cells)==48,"all phase/cost/signal cells required")
    expected_cells={(signal,cost,phase) for signal in ("12-1","mixed") for cost in (0,5,10,25) for phase in range(1,7)}
    require({(r["signal"],r["cost_bps_per_side"],r["phase"][0]) for r in cells}==expected_cells,"complete unique calendar cells")
    for r in cells:
        near(r["cagr_difference_pp"],100*(accounts[r["high_run_id"]]["metrics"]["full_period"]["cagr"]-accounts[r["low_run_id"]]["metrics"]["full_period"]["cagr"]),"calendar estimate binding")
    with (folder/"validation-risk-metrics.csv").open(newline="",encoding="utf-8") as f: risk_rows=list(csv.DictReader(f))
    require(len(risk_rows)==116,"risk export count")
    require({r["run_id"] for r in risk_rows}==set(accounts),"risk export identities")
    for r in risk_rows:
        account=accounts[r["run_id"]]
        for k in ("cagr","max_drawdown","annualized_two_sided_turnover"):
            near(float(r[k]),account["metrics"]["full_period"][k],"risk CSV metric binding")
        for k in ("sharpe_monthly_annualized","tracking_error_monthly_annualized","beta_to_SPY_excess_returns"):
            near(float(r[k]),account["monthly_risk"][k],"risk CSV metric binding")
    for identity in daily[0]:
        if identity=="session":continue
        values=[float(r[identity]) for r in daily]
        require(all(math.isfinite(x) and x>0 for x in values),"invalid daily NAV")
        near(values[0],1,"daily anchor normalization")
        near(values[-1],float(rows[identity][-1]["normalized_nav"]),"daily/monthly final NAV")
        peak=values[0];drawdown=0
        for value in values:peak=max(peak,value);drawdown=min(drawdown,value/peak-1)
        near(drawdown,accounts[identity]["metrics"]["full_period"]["max_drawdown"],"daily maximum drawdown")
    print("PASS: validated public summary, 116 monthly paths, risk metrics, all phases and receipt hashes.")
    return s


if __name__=="__main__": check()
