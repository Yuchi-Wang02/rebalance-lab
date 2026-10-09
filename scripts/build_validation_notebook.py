#!/usr/bin/env python3
"""Create, execute and export a public-input validation companion notebook."""
import json
import os
import shutil
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter

ROOT=Path(__file__).resolve().parents[1]


def build():
    cells=[]
    def md(text):cells.append(nbf.v4.new_markdown_cell(text.strip()))
    def code(text):cells.append(nbf.v4.new_code_cell(text.strip()))
    md('''# Rebalance Lab: a validation companion

## Principal finding

Across six semiannual calendars, the 12-1 monthly-minus-semiannual CAGR difference changes sign. At 5 bps it ranges from -0.92 to +0.53 pp/year. The six-sleeve tranche has 8.24% CAGR and -40.91% daily maximum drawdown. The two primary paired 95% intervals cross zero.

This executed notebook recomputes statistics and editable figures from **public derived portfolio inputs**. It does not reconstruct portfolios from raw vendor prices or certify live execution. The owner has completed a trade reconciliation and written result/judgment review; exact signal-window explanation and observed oral presentation remain pending.
''')
    md('''## Context & Methods

Claim: more frequent momentum selection and reweighting improves net portfolio performance. Nine sector ETFs; 2001-2025; primary 12-1 signal; 5 bps per side; March/September reference. Other signals, calendars and costs are robustness scenarios.

### Key Assumptions

- Equal tranche capital at formation in 1999, followed by 2000 burn-in. No sleeve transfer or re-equalization at the reporting anchor.
- Net monthly simple returns, paired by calendar month. Bootstrap resamples returns, not price histories or fresh strategy decisions.
- Captured French monthly RF; zero-interest portfolio cash. Sharpe/TE use sample standard deviation, annualized with sqrt(12); beta includes an intercept.
- Retrospective extension, prior history inspected; no prospective-registration or untouched-holdout claim.

Clone the repository, install `requirements-research.txt` in a virtual environment, and run this notebook with that environment's kernel. No credentials, downloads or absolute machine paths are needed.
''')
    md('''### 1. Locate the repository and load analysis tools

The notebook uses project calculation helpers for reproduction, not as an independent check. The separately authored verifier and its receipt are linked below.''')
    code('''from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "site/data/validation-study-summary.json").exists())
sys.path.insert(0, str(ROOT))
from pilot.validation_study import risk_metrics, paired_cagr_intervals
from pilot.validation_figures import calendar_figure, wealth_figure, interval_figure, cost_figure
get_ipython().run_line_magic("matplotlib", "inline")
DATA = ROOT / "site/data"
summary = json.loads((DATA / "validation-study-summary.json").read_text(encoding="utf-8"))
''')
    md('''## Data

### 2. Verify identities and exact monthly alignment

Sources: public `validation-monthly-returns.csv`, `validation-daily-nav.csv`, result JSON and replay receipt. RF provenance records the official French archive URL, retrieval time and hashes. Derived strategy returns are not raw vendor observations.''')
    code('''receipt = json.loads((DATA / "validation-study-replay.json").read_text(encoding="utf-8"))
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert receipt["passed"] and receipt["public_summary_sha256"] == digest(DATA / "validation-study-summary.json")
for name, record in summary["derived_inputs"].items():
    assert digest(DATA / name) == record["sha256"], name
monthly = pd.read_csv(DATA / "validation-monthly-returns.csv")
expected = [f"{year}-{month:02d}" for year in range(2001, 2026) for month in range(1, 13)]
assert len(monthly) == 34800 and monthly.run_id.nunique() == 116
for identity, group in monthly.groupby("run_id", sort=False):
    assert group.month.tolist() == expected, identity
returns = monthly.pivot(index="month", columns="run_id", values="simple_return")
RF = monthly[monthly.run_id == "SPY-5bps"].RF.to_numpy()
ids = summary["primary_ids"]
accounts = {r["run_id"]: r for r in summary["runs"]}
pd.DataFrame({"Verified item": ["Aligned months", "Source accounts", "Derived tranches", "Monthly rows"], "Count": [300, 108, 8, len(monthly)]})
''')
    md('''## Results

### 3. Report the entire calendar/cost grid

The outlined row is the designated March/September reference. Colors and signed values represent a scenario difference, not statistical certainty.''')
    code('''fig = calendar_figure(summary)
display(fig)
plt.close(fig)
''')
    md('''The primary 5 bps comparison wins against three calendars and loses against three. All scenarios share the same history; these are not independent replications.''')
    md('''### 4. Recompute growth and monthly risk

The table combines daily maximum drawdown from the validated ledger with newly recomputed monthly risk. TE is annualized tracking error to SPY; cash earns zero.''')
    code('''risk_rows = []
for key in ["monthly", "semiannual", "tranched", "benchmark"]:
    identity = ids[key]
    vector = returns[identity].to_numpy()
    calculated = risk_metrics(vector, returns[ids["benchmark"]].to_numpy(), RF)
    CAGR = np.expm1(12 * np.log1p(vector).mean())
    assert abs(CAGR - accounts[identity]["metrics"]["full_period"]["cagr"]) < 1e-12
    for name, value in calculated.items():
        if value is not None:
            assert abs(value - accounts[identity]["monthly_risk"][name]) < 1e-10
    risk_rows.append({"Portfolio": key, "CAGR %": 100*CAGR,
        "Daily max DD %": 100*accounts[identity]["metrics"]["full_period"]["max_drawdown"],
        "Sharpe": calculated["sharpe_monthly_annualized"],
        "TE %": 100*calculated["tracking_error_monthly_annualized"],
        "SPY beta": calculated["beta_to_SPY_excess_returns"]})
pd.DataFrame(risk_rows).round(3)
''')
    code('''fig = wealth_figure(summary, DATA / "validation-daily-nav.csv")
display(fig)
plt.close(fig)
''')
    md('''The tranche's maximum drawdown is deeper than monthly or March/September in this history. The construction spreads a calendar allocation; it is not a guarantee of lower market risk.''')
    md('''### 5. Recompute the paired bootstrap intervals

Use 10,000 joint draws, seed 20261009, mean blocks 12 (primary), 6 and 24 months. Each estimate is a difference of sampled CAGRs. A shared monthly draw retains dependence between strategy returns.''')
    code('''labels = [ids[k] for k in ["monthly", "semiannual", "tranched", "weight_reset", "benchmark"]]
comparisons = [("monthly_minus_march_september", labels[0], labels[1]),
               ("monthly_minus_tranched", labels[0], labels[2])]
recomputed = paired_cagr_intervals(returns[labels].to_numpy(), labels, comparisons, summary["protocol"]["bootstrap"])
for calculated, saved in zip(recomputed, summary["primary_intervals"]):
    assert calculated["comparison"] == saved["comparison"]
    assert np.allclose(calculated["ci95_difference_pp"], saved["ci95_difference_pp"], atol=1e-10, rtol=0)
pd.DataFrame([{"Comparison": r["comparison"], "Block months": r["mean_block_months"],
    "Estimate pp/yr": r["cagr_difference_pp"], "95% lower": r["ci95_difference_pp"][0],
    "95% upper": r["ci95_difference_pp"][1]} for r in recomputed]).round(3)
''')
    code('''fig = interval_figure(summary)
display(fig)
plt.close(fig)
''')
    md('''Both primary intervals cross zero; that does not prove equivalence. Resampling assumptions and nonstationarity are material. A sampled return path does not recreate the strategy on an alternative market price path.''')
    md('''### 6. Keep trading costs attached

Each cost uses its separately computed accounts. The tranche retains gross sleeve costs without netting.''')
    code('''fig = cost_figure(summary)
display(fig)
plt.close(fig)
''')
    md('''## Takeaways

1. Calendar choice changes the sign of the frequency comparison in the primary sample.
2. The tranche is an explicit comparison, with a deeper observed drawdown rather than a promised improvement.
3. The primary intervals do not establish a general frequency ranking.
4. Computation is reconciled on the same vendor snapshot; source-price and execution accuracy are separate questions.

The same AI agent authored the calculation and separate verifier. Owner review is partial; it does not establish full owner notebook reproduction or independent external validation. The A/B/C appendix, 2026 case and exact hashes remain in the saved summary; macro-state and multi-factor extensions are deferred.

References: [method protocol](../docs/methods/validation-study.md), [validation memo](../docs/validation/validation-memo.md), [design decisions](../docs/methods/design-decisions.md), [reproduction guide](../docs/reproduction.md), [French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), [Politis and Romano stationary bootstrap](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870).
''')
    nb=nbf.v4.new_notebook(cells=cells,metadata={"kernelspec":{"display_name":"Python 3 (research environment)","language":"python","name":"python3"},"language_info":{"name":"python"}})
    nbf.validate(nb)
    directory=ROOT/"notebooks";directory.mkdir(exist_ok=True)
    kernel_root=ROOT/"tmp/jupyter";kernel=kernel_root/"kernels/rebalance-lab";kernel.mkdir(parents=True,exist_ok=True)
    (kernel/"kernel.json").write_text(json.dumps({"argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],"display_name":"Rebalance Lab","language":"python"}))
    os.environ["JUPYTER_PATH"]=str(kernel_root)
    os.environ["JUPYTER_RUNTIME_DIR"]=str(ROOT/"tmp/jupyter-runtime")
    client=NotebookClient(nb,timeout=180,kernel_name="rebalance-lab",resources={"metadata":{"path":str(directory)}})
    client.execute()
    image_count=sum("image/png" in output.get("data",{}) for cell in nb.cells for output in cell.get("outputs",[]))
    assert image_count>=4,"native plots missing from notebook outputs"
    path=directory/"validation-study.ipynb";nbf.write(nb,path)
    downloads=ROOT/"site/downloads";downloads.mkdir(exist_ok=True);shutil.copyfile(path,downloads/path.name)
    exporter=HTMLExporter(template_name="lab");exporter.require_js_url="";exporter.mathjax_url=""
    body,_=exporter.from_notebook_node(nb)
    # Export is read-only; repair repository-relative notebook links for the static site.
    body=body.replace('href="../docs/', 'href="https://github.com/Yuchi-Wang02/rebalance-lab/blob/main/docs/')
    import re
    body=body.replace('<title>Notebook</title>','<title>Rebalance Lab: Validation Companion</title>')
    navigation='<div style="padding:16px 28px;background:#f6f4ed;font-family:system-ui"><a href="pilot.html">← Rebalance Lab study</a> · <a href="downloads/validation-study.ipynb">Executed notebook download</a></div>'
    body=re.sub(r'(<body\b[^>]*>)',lambda match:match[0]+navigation,body,count=1)
    (ROOT/"site/notebook.html").write_text(body,encoding="utf-8")
    print(f"Executed {sum(c.cell_type=='code' for c in nb.cells)} code cells; {image_count} native plot outputs; notebook and HTML saved.")


if __name__=="__main__":build()
