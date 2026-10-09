"""Public-input figures shared by the report and executed companion notebook."""
import csv
import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import PercentFormatter, ScalarFormatter
from matplotlib.patches import Rectangle

COLORS={"monthly":"#213e50","semiannual":"#557867","tranched":"#ae7b31","benchmark":"#858b8f"}
LABELS={"monthly":"Monthly","semiannual":"March / September","tranched":"Six-sleeve tranche","benchmark":"SPY context"}


def style():
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10.5,"axes.spines.top":False,"axes.spines.right":False,
        "axes.facecolor":"#faf9f5","figure.facecolor":"#faf9f5","text.color":"#172f3a","axes.labelcolor":"#172f3a",
        "xtick.color":"#58656b","ytick.color":"#58656b","svg.fonttype":"none","savefig.bbox":"tight"})


def calendar_figure(summary):
    style();fig,axes=plt.subplots(1,2,figsize=(11.4,4.8),sharey=True,layout="constrained")
    costs=[0,5,10,25];rows=summary["calendar_comparisons"]
    bound=max(abs(r["cagr_difference_pp"]) for r in rows)
    for ax,signal,title in zip(axes,["12-1","mixed"],["12-1 momentum (primary)","Blended momentum (robustness)"]):
        matrix=[[next(r["cagr_difference_pp"] for r in rows if r["signal"]==signal and r["phase"]==[m,m+6] and r["cost_bps_per_side"]==c) for c in costs] for m in range(1,7)]
        im=ax.imshow(matrix,cmap="PuOr_r",norm=TwoSlopeNorm(vmin=-bound,vcenter=0,vmax=bound),aspect="auto")
        ax.set_xticks(range(4),[str(c) for c in costs]);ax.set_yticks(range(6),["Jan / Jul","Feb / Aug","Mar / Sep *","Apr / Oct","May / Nov","Jun / Dec"])
        ax.set_xlabel("Modeled cost per side (bps)");ax.set_title(title,fontweight="bold",pad=14)
        for y,row in enumerate(matrix):
            for x,value in enumerate(row): ax.text(x,y,f"{value:+.2f}",ha="center",va="center",color="white" if abs(value)>bound*.57 else "#172f3a",fontsize=11)
        ax.add_patch(Rectangle((-.5,1.5),4,1,fill=False,edgecolor="#172f3a",lw=1.3))
    fig.colorbar(im,ax=axes,label="Monthly minus semiannual CAGR (pp / year)",shrink=.82,pad=.035)
    fig.suptitle("The comparison depends on the semiannual calendar",fontsize=15,fontweight="bold")
    return fig


def wealth_figure(summary,daily_csv):
    style();fig,(ax,dd)=plt.subplots(2,1,figsize=(11.4,6.6),sharex=True,gridspec_kw={"height_ratios":[2,1]},layout="constrained")
    with Path(daily_csv).open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    dates=[date.fromisoformat(r["session"]) for r in rows]
    for key in ("monthly","semiannual","tranched","benchmark"):
        i=summary["primary_ids"][key];values=[float(r[i]) for r in rows];peak=1;drawdowns=[]
        for nav in values: peak=max(peak,nav);drawdowns.append(nav/peak-1)
        ls="--" if key=="benchmark" else "-"
        ax.plot(dates,values,color=COLORS[key],lw=1.6,ls=ls,label=LABELS[key])
        dd.plot(dates,drawdowns,color=COLORS[key],lw=1.2,ls=ls)
    ax.set_yscale("log");ax.set_yticks([.5,1,2,4,8]);ax.yaxis.set_major_formatter(ScalarFormatter());ax.set_ylabel("Growth of $1 (log scale)")
    ax.legend(frameon=False,ncol=2,loc="upper left",fontsize=10);ax.grid(alpha=.18)
    ax.set_title("Tranching changes the path; it does not guarantee a shallower drawdown",loc="left",fontsize=13,fontweight="bold",pad=16)
    dd.set_ylabel("Daily drawdown");dd.yaxis.set_major_formatter(PercentFormatter(1));dd.grid(alpha=.18)
    dd.set_xticks([dates[0],date(2005,1,1),date(2010,1,1),date(2015,1,1),date(2020,1,1),dates[-1]],
                 ["2000 close","2005","2010","2015","2020","2025 close"])
    dd.set_xlim(dates[0],dates[-1]);return fig


def interval_figure(summary):
    style();fig,ax=plt.subplots(figsize=(11.4,3.2),layout="constrained")
    rows=[r for r in summary["primary_intervals"] if r["primary_block"]]
    for j,r in enumerate(rows):
        lo,hi=r["ci95_difference_pp"];value=r["cagr_difference_pp"]
        ax.hlines(1-j,lo,hi,color="#213e50",lw=2);ax.scatter([value],[1-j],color="#213e50",s=45,zorder=3)
        ax.text(hi+.1,1-j,f"{value:+.2f}  [{lo:+.2f}, {hi:+.2f}]",va="center",fontsize=10)
    ax.axvline(0,color="#858b8f",ls="--",lw=1)
    ax.set_yticks([1,0],["Monthly - Mar / Sep","Monthly - six-sleeve tranche"])
    ax.set_ylim(-.6,1.6);ax.set_xlim(-3.5,5.2);ax.set_xticks([-3,-2,-1,0,1,2,3])
    ax.set_xlabel("CAGR difference (percentage points / year)")
    ax.set_title("Both paired 95% intervals cross zero",loc="left",fontweight="bold",fontsize=14,pad=14)
    ax.grid(axis="x",alpha=.15);return fig


def cost_figure(summary):
    style();fig,axes=plt.subplots(1,2,figsize=(11.4,4.1),sharey=True,layout="constrained")
    accounts={r["run_id"]:r for r in summary["runs"]};costs=[0,5,10,25]
    for ax,prefix,title in zip(axes,["12","MIX"],["12-1 momentum","Blended momentum"]):
        for low,label,color,marker in [(f"S{prefix}-03-09", "Monthly - Mar / Sep",COLORS["semiannual"],"o"),(f"T{prefix}","Monthly - tranche",COLORS["tranched"],"s")]:
            vals=[100*(accounts[f"M{prefix}-{c}bps"]["metrics"]["full_period"]["cagr"]-accounts[f"{low}-{c}bps"]["metrics"]["full_period"]["cagr"]) for c in costs]
            ax.plot(costs,vals,color=color,marker=marker,label=label,lw=1.6)
        ax.axhline(0,color="#858b8f",lw=.8);ax.set_xticks(costs);ax.set_xlabel("Modeled cost per side (bps)");ax.set_title(title,fontweight="bold");ax.grid(alpha=.15)
    axes[0].set_ylabel("CAGR difference (pp / year)");axes[0].legend(frameon=False,fontsize=9.5)
    return fig


def render_all(summary_path, output_dir):
    summary_path=Path(summary_path);summary=json.loads(summary_path.read_text(encoding="utf-8"));output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    figures={"validation-calendar-costs":calendar_figure(summary),"validation-wealth-drawdown":wealth_figure(summary,summary_path.parent/"validation-daily-nav.csv"),
             "validation-intervals":interval_figure(summary),"validation-costs":cost_figure(summary)}
    for name,fig in figures.items():
        fig.savefig(output_dir/(name+".svg"));fig.savefig(output_dir/(name+".png"),dpi=155);plt.close(fig)


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--summary",required=True);p.add_argument("--output-dir",required=True)
    a=p.parse_args();render_all(a.summary,a.output_dir)
