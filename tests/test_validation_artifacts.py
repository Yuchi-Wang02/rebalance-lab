import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.validate_validation_artifacts import check

ROOT=Path(__file__).resolve().parents[1]


class PublicValidationTests(unittest.TestCase):
    def clone(self,directory):
        root=Path(directory)
        s=json.loads((ROOT/"site/data/validation-study-summary.json").read_text())
        names=["site/data/validation-study-summary.json","site/data/validation-study-replay.json",
               "site/data/validation-monthly-returns.csv","site/data/validation-daily-nav.csv","site/data/validation-risk-metrics.csv",
               "configs/sector-etf-validation.v1.json","docs/validation/etf-validation-protocol-freeze.json","scripts/validate_validation_study_independent.py","scripts/prepare_validation_artifacts.py",*s["code_sha256"]]
        for name in names:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        return root

    def test_public_summary_reconciles(self):
        with contextlib.redirect_stdout(io.StringIO()):s=check()
        self.assertEqual(s["months"],300)

    def test_stale_summary_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.clone(temp);p=root/"site/data/validation-study-summary.json";s=json.loads(p.read_text());s["months"]=299;p.write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError,"stale public summary"):check(root)

    def test_missing_or_shifted_month_rejected_even_if_rehashed(self):
        for mutate in ("missing","shifted"):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as temp:
                root=self.clone(temp);p=root/"site/data/validation-monthly-returns.csv"
                with p.open(newline="") as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
                if mutate=="missing":rows.pop(10)
                else:rows[10]["month"]="2002-03"
                with p.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
                summary=root/"site/data/validation-study-summary.json";s=json.loads(summary.read_text())
                s["derived_inputs"][p.name]["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest();summary.write_text(json.dumps(s))
                receipt=root/"site/data/validation-study-replay.json";v=json.loads(receipt.read_text());v["public_summary_sha256"]=hashlib.sha256(summary.read_bytes()).hexdigest();receipt.write_text(json.dumps(v))
                with self.assertRaisesRegex(ValueError,"missing, duplicate or shifted"):check(root)

    def test_executed_notebook_has_native_plots_and_no_errors(self):
        nb=json.loads((ROOT/"notebooks/validation-study.ipynb").read_text())
        code=[c for c in nb["cells"] if c["cell_type"]=="code"]
        self.assertTrue(all(c["execution_count"] is not None for c in code))
        outputs=[o for c in code for o in c["outputs"]]
        self.assertFalse(any(o["output_type"]=="error" for o in outputs))
        self.assertGreaterEqual(sum("image/png" in o.get("data",{}) for o in outputs),4)

    def test_wrong_risk_export_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.clone(temp);p=root/"site/data/validation-risk-metrics.csv"
            with p.open(newline="") as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            rows[0]["sharpe_monthly_annualized"]="99"
            with p.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"risk CSV metric binding"):check(root)

    def test_shifted_session_rejected_even_if_rehashed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=self.clone(temp);p=root/"site/data/validation-monthly-returns.csv"
            with p.open(newline="") as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
            rows[0]["session"]="2001-01-30"
            with p.open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            summary=root/"site/data/validation-study-summary.json";s=json.loads(summary.read_text())
            s["derived_inputs"][p.name]["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest();summary.write_text(json.dumps(s))
            receipt=root/"site/data/validation-study-replay.json";v=json.loads(receipt.read_text());v["public_summary_sha256"]=hashlib.sha256(summary.read_bytes()).hexdigest();receipt.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,"monthly session alignment"):check(root)


if __name__=="__main__":unittest.main()
