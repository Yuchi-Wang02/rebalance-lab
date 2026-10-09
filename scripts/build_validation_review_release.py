#!/usr/bin/env python3
"""Build and verify a local review release; no Git write or remote publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=(".github","configs","docs","pilot","spmo_lab","stock_pilot","scripts","tests","site","notebooks")
ROOT_FILES=("README.md","CONTRIBUTING.md","LICENSE","NOTICE",".gitignore",".gitattributes","requirements-pilot.txt","requirements-analysis.txt","requirements-research.txt")
EXCLUDED_PARTS={"__pycache__",".git",".venv","raw","processed","generated","tmp","output"}
TEXT_SUFFIXES={".py",".md",".json",".csv",".html",".js",".mjs",".yml",".yaml",".css",".txt",".svg",".ipynb"}
SECRETS=[re.compile(r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{25,}'),re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    re.compile(r'["\'](?:api[_-]?key|password|access_token|client_secret)["\']\s*:\s*["\'](?!\[REDACTED|YOUR_|PLACEHOLDER)[A-Za-z0-9_+/-]{20,}["\']',re.I)]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
def require(value,message):
    if not value:raise ValueError(message)

def public_files(root=ROOT):
    files=[root/name for name in ROOT_FILES]
    for folder in FOLDERS:
        files.extend(p for p in (root/folder).rglob("*") if p.is_file() and not any(part in EXCLUDED_PARTS for part in p.relative_to(root).parts))
    files.extend((root/"results").glob("*.json"))
    files=sorted(set(files))
    for path in files:
        name=path.relative_to(root).as_posix()
        require(not path.name.startswith(".env") and not path.is_symlink(),f"excluded file: {name}")
        if path.suffix in TEXT_SUFFIXES:
            text=path.read_text(encoding="utf-8")
            require(not any(pattern.search(text) for pattern in SECRETS),f"credential-like content: {name}")
            require(not re.search(r'[A-Z]:[\\/]+(?:Users|home)[\\/]+[^\s"\']+',text,re.I),f"machine-specific content: {name}")
    return files

class Links(HTMLParser):
    def __init__(self):super().__init__();self.ids=set();self.links=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get("id"):self.ids.add(attrs["id"])
        for key in ("href","src"):
            if attrs.get(key):self.links.append(attrs[key])

def check_site(root):
    cache={};count=0
    for file in sorted((root/"site").glob("*.html")):
        parser=Links();parser.feed(file.read_text(encoding="utf-8"));cache[file.resolve()]=parser
    for file,parser in cache.items():
        for link in parser.links:
            parsed=urlsplit(link)
            if parsed.scheme or parsed.netloc:
                # Future repository links must resolve against this local release.
                prefix="/Yuchi-Wang02/rebalance-lab/blob/main/"
                if parsed.netloc.lower()=="github.com" and parsed.path.startswith(prefix):
                    require((root/unquote(parsed.path[len(prefix):])).is_file(),f"stale repository link: {file.name}")
                continue
            path=(file.parent/unquote(parsed.path)).resolve() if parsed.path else file
            require(path.is_relative_to(root.resolve()) and path.is_file(),f"broken local site asset: {file.name}: {link}")
            if parsed.fragment and path in cache:require(unquote(parsed.fragment) in cache[path].ids,f"broken section: {file.name}: {link}")
            count+=1
    return {"html_pages":len(cache),"local_links_and_assets":count}

def archive(path,files,base,manifest=None):
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for file in files:z.write(file,file.relative_to(base).as_posix())
        if manifest:z.writestr("RELEASE-MANIFEST.json",json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    with zipfile.ZipFile(path) as z:require(z.testzip() is None,"ZIP CRC failure")

def run_check(root,log_dir,name,args):
    completed=subprocess.run(args,cwd=root,text=True,encoding="utf-8",errors="replace",capture_output=True,env={**os.environ,"PYTHONUTF8":"1"})
    (log_dir/(name+".log")).write_text(completed.stdout+completed.stderr,encoding="utf-8")
    require(completed.returncode==0,f"check failed: {name}; inspect its local log")
    return completed.stdout+completed.stderr

def execute_notebook(root):
    import nbformat
    from nbclient import NotebookClient
    folder=root/"tmp/jupyter/kernels/review-kernel";folder.mkdir(parents=True)
    save(folder/"kernel.json",{"argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],"display_name":"Release check","language":"python"})
    previous=os.environ.get("JUPYTER_PATH");os.environ["JUPYTER_PATH"]=str(root/"tmp/jupyter")
    try:
        nb=nbformat.read(root/"notebooks/validation-study.ipynb",as_version=4)
        for cell in nb.cells:
            if cell.cell_type=="code":cell.execution_count=None;cell.outputs=[]
        NotebookClient(nb,timeout=180,kernel_name="review-kernel",resources={"metadata":{"path":str(root/"notebooks")}}).execute()
        code=[c for c in nb.cells if c.cell_type=="code"]
        outputs=[o for c in code for o in c.outputs]
        require(all(c.execution_count is not None for c in code) and not any(o.output_type=="error" for o in outputs),"clean notebook execution")
        images=sum("image/png" in o.get("data",{}) for o in outputs)
        require(images==4,"four notebook figures required")
        nbformat.write(nb,root/"tmp/clean-release-notebook.ipynb")
        return {"clean_kernel":True,"private_inputs_present":False,"executed_cells":len(code),"native_plots":images}
    finally:
        if previous is None:os.environ.pop("JUPYTER_PATH",None)
        else:os.environ["JUPYTER_PATH"]=previous

def build(node):
    out=ROOT/"output/review";out.mkdir(parents=True,exist_ok=True)
    logs=out/"logs";logs.mkdir(exist_ok=True)
    screenshots=["home-desktop.jpg","etf-mobile.jpg","etf-uncertainty-desktop.jpg","etf-data-failure.jpg","notebook-desktop.jpg"]
    presentation=json.loads((ROOT/"results/presentation-review.json").read_text(encoding="utf-8"))
    require(presentation["reviewer"]=="AI assistant" and presentation["independent_human_review"] is False,"presentation review provenance")
    for name,digest in presentation["artifact_sha256"].items():
        require(sha(ROOT/name)==digest,f"presentation review is stale: {name}")
    require(all((out/"screenshots"/n).stat().st_size>1000 for n in screenshots),"browser review evidence required")
    files=public_files();site_check=check_site(ROOT)
    zip_path=out/"rebalance-lab-public-review.zip"
    archive(zip_path,files,ROOT)
    # Fresh extraction has no .git, raw vendor inputs or private account ledgers.
    fresh=ROOT/"tmp"/("release-check-"+uuid.uuid4().hex[:12]);fresh.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():require((fresh/name).resolve().is_relative_to(fresh.resolve()),"unsafe archive entry")
        z.extractall(fresh)
    checks={}
    for script in ("validate_design","validate_pilot_artifacts","validate_stock_pilot_artifacts","validate_validation_artifacts"):
        run_check(fresh,logs,script,[sys.executable,"-X","utf8",f"scripts/{script}.py"]);checks[script]=True
    output=run_check(fresh,logs,"python-tests",[sys.executable,"-X","utf8","-m","unittest","discover","-s","tests","-p","test_*.py"])
    match=re.search(r"Ran (\d+) tests",output);require(match and "OK" in output and "skipped=" not in output,"full numerical tests required")
    checks["python_tests"]={"passed":int(match[1]),"skipped":0}
    output=run_check(fresh,logs,"javascript-tests",[node,"--test","tests/test_pilot_ui.mjs","tests/test_validation_ui.mjs"])
    match=re.search(r"(?:ℹ|#) tests (\d+)",output);require(match,"JavaScript test receipt missing")
    checks["javascript_tests"]={"passed":int(match[1])}
    for script in ("app","pilot","stocks","validation"):run_check(fresh,logs,"syntax-"+script,[node,"--check",f"site/{script}.js"])
    checks["javascript_syntax"]=True;checks["public_site_links"]=check_site(fresh)
    checks["public_only_notebook"]=execute_notebook(fresh)
    from pypdf import PdfReader
    brief=PdfReader(ROOT/"site/assets/rebalance-lab-validation-brief.pdf");memo=PdfReader(ROOT/"site/assets/rebalance-lab-validation-memo.pdf")
    require(len(brief.pages)==4 and len(memo.pages)==1,"PDF page counts")
    require(all(len(p.extract_text())>700 for p in brief.pages),"PDF text missing")
    checks["pdf"]={"brief_pages":4,"memo_pages":1,**presentation["pdf"]}
    checks["browser"]={**presentation["browser"],"screenshots":screenshots}
    # Preparation state and owner state are separate from remote authorization.
    status=json.loads((ROOT/"results/status.json").read_text(encoding="utf-8"))
    progress=json.loads((ROOT/"results/owner-review-progress.json").read_text(encoding="utf-8"))
    for key in ("actual_answers_recorded","checkpoint_1","checkpoint_2","checkpoint_3"):
        require(status["owner_review"][key]==progress[key],"owner progress projection is stale")
    require(status["owner_presentation_ready"]==progress["owner_presentation_ready"],"owner readiness projection")
    status["stage"]="research_and_presentation_complete_local_review"
    status["research_and_presentation_complete"]=True
    status["publication"]["local_review_package_complete"]=True
    save(ROOT/"results/status.json",status)
    baseline=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    tracked=[p for p in files if p.relative_to(ROOT).parts[0] in {"site","notebooks"} or p.relative_to(ROOT).as_posix() in {"README.md","docs/studies/validation-study.md","docs/methods/validation-study.md","docs/validation/validation-memo.md","docs/methods/design-decisions.md","docs/reproduction.md","results/status.json"}]
    dirty=bool(subprocess.run(["git","status","--porcelain"],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip())
    tracked.extend([ROOT/"results/owner-review-progress.json",ROOT/"results/presentation-review.json"])
    record={"schema_version":2,"recorded_at_utc":datetime.now(timezone.utc).isoformat(),"baseline_commit":baseline,"implementation_is_uncommitted":dirty,"research_and_presentation_complete":True,"owner_presentation_ready":status["owner_presentation_ready"],"new_version_deployed":status["publication"]["new_version_deployed"],"checks":checks,"release_scope":{"raw_vendor_data":False,"credentials":False,"private_ledgers":False,"private_owner_material":False},"artifact_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in tracked}}
    save(ROOT/"results/validation-release.json",record)
    review='''# Rebalance Lab：本地发布审阅包

研究与展示已完成；交易核对、结果和判断的书面复核已接受。精确信号窗口的本人解释及观察到的口述仍待补，完整 Notebook 本人复算未核实。公开生产版本的发布状态以 results/status.json 和 GitHub 实际状态为准。

先看四页英文 brief 和 README 首屏，再看三次复核表。公开审阅 ZIP 包含代码、派生输入、Notebook、网页、六份核心阅读材料和历史证据；不含原始行情、凭据、私有账户路径或本人复核参考答案。单独的 owner ZIP 是私人学习和面试准备材料。

## 发布前逐项审阅

- [x] 配置和扩展运行前冻结记录绑定；历史结果已看过的事实已披露。
- [x] 原始账户、分批账户、统计、图表及导出材料完成相应检查。
- [x] 从公开 ZIP 的新目录复核旧／新结果，执行全部测试和干净内核 Notebook。
- [x] 桌面、手机、键盘、加载失败及无 JavaScript 情形已检查；PDF 逐页查看。
- [x] 原始 75 股方案归档，历史链接保留，旧试点含义不被新结果覆盖。
- [x] MIT 许可和第三方数据排除说明已准备。
- [x] 依据实际提交更新本人贡献与进度；未完成部分单独保留。
- [ ] 本人补足精确信号窗口解释和口述展示。
- [ ] 用户审阅具体成品，并明确授权公开的新版本。
- [ ] 获得授权后核对暂存清单、commit、push、CI、Pages；部署后检查真实页面和下载。

本地检查通过不等于远程 CI 已运行；本地打包不等于已发布。计算复算也不等于外部同行或独立行情核验。

## 项目包装与标签（待发布设置）

Title: Rebalance Lab: A Validation Study of Momentum Rebalancing

Subtitle: Calendar Timing, Trading Costs, and Reproducible Backtests

Repository description: A reproducible validation study of momentum rebalancing: calendar sensitivity, trading costs, paired uncertainty and separate calculation checks.

Suggested GitHub topics: financial-research, model-validation, momentum, rebalancing, backtesting, reproducible-research, robustness-checks, bootstrap, risk-analysis.

Sharing card: site/assets/validation-preview.png。首页、README 和简报使用同一发现；不使用高收益、证明 timing luck、事前预注册或独立人类验证等超出证据的表述。

## 本地阅读

Windows：用研究环境执行 `python -m http.server 8000 --directory site`，然后打开 http://127.0.0.1:8000/。

校验记录：results/validation-release.json。ZIP 内 RELEASE-MANIFEST.json 列出每个公开文件的 SHA-256。完整引擎复算另需 reproduction guide 指定的私有快照；公开 Notebook 只用派生输入。
'''
    (out/"START-HERE.md").write_text(review,encoding="utf-8")
    files=public_files()
    manifest={"schema_version":2,"recorded_at_utc":record["recorded_at_utc"],"baseline_commit":baseline,"uncommitted_local_review":dirty,"public_file_count":len(files),"files":{p.relative_to(ROOT).as_posix():{"sha256":sha(p),"bytes":p.stat().st_size} for p in files},"exclusions":["raw vendor data","credentials","private account ledgers","owner checkpoint answers and reviewer guide",".git and virtual environment"]}
    save(out/"public-release-manifest.json",manifest);archive(zip_path,files,ROOT,manifest)
    with zipfile.ZipFile(zip_path) as z:
        require(len(z.namelist())==len(files)+1,"final archive size")
        for name,item in manifest["files"].items():require(hashlib.sha256(z.read(name)).hexdigest()==item["sha256"],"final archive hash mismatch")
    owner=ROOT/"output/private/owner-review";owner_files=sorted(p for p in owner.iterdir() if p.is_file())
    archive(out/"rebalance-lab-owner-review-private.zip",owner_files,owner)
    save(out/"package-receipt.json",{"public_zip_sha256":sha(zip_path),"public_file_count":len(files),"owner_zip_sha256":sha(out/"rebalance-lab-owner-review-private.zip"),"new_version_deployed":False})
    print(json.dumps({"public_files":len(files),"checks":checks,"public_zip":str(zip_path),"owner_ready":False,"deployed":False},indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--node",default=shutil.which("node"));args=parser.parse_args()
    require(args.node,"Node executable required");build(args.node)
