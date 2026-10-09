#!/usr/bin/env python3
"""Compute the frozen validation extension from preserved, verified accounts."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from pilot.validation_study import aggregate_sleeves, monthly_path, risk_metrics, paired_cagr_intervals
from pilot.mechanism_analysis import paired_inference, bootstrap_intervals


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def compressed(path): return json.loads(gzip.decompress(Path(path).read_bytes()))
def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")


def run(run_dir, factor_dir, validation, output_dir):
    protocol_path = ROOT/"configs/sector-etf-validation.v1.json"
    cfg = load(protocol_path)
    freeze = load(ROOT/"docs/validation/etf-validation-protocol-freeze.json")
    if freeze["protocol_sha256"] != sha(protocol_path): raise ValueError("protocol differs from freeze")
    manifest_path = run_dir/"manifest.json"
    if sha(manifest_path) != cfg["source_run_manifest_sha256"]: raise ValueError("source run differs")
    manifest = load(manifest_path)
    for name, record in manifest["file_sha256"].items():
        expected = record["sha256"] if isinstance(record, dict) else record
        if sha(run_dir/name) != expected: raise ValueError(f"source artifact changed: {name}")
    receipt = load(validation)
    if not receipt["passed"] or receipt["run_manifest_sha256"] != sha(manifest_path):
        raise ValueError("source independent replay is absent or stale")
    factor_manifest = load(factor_dir/"manifest.json")
    normalized = factor_dir/"factors-2001-2025.csv"
    # Acquisition manifest binds raw captures and the normalized RF series.
    for record in factor_manifest["captures"]:
        if sha(factor_dir/record["file"]) != record["sha256"]: raise ValueError("factor capture changed")
    if sha(normalized) != factor_manifest["normalized_sha256"]: raise ValueError("normalized factor capture changed")
    with normalized.open(encoding="utf-8", newline="") as f: factors = list(csv.DictReader(f))
    expected_months = [f"{y}-{m:02d}" for y in range(2001,2026) for m in range(1,13)]
    if [r["month"] for r in factors] != expected_months: raise ValueError("RF months do not align")
    rf = [float(r["RF"]) for r in factors]
    source = load(run_dir/"summary.json")
    accounts = {p.name[:-8]: compressed(p) for p in run_dir.glob("*.json.gz") if p.name != "input-data.json.gz"}
    if len(accounts) != 108: raise ValueError("source must contain all 108 accounts")
    data = compressed(run_dir/"input-data.json.gz")
    tranches = {}
    for signal, prefix in (("12-1","12"),("mixed","MIX")):
        for cost in cfg["cost_bps_per_side"]:
            ids = [f"S{prefix}-{a:02d}-{b:02d}-{cost}bps" for a,b in cfg["phase_pairs"]]
            identity = f"T{prefix}-{cost}bps"
            tranches[identity] = aggregate_sleeves([accounts[i] for i in ids], data, cfg, identity)
    accounts.update(tranches)
    monthly = {i:monthly_path(r,cfg["report_anchor"],cfg["primary_end"]) for i,r in accounts.items()}
    primary = {"monthly":"M12-5bps","semiannual":"S12-03-09-5bps","tranched":"T12-5bps",
               "weight_reset":"B12-03-09-5bps","benchmark":"SPY-5bps"}
    for identity, account in accounts.items():
        benchmark = f"SPY-{int(account['cost_bps_per_side'])}bps"
        account["monthly_risk"] = risk_metrics([r["simple_return"] for r in monthly[identity]],
                                              [r["simple_return"] for r in monthly[benchmark]],rf)
        growth = monthly[identity][-1]["normalized_nav"]-1
        if not math.isclose(growth,account["metrics"]["full_period"]["total_return"],abs_tol=1e-10):
            raise ValueError("monthly and daily total return differ")
    labels = [primary[k] for k in ("monthly","semiannual","tranched","weight_reset","benchmark")]
    values = np.column_stack([[r["simple_return"] for r in monthly[i]] for i in labels])
    comparisons = [("monthly_minus_march_september",labels[0],labels[1]),("monthly_minus_tranched",labels[0],labels[2])]
    intervals = paired_cagr_intervals(values,labels,comparisons,cfg["bootstrap"])
    abc_values = values[:,[1,3,0]]
    mechanism_cfg = load(ROOT/"configs/sector-etf-mechanisms.v1.json")
    mechanism_inference = paired_inference(abc_values)
    mechanism_intervals = [r for n in [12,6,24] for r in bootstrap_intervals(abc_values,10000,n,20261009)]
    output_dir.mkdir(parents=True,exist_ok=False)
    for identity, account in tranches.items():
        (output_dir/(identity+".json.gz")).write_bytes(gzip.compress((json.dumps(account,allow_nan=False)+"\n").encode(),mtime=0))
    with (output_dir/"monthly-returns.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["month","session","run_id","policy","signal","cost_bps_per_side","simple_return","normalized_nav","RF"])
        writer.writeheader()
        for identity, account in sorted(accounts.items()):
            for j,row in enumerate(monthly[identity]):
                writer.writerow({**row,"run_id":identity,"policy":account.get("policy","SPY"),"signal":account.get("signal","benchmark"),
                                 "cost_bps_per_side":account["cost_bps_per_side"],"RF":rf[j]})
    rows_by_date = {i:{r["session"]:r for r in accounts[i]["daily"]} for i in labels}
    dates=[d for d in rows_by_date[labels[0]] if cfg["report_anchor"]<=d<=cfg["primary_end"]]
    with (output_dir/"primary-daily-nav.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f);writer.writerow(["session",*labels])
        for date in dates:
            writer.writerow([date,*[rows_by_date[i][date]["nav"]/rows_by_date[i][cfg["report_anchor"]]["nav"] for i in labels]])
    metadata = [{k:r[k] for k in ("run_id","policy","signal","phase","cost_bps_per_side","metrics","monthly_risk") if k in r} for r in accounts.values()]
    legacy_comparisons=[r for r in source["comparisons"]["full_period"] if r.get("contrast")=="C-A"]
    # Source comparison labels are verified here before publication.
    if len(legacy_comparisons)!=48: raise ValueError("48 monthly/semiannual comparisons required")
    source_hashes={"run_manifest_sha256":sha(manifest_path),"source_replay_sha256":sha(validation),
                   "input_data_gzip_sha256":sha(run_dir/"input-data.json.gz"),"factor_manifest_sha256":sha(factor_dir/"manifest.json"),
                   "factor_normalized_sha256":sha(normalized),"protocol_sha256":sha(protocol_path),"freeze_sha256":sha(ROOT/"docs/validation/etf-validation-protocol-freeze.json")}
    code_files=["scripts/run_validation_study.py","pilot/validation_study.py","pilot/mechanism_analysis.py"]
    result={"schema_version":1,"experiment_id":cfg["experiment_id"],"run_id":output_dir.name,
            "generated_at_utc":datetime.now(timezone.utc).isoformat(),"protocol":cfg,"primary_ids":primary,
            "account_count":108,"derived_tranche_count":8,"months":300,"runs":metadata,
            "calendar_comparisons":legacy_comparisons,"primary_intervals":intervals,
            "mechanism_appendix":{"inference":mechanism_inference,"bootstrap":mechanism_intervals,"interpretation":"sequential conditional comparisons, not a unique causal decomposition"},
            "source_hashes":source_hashes,"code_sha256":{n:sha(ROOT/n) for n in code_files},
            "factor_source":factor_manifest,"source_replay":receipt,
            "checks":{"equal_initial_sleeve_capital":True,"no_anchor_reset":True,"monthly_daily_growth_reconciles":True,"exact_300_month_RF_join":True},
            "status":"computed_pending_extension_validation","owner_mastery_verified":False}
    save(output_dir/"summary.json",result)
    save(output_dir/"protocol.json",cfg)
    save(output_dir/"manifest.json",{"schema_version":1,"run_id":output_dir.name,"files":{p.name:{"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(output_dir.iterdir())},"code_sha256":result["code_sha256"]})
    return {"output":str(output_dir),"accounts":len(accounts),"tranches":8,"primary_intervals":intervals[:2]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",required=True,type=Path);parser.add_argument("--factor-dir",required=True,type=Path)
    parser.add_argument("--validation",required=True,type=Path);parser.add_argument("--output-dir",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.run_dir,args.factor_dir,args.validation,args.output_dir),indent=2))
