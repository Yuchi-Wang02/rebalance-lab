#!/usr/bin/env python3
"""Separate tranche and statistical reconciliation; no project calculation imports."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timezone

import numpy as np


def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def zipped(path): return json.loads(gzip.decompress(Path(path).read_bytes()))
def require(condition, message):
    if not condition: raise ValueError(message)
def near(a,b, label, tolerance=3e-10):
    require(math.isclose(a,b,rel_tol=tolerance,abs_tol=tolerance),label)


def verify(source_dir, extension_dir, factor_dir, output):
    summary=load(extension_dir/"summary.json"); cfg=summary["protocol"]
    root=Path(__file__).resolve().parents[1]
    require(sha(root/"configs/sector-etf-validation.v1.json")==summary["source_hashes"]["protocol_sha256"],"protocol changed")
    for name,digest in summary["code_sha256"].items(): require(sha(root/name)==digest,f"extension code changed: {name}")
    manifest=load(extension_dir/"manifest.json")
    for name,record in manifest["files"].items(): require(sha(extension_dir/name)==record["sha256"],f"extension artifact changed: {name}")
    require(sha(source_dir/"manifest.json")==summary["source_hashes"]["run_manifest_sha256"],"source manifest differs")
    source_manifest=load(source_dir/"manifest.json")
    for name,digest in source_manifest["file_sha256"].items(): require(sha(source_dir/name)==digest,f"source artifact changed: {name}")
    for name,digest in source_manifest["code_sha256"].items(): require(sha(root/name)==digest,f"source engine code differs: {name}")
    require(sha(factor_dir/"factors-2001-2025.csv")==summary["source_hashes"]["factor_normalized_sha256"],"RF capture differs")
    with (factor_dir/"factors-2001-2025.csv").open(newline="",encoding="utf-8") as f: rf_rows=list(csv.DictReader(f))
    expected=[f"{y}-{m:02d}" for y in range(2001,2026) for m in range(1,13)]
    require([r["month"] for r in rf_rows]==expected,"RF month order differs")
    rf=np.array([float(r["RF"]) for r in rf_rows])
    accounts={p.name[:-8]:zipped(p) for p in source_dir.glob("*.json.gz") if p.name!="input-data.json.gz"}
    data=zipped(source_dir/"input-data.json.gz"); index={d:j for j,d in enumerate(data["sessions"])}
    composite_rows=0;max_nav_error=0.
    for prefix in ("12","MIX"):
        for cost in (0,5,10,25):
            identity=f"T{prefix}-{cost}bps"; composite=zipped(extension_dir/(identity+".json.gz"))
            sleeves=[accounts[f"S{prefix}-{m:02d}-{m+6:02d}-{cost}bps"] for m in range(1,7)]
            require(all(s["daily"][0]["session"]=="1999-12-31" and s["daily"][0]["nav"]==1000000 for s in sleeves),"formation differs")
            event_maps=[{t["session"]:t for t in s["trades"]} for s in sleeves]
            actual_trades={t["session"]:t for t in composite["trades"]}
            for j,row in enumerate(composite["daily"]):
                require(all(s["daily"][j]["session"]==row["session"] for s in sleeves),"tranche date mismatch")
                target=sum(s["daily"][j]["nav"]/6 for s in sleeves)
                max_nav_error=max(max_nav_error,abs(row["nav"]/target-1));near(row["nav"],target,"tranche NAV")
                near(row["cash"],sum(s["daily"][j]["cash"]/6 for s in sleeves),"tranche cash")
                symbols=set().union(*(s["daily"][j]["positions"] for s in sleeves))
                require(set(row["positions"])==symbols,"tranche symbol set")
                for symbol in symbols: near(row["positions"][symbol],sum(s["daily"][j]["positions"].get(symbol,0)/6 for s in sleeves),"tranche units")
                events=[e[row["session"]] for e in event_maps if row["session"] in e]
                require((row["session"] in actual_trades)==bool(events),"tranche event timing")
                if events:
                    t=actual_trades[row["session"]];k=index[row["session"]]
                    pre=sum((s["daily"][j-1]["cash"]+sum(q*data["adjusted_open"][symbol][k] for symbol,q in s["daily"][j-1]["positions"].items()))/6 for s in sleeves)
                    gross=sum(e["traded_notional"]/6 for e in events);fee=sum(e["cost"]/6 for e in events)
                    near(t["pretrade_nav"],pre,"pretrade pooled NAV");near(t["traded_notional"],gross,"gross notional; no netting")
                    near(t["cost"],fee,"pooled fees");near(fee,cost*gross/10000,"fee rate")
                    near(t["turnover"],gross/pre,"pooled turnover")
                composite_rows+=1
            require(cfg["report_anchor"] not in actual_trades,"artificial anchor trade")
            accounts[identity]=composite
    with (extension_dir/"monthly-returns.csv").open(newline="",encoding="utf-8") as f: monthly_csv=list(csv.DictReader(f))
    parsed={identity:[] for identity in accounts}
    for row in monthly_csv:
        require(row["run_id"] in parsed,"unknown monthly account");parsed[row["run_id"]].append(row)
    metadata={r["run_id"]:r for r in summary["runs"]};monthly={}
    for identity,account in accounts.items():
        rows=parsed[identity];require([r["month"] for r in rows]==expected,"missing, duplicate or shifted monthly return")
        days=[d for d in account["daily"] if cfg["report_anchor"]<=d["session"]<=cfg["primary_end"]]
        require(days[0]["session"]==cfg["report_anchor"] and days[-1]["session"]==cfg["primary_end"],"report boundaries")
        bymonth={d["session"][:7]:d for d in days[1:]};prev=days[0]["nav"];returns=[]
        peak=prev;dd=0.
        for day in days: peak=max(peak,day["nav"]);dd=min(dd,day["nav"]/peak-1)
        metrics=metadata[identity]["metrics"]["full_period"]
        near(metrics["cagr"],(days[-1]["nav"]/prev)**(1/25)-1,"CAGR")
        near(metrics["max_drawdown"],dd,"daily drawdown")
        for j,row in enumerate(rows):
            day=bymonth[row["month"]];value=day["nav"]/prev-1
            near(float(row["simple_return"]),value,"monthly return");near(float(row["RF"]),rf[j],"RF join")
            require(row["session"]==day["session"],"monthly endpoint")
            returns.append(value);prev=day["nav"]
        monthly[identity]=np.array(returns)
    for identity,values in monthly.items():
        market=monthly[f"SPY-{int(metadata[identity]['cost_bps_per_side'])}bps"]
        excess=values-rf;mx=market-rf;n=len(values)
        mean=float(sum(excess)/n);sd=math.sqrt(sum((v-mean)**2 for v in excess)/(n-1))
        active=values-market;active_mean=float(sum(active)/n)
        te=math.sqrt(12*sum((v-active_mean)**2 for v in active)/(n-1))
        xmean=float(sum(mx)/n);beta=float(sum((x-xmean)*(y-mean) for x,y in zip(mx,excess))/sum((x-xmean)**2 for x in mx))
        risk=metadata[identity]["monthly_risk"]
        near(risk["sharpe_monthly_annualized"],math.sqrt(12)*mean/sd,"monthly Sharpe")
        near(risk["tracking_error_monthly_annualized"],te,"tracking error")
        near(risk["beta_to_SPY_excess_returns"],beta,"SPY beta")
    labels=[summary["primary_ids"][k] for k in ("monthly","semiannual","tranched","weight_reset","benchmark")]
    logs=np.log1p(np.column_stack([monthly[i] for i in labels]));spec=cfg["bootstrap"]
    for length in (12,6,24):
        rng=np.random.default_rng(np.random.SeedSequence([spec["seed"],length]));n=spec["repetitions"]
        chosen=np.zeros((n,300),dtype=np.int32);chosen[:,0]=rng.integers(0,300,n)
        for month in range(1,300):
            restart=rng.random(n)<1/length;new=rng.integers(0,300,n)
            chosen[:,month]=np.where(restart,new,(chosen[:,month-1]+1)%300)
        sampled=np.expm1(logs[chosen].sum(axis=1)*12/300)
        for row in summary["primary_intervals"]:
            if row["mean_block_months"]!=length: continue
            hi,lo=[labels.index(row[k]) for k in ("high_run_id","low_run_id")]
            interval=np.quantile(100*(sampled[:,hi]-sampled[:,lo]),[.025,.975])
            for a,b in zip(row["ci95_difference_pp"],interval): near(a,float(b),"bootstrap percentile")
    with (extension_dir/"primary-daily-nav.csv").open(newline="",encoding="utf-8") as f: public=list(csv.DictReader(f))
    for identity in labels:
        days={d["session"]:d["nav"] for d in accounts[identity]["daily"]}
        for row in public: near(float(row[identity]),days[row["session"]]/days[cfg["report_anchor"]],"exported normalized NAV")
    result={"schema_version":1,"passed":True,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "imports_project_calculation_code":False,"account_count":116,"derived_tranche_count":8,
            "tranche_daily_states_checked":composite_rows,"monthly_rows_checked":len(monthly_csv),
            "max_relative_tranche_NAV_error":max_nav_error,"extension_manifest_sha256":sha(extension_dir/"manifest.json"),
            "summary_sha256":sha(extension_dir/"summary.json"),"verifier_code_sha256":sha(__file__),
            "checks":{"capital_aggregation":True,"cash_and_units":True,"gross_costs_without_netting":True,"monthly_returns":True,"risk_metrics":True,"paired_bootstrap_percentiles":True,"daily_export":True},
            "limitations":["Same agent authored both implementations; shared specification misunderstanding remains possible.","Same preserved vendor inputs; no independent market source or live execution certification.","Bootstrap is conditional on the observed history and return-resampling model; it does not remove retrospective design or nonstationarity risk."]}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source-dir",required=True,type=Path)
    p.add_argument("--extension-dir",required=True,type=Path);p.add_argument("--factor-dir",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args();print(json.dumps(verify(a.source_dir,a.extension_dir,a.factor_dir,a.output),indent=2))
