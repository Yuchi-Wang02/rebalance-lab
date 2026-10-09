#!/usr/bin/env python3
"""Four-page research brief and standalone validation memo from one summary."""
import json
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
import matplotlib.font_manager as fonts

PAPER=HexColor("#faf9f5");INK=HexColor("#172f3a");MUTED=HexColor("#58656b");GREEN=HexColor("#557867");LINE=HexColor("#d5d9cf")
WIDTH,HEIGHT=letter;LEFT=43;RIGHT=WIDTH-43;SPAN=RIGHT-LEFT
for name,family,weight in [("Body","DejaVu Sans","normal"),("BodyBold","DejaVu Sans","bold"),("Display","DejaVu Serif","normal")]:
    pdfmetrics.registerFont(TTFont(name,fonts.findfont(fonts.FontProperties(family=family,weight=weight))))
BODY=ParagraphStyle("body",fontName="Body",fontSize=10.2,leading=14.2,textColor=INK,spaceAfter=9)
SMALL=ParagraphStyle("small",parent=BODY,fontSize=8.4,leading=11.8,textColor=MUTED)
LEAD=ParagraphStyle("lead",parent=BODY,fontSize=12.2,leading=17)


def para(c,text,y,style=BODY,width=SPAN,x=LEFT):
    p=Paragraph(text.replace("–","-").replace("—","-").replace("−","-"),style)
    _,height=p.wrap(width,HEIGHT);require(y-height>44,"PDF content crosses footer")
    p.drawOn(c,x,y-height);return y-height-10
def require(v,message):
    if not v:raise ValueError(message)
def heading(c,text,y):
    c.setFillColor(GREEN);c.setFont("BodyBold",10.8);c.drawString(LEFT,y-12,text);return y-25
def start(c,page,label,title):
    c.setFillColor(PAPER);c.rect(0,0,WIDTH,HEIGHT,fill=1,stroke=0)
    c.setFillColor(GREEN);c.setFont("BodyBold",9);c.drawString(LEFT,HEIGHT-42,"REBALANCE LAB / VALIDATION RESEARCH")
    c.setFillColor(MUTED);c.setFont("Body",8);c.drawRightString(RIGHT,HEIGHT-42,"9 October 2026 / Version 1")
    c.setStrokeColor(LINE);c.line(LEFT,HEIGHT-54,RIGHT,HEIGHT-54)
    c.setFillColor(INK);c.setFont("Display",25);c.drawString(LEFT,HEIGHT-89,title)
    c.setFillColor(MUTED);c.setFont("Body",9);c.drawString(LEFT,HEIGHT-108,label)
    c.setFont("Body",8);c.drawString(LEFT,25,"Retrospective evidence | 2001-2025 | No trading recommendation")
    c.drawRightString(RIGHT,25,f"{page} / 4")
    return HEIGHT-132
def table(c,data,widths,y,font=9):
    style=ParagraphStyle("cell",fontName="Body",fontSize=font,leading=font*1.4,textColor=INK)
    wrapped=[[Paragraph(escape(str(x)),style) for x in row] for row in data]
    t=Table(wrapped,colWidths=widths,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),HexColor("#e2e9dd")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("LINEBELOW",(0,0),(-1,-1),.45,LINE),
        ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8)]))
    _,h=t.wrap(SPAN,HEIGHT);require(y-h>48,"table crosses footer");t.drawOn(c,LEFT,y-h);return y-h-13
def pct(x):return f"{100*x:.2f}%"


def build(s):
    out=ROOT/"output/pdf";out.mkdir(parents=True,exist_ok=True)
    path=out/"rebalance-lab-validation-brief.pdf";c=canvas.Canvas(str(path),pagesize=letter,invariant=1)
    c.setTitle("Rebalance Lab: A Validation Study of Momentum Rebalancing");c.setAuthor("Rebalance Lab - AI-assisted research documentation")
    runs={r["run_id"]:r for r in s["runs"]};ids=s["primary_ids"]
    m,a,t,spy=[runs[ids[k]] for k in ("monthly","semiannual","tranched","benchmark")]
    y=start(c,1,"Calendar timing, trading costs, and reproducible backtests","Momentum Rebalancing Validation")
    y=para(c,"<b>The monthly-semiannual comparison changes sign across six rebalancing calendars.</b>",y,LEAD)
    y=para(c,"Evaluate the claim that more frequent momentum selection improves net portfolio performance. Nine sector ETFs, two signals, six semiannual schedules and four costs form a bounded historical test. The principal finding is calendar sensitivity; inference does not establish a general frequency ranking.",y)
    y=heading(c,"Complete primary calendar grid",y)
    data=[["Semiannual signal months","0 bps","5 bps","10 bps","25 bps"]]
    names=["Jan / Jul","Feb / Aug","Mar / Sep (reference)","Apr / Oct","May / Nov","Jun / Dec"]
    for j,name in enumerate(names):
        data.append([name,*[f"{next(r['cagr_difference_pp'] for r in s['calendar_comparisons'] if r['signal']=='12-1' and r['phase']==[j+1,j+7] and r['cost_bps_per_side']==cost):+.2f}" for cost in [0,5,10,25]]])
    y=table(c,data,[190,84,84,84,84],y,9.6)
    y=para(c,"Monthly minus semiannual CAGR, percentage points per year. Positive favors monthly. The 5 bps range is -0.92 to +0.53; March/September is -0.49. All 48 cells across both signals are available in the report. A scenario range is not a confidence interval.",y,SMALL)
    y=heading(c,"The verification approach",y)
    y=para(c,"Rules fixed before extension runs with prior history exposure disclosed; closing signals and next-open proxy execution; separate cost accounts; all calendars retained; second implementations reconcile accounting and statistics.",y)
    y=heading(c,"Principal judgment",y)
    y=para(c,"The calculation supports a calendar-sensitive result in this sample. It does not establish an optimal frequency or show that timing luck explains all performance differences. The additional tranche test and uncertainty appear on the next two pages.",y)
    c.showPage()
    y=start(c,2,"Equal initial allocation; autonomous sleeves; no reporting-boundary reset","Test the Tranche Comparison")
    y=para(c,"Six semiannual sleeves each receive one-sixth of initial capital. They first execute on 3 January 2000, then continue without capital transfers or order netting. The 2000 burn-in can create unequal sleeve capital. Reporting from the 2000 year-end close normalizes pooled NAV; it does not re-equalize the sleeves.",y)
    # PDF-sized chart keeps axis and legend type readable at the printed width.
    from pilot.validation_figures import wealth_figure
    import matplotlib.pyplot as plt
    fig=wealth_figure(s,ROOT/"site/data/validation-daily-nav.csv")
    fig.set_size_inches(7.3,4.3)
    ax,dd=fig.axes
    ax.set_title("Primary wealth and daily drawdown",fontsize=11,loc="left",pad=10)
    ax.legend(frameon=False,ncol=2,loc="upper left",fontsize=8)
    for axis in (ax,dd):axis.tick_params(labelsize=8);axis.yaxis.label.set_size(8.5)
    dd.set_xticks([__import__('datetime').date(2000,12,29),__import__('datetime').date(2010,1,1),__import__('datetime').date(2020,1,1),__import__('datetime').date(2025,12,31)],["2000 close","2010","2020","2025 close"])
    temp=ROOT/"tmp/pdfs";temp.mkdir(parents=True,exist_ok=True);chart=temp/"wealth-print.png";fig.savefig(chart,dpi=220);plt.close(fig)
    image_height=SPAN*4.3/7.3;c.drawImage(str(chart),LEFT,y-image_height,width=SPAN,height=image_height,preserveAspectRatio=True,anchor="c");y-=image_height+12
    y=para(c,"Each path normalized at the reporting anchor; 12-1 signal, 5 bps per side. SPY is opportunity-cost context with different exposures, not a frequency control. Drawdown uses daily closing NAV.",y,SMALL)
    y=heading(c,"The mitigation has a tradeoff",y)
    y=para(c,f"Tranche net CAGR is <b>{pct(t['metrics']['full_period']['cagr'])}</b>, compared with {pct(m['metrics']['full_period']['cagr'])} monthly and {pct(a['metrics']['full_period']['cagr'])} for March/September. Its <b>{pct(t['metrics']['full_period']['max_drawdown'])}</b> maximum drawdown is deeper than both. Pooling calendars does not guarantee better growth or a shallower loss.",y)
    c.showPage()
    y=start(c,3,"Monthly risk metrics and paired intervals accompany the return comparison","Uncertainty and Risk")
    y=heading(c,"Primary risk comparison",y)
    data=[["Portfolio","CAGR","Max DD","Sharpe","TE","Beta","NAV/yr"]]
    for label,r in [("Monthly",m),("Mar / Sep",a),("Tranche",t),("SPY context",spy)]:
        q=r['metrics']['full_period'];v=r['monthly_risk'];data.append([label,pct(q['cagr']),pct(q['max_drawdown']),f"{v['sharpe_monthly_annualized']:.3f}",pct(v['tracking_error_monthly_annualized']),f"{v['beta_to_SPY_excess_returns']:.3f}",f"{q['annualized_two_sided_turnover']:.2f}x"])
    y=table(c,data,[112,65,71,65,71,65,77],y,8.9)
    y=para(c,"Sharpe uses monthly excess returns and captured French RF. TE is annualized monthly tracking error to SPY; beta includes an intercept and uses excess returns. DD is daily maximum drawdown; NAV/yr is gross buys plus sells. Cash earns zero.",y,SMALL)
    y=heading(c,"Paired 95% intervals for CAGR differences",y)
    primary=[r for r in s['primary_intervals'] if r['primary_block']]
    data=[["Monthly minus","Estimate, pp/yr","95% interval, pp/yr"]]
    for label,r in zip(["March / September","Six-sleeve tranche"],primary):
        data.append([label,f"{r['cagr_difference_pp']:+.2f}",f"[{r['ci95_difference_pp'][0]:+.2f}, {r['ci95_difference_pp'][1]:+.2f}]"])
    y=table(c,data,[223,120,183],y,10)
    y=para(c,"10,000 paired stationary bootstrap draws of 300 net monthly returns; seed 20261009; primary expected block length 12 months. The same resampled months apply to every account. Compute sampled compounded annual growth, then the paired difference.",y)
    y=heading(c,"Block sensitivity",y)
    data=[["Mean block","Monthly - Mar/Sep CI","Monthly - tranche CI"]]
    for n in [6,12,24]:
        rr=[r for r in s['primary_intervals'] if r['mean_block_months']==n]
        data.append([f"{n} months",*[f"[{r['ci95_difference_pp'][0]:+.2f}, {r['ci95_difference_pp'][1]:+.2f}]" for r in rr]])
    y=table(c,data,[130,198,198],y,9.1)
    y=para(c,"<b>Both primary intervals include zero.</b> This does not prove equivalence. The intervals are conditional on realized net returns and resampling assumptions; they do not remove nonstationarity or retrospective design risk. No winning calendar is promoted.",y)
    c.showPage()
    y=start(c,4,"Calculation reconciled; general frequency superiority unsupported","Validation Memo")
    sections=[("Scope and disposition","Accept as a reproducible, bounded historical validation case. Compare nine sector ETFs across two signals, six semiannual schedules and four costs, plus six-sleeve pooled accounts. Primary inference is 2001-2025, 12-1, 5 bps. Do not use this case to certify a live strategy or choose an optimal calendar."),
      ("Data lineage","Preserved Yahoo responses -> common-session adjusted prices -> portfolio accounts -> accounting replay -> tranche sums -> monthly risk and paired intervals -> public derived CSVs and summary. SHA-256 binds snapshots, configuration and code. French monthly RF is captured separately and joined to 300 months. Hash identity does not certify source accuracy."),
      ("Separate implementation checks","Legacy replay: 60 paths. Mechanism replay: 108 paths, 726,732 daily states, maximum relative NAV error 1.78e-14. Extension: eight tranches, 53,832 daily states and 34,800 monthly rows; capital, cash, units, gross fees, risk and bootstrap percentiles reconcile. The extension verifier imports no project calculation code."),
      ("Independence boundary","The same AI agent authored both implementations. Separate algorithms can expose arithmetic and implementation defects but cannot exclude a shared misunderstanding of the specification. No external reviewer agreement, independent price validation or live fill certification is claimed."),
      ("Findings and residual risk","The primary difference changes sign across calendars; both paired intervals span zero. Tranching retains a deeper drawdown. Prior history exposure, adjusted-price/opening proxies, fixed costs, zero-interest cash, changing sector exposures and bootstrap nonstationarity remain risks. Written owner result and judgment reviews are accepted; signal-window explanation and observed oral presentation remain pending.")]
    for title,text in sections:y=heading(c,title,y);y=para(c,text,y,ParagraphStyle("memo",parent=BODY,fontSize=9.8,leading=13.5))
    y=para(c,'<b>Evidence:</b> <link href="https://yuchi-wang02.github.io/rebalance-lab/pilot.html" color="#557867">Study and downloads</link> | <link href="https://github.com/Yuchi-Wang02/rebalance-lab" color="#557867">Repository, methods and receipts</link><br/><b>Method/source:</b> French Data Library monthly RF; Politis and Romano (1994), The Stationary Bootstrap. Exact URLs and capture hashes appear in the reproduction guide.',y,SMALL)
    c.save()
    reader=PdfReader(path);require(len(reader.pages)==4,"brief must contain four pages")
    import io
    memo=out/"rebalance-lab-validation-memo.pdf";overlay=io.BytesIO()
    stamp=canvas.Canvas(overlay,pagesize=letter,invariant=1)
    stamp.setFillColor(PAPER);stamp.rect(RIGHT-45,18,46,17,fill=1,stroke=0)
    stamp.setFillColor(MUTED);stamp.setFont("Body",8);stamp.drawRightString(RIGHT,25,"1 / 1");stamp.save();overlay.seek(0)
    memo_page=reader.pages[3];memo_page.merge_page(PdfReader(overlay).pages[0])
    writer=PdfWriter();writer.add_page(memo_page);writer.write(memo)
    for p in [path,memo]:shutil.copyfile(p,ROOT/"site/assets"/p.name)
    # A new code-drawn sharing card; no external imagery or media download.
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new("RGB",(1200,630),"#f6f4ed");draw=ImageDraw.Draw(image)
    font_path=fonts.findfont(fonts.FontProperties(family="DejaVu Sans"));display=fonts.findfont(fonts.FontProperties(family="DejaVu Serif"))
    f=lambda size:ImageFont.truetype(font_path,size)
    draw.text((58,45),"REBALANCE LAB / VALIDATION RESEARCH",font=f(19),fill="#557867")
    for j,line in enumerate(["A Validation Study of","Momentum Rebalancing"]):draw.text((58,120+j*76),line,font=ImageFont.truetype(display,54),fill="#172f3a")
    draw.line((58,320,1142,320),fill="#d5d9cf",width=2)
    draw.text((58,362),"Calendar-sensitive results. Paired uncertainty.",font=f(29),fill="#172f3a")
    draw.text((58,410),"Separate implementations. Explicit remaining risk.",font=f(26),fill="#557867")
    draw.text((58,550),"Nine sector ETFs  |  2001-2025  |  Retrospective study",font=f(20),fill="#58656b")
    image.save(ROOT/"site/assets/validation-preview.png")
    renderer=shutil.which("pdftoppm")
    if renderer:
        import subprocess
        subprocess.run([renderer,"-r","108","-png",str(path),str(temp/"brief-page")],check=True,capture_output=True)
    else:
        import pypdfium2
        doc=pypdfium2.PdfDocument(path)
        for i,page in enumerate(doc):page.render(scale=1.5).to_pil().save(temp/f"brief-page-{i+1}.png")
    print("Generated four-page brief, one-page memo, sharing card and rendered QA pages.")


if __name__=="__main__":
    from scripts.validate_validation_artifacts import check
    build(check())
