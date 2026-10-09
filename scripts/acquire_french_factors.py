#!/usr/bin/env python3
"""Freeze official monthly factor ZIPs and require an exact 300-month join."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SOURCES = {"FF3": ("F-F_Research_Data_Factors_CSV.zip", ["Mkt-RF", "SMB", "HML", "RF"]),
           "Mom": ("F-F_Momentum_Factor_CSV.zip", ["Mom"])}


def parse_zip(body, columns):
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(files) != 1:
            raise ValueError("expected exactly one official CSV in ZIP")
        text = archive.read(files[0]).decode("utf-8-sig")
    header = None
    result = {}
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        clean = [value.strip() for value in row]
        if set(columns).issubset(clean):
            header = clean
        if header is None or not clean[0].isdigit() or len(clean[0]) != 6:
            continue
        month = clean[0][:4] + "-" + clean[0][4:]
        if not "2001-01" <= month <= "2025-12":
            continue
        if month in result or len(clean) != len(header):
            raise ValueError("duplicate or malformed monthly factor row")
        values = {name: float(clean[header.index(name)]) for name in columns}
        if any(value in (-99.99, -999) for value in values.values()):
            raise ValueError("missing-factor sentinel in required window")
        result[month] = {name: value / 100 for name, value in values.items()}
    expected = {f"{year}-{month:02d}" for year in range(2001, 2026) for month in range(1, 13)}
    if set(result) != expected:
        raise ValueError("official factor data does not cover exactly the 300 required months")
    return result


def acquire(output_root):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(output_root) / run_id
    output.mkdir(parents=True, exist_ok=False)
    records, parts = [], {}
    for label, (filename, columns) in SOURCES.items():
        url = BASE + filename
        request = urllib.request.Request(url, headers={"User-Agent": "Rebalance-Lab academic factor-exposure diagnostic"})
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(2 * 1024 * 1024 + 1)
            status = response.status
        if status != 200 or len(body) > 2 * 1024 * 1024:
            raise ValueError("factor acquisition failed")
        with (output / filename).open("xb") as stream:
            stream.write(body)
        parts[label] = parse_zip(body, columns)
        records.append({"label": label, "url": url, "file": filename, "http_status": status,
                        "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                        "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
    rows = [{"month": month, **parts["FF3"][month], **parts["Mom"][month]} for month in sorted(parts["FF3"])]
    with (output / "factors-2001-2025.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["month", "Mkt-RF", "SMB", "HML", "RF", "Mom"])
        writer.writeheader()
        writer.writerows(rows)
    manifest = {"schema_version": 1, "run_id": run_id, "source": "Kenneth French official Data Library",
                "source_definition": "U.S. monthly FF3 and long-short stock Momentum factor",
                "observations": 300, "first_month": rows[0]["month"], "last_month": rows[-1]["month"],
                "normalized_units": "decimal_monthly_returns", "captures": records,
                "normalized_sha256": hashlib.sha256((output / "factors-2001-2025.csv").read_bytes()).hexdigest(),
                "acquisition_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "limitations": ["Retrieved revised history, not a real-time vintage.", "Long-short stock momentum differs from this long-only sector selection score."]}
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True); stream.write("\n")
    return {"factor_dir": str(output), "monthly_rows": 300}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/raw/french-factors")
    print(json.dumps(acquire(parser.parse_args().output_dir)))
