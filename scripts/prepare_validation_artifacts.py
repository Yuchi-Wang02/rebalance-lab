#!/usr/bin/env python3
"""Prepare local public aggregates; this command does not publish remotely."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")


def prepare(extension,receipt):
    s=json.loads((extension/"summary.json").read_text());v=json.loads(receipt.read_text())
    if not v["passed"] or v["summary_sha256"]!=sha(extension/"summary.json"):
        raise ValueError("extension is not independently reconciled")
    target=ROOT/"site/data";target.mkdir(exist_ok=True)
    names={"monthly-returns.csv":"validation-monthly-returns.csv","primary-daily-nav.csv":"validation-daily-nav.csv"}
    for original,public in names.items(): shutil.copyfile(extension/original,target/public)
    public=s.copy();public["status"]="computed_and_separately_reconciled"
    public["validation"]={k:v[k] for k in ("passed","imports_project_calculation_code","account_count","tranche_daily_states_checked","monthly_rows_checked","max_relative_tranche_NAV_error","verifier_code_sha256","checks","limitations")}
    public["derived_inputs"]={name:{"sha256":sha(target/name),"bytes":(target/name).stat().st_size} for name in names.values()}
    public["private_extension_summary_sha256"]=sha(extension/"summary.json")
    public["public_preparation_code_sha256"]=sha(__file__)
    save(target/"validation-study-summary.json",public)
    save(target/"validation-study-replay.json",{**v,"private_extension_summary_sha256":v["summary_sha256"],"public_summary_sha256":sha(target/"validation-study-summary.json")})
    with (target/"validation-risk-metrics.csv").open("w",encoding="utf-8",newline="") as f:
        keys=["run_id","signal","cost_bps_per_side","cagr","max_drawdown","annualized_two_sided_turnover","sharpe_monthly_annualized","tracking_error_monthly_annualized","beta_to_SPY_excess_returns"]
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for r in public["runs"]:
            writer.writerow({"run_id":r["run_id"],"signal":r.get("signal","benchmark"),"cost_bps_per_side":r["cost_bps_per_side"],
                             **{k:r["metrics"]["full_period"][k] for k in keys[3:6]},**{k:r["monthly_risk"][k] for k in keys[6:]}})
    print("Prepared validated aggregates locally; no commit, push or deployment performed.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--extension-dir",required=True,type=Path);p.add_argument("--receipt",required=True,type=Path)
    a=p.parse_args();prepare(a.extension_dir,a.receipt)
