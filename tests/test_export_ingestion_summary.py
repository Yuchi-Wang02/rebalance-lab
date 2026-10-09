"""Verify public aggregate export without networking or publishing market rows."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


helpers = load_module("ingestion_fixture_helpers", ROOT / "tests" / "test_ingest_diagnostic.py")
exporter = load_module("export_ingestion_summary", ROOT / "scripts" / "export_ingestion_summary.py")


class SummaryExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

        def fetch(url):
            symbol = urlsplit(url).path.rsplit("/", 1)[-1]
            return 200, helpers.encoded(helpers.fixture(symbol))

        with mock.patch.object(helpers.ingest, "fetch_bytes", side_effect=fetch):
            original = self.ingest(["--start", "2024-03-08", "--end", "2024-03-11"])
        with mock.patch.object(helpers.ingest, "fetch_bytes", side_effect=AssertionError("network forbidden")):
            replay = self.ingest(["--raw-dir", original["raw_dir"]])
        self.original = Path(original["processed_dir"])
        self.replay = Path(replay["processed_dir"])

    def ingest(self, extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = helpers.ingest.main(["--data-dir", str(self.folder), *extra])
        self.assertEqual(code, 0)
        return json.loads(output.getvalue())

    @staticmethod
    def read(path):
        return json.loads(path.read_text())

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def alter_both_quality_reports(self, edit):
        """Model identical future private diagnostic fields, with valid hashes."""
        for directory in (self.original, self.replay):
            path = directory / "quality_report.json"
            quality = self.read(path)
            edit(quality)
            self.write(path, quality)
            manifest_path = directory / "manifest.json"
            manifest = self.read(manifest_path)
            manifest["derived_file_sha256"]["quality_report.json"] = exporter.sha256(path)
            self.write(manifest_path, manifest)

    def test_valid_export_reports_aggregates_without_promoting_research_readiness(self):
        summary = exporter.export_summary(self.original, self.replay)
        self.assertTrue(summary["diagnostic_passed"])
        self.assertTrue(summary["cache_replay_verified"])
        self.assertFalse(summary["research_ready"])
        self.assertEqual(summary["calendar_coverage"], "not_verified")
        self.assertEqual(summary["price_adjustment_semantics"], "not_verified")
        self.assertEqual(summary["requested_start"], "2024-03-08")
        self.assertEqual(summary["requested_end"], "2024-03-11")
        self.assertEqual([s["symbol"] for s in summary["symbols"]], ["SPMO", "SPY"])
        for symbol in summary["symbols"]:
            self.assertEqual(symbol["rows"], 2)
            self.assertEqual(symbol["complete_ohlc_rows"], 2)
            self.assertEqual(symbol["missing_ohlc_rows"] + symbol["invalid_ohlc_rows"], 0)
        manifest = self.read(self.original / "manifest.json")
        self.assertEqual(summary["source_script_sha256"], manifest["script_sha256"])
        self.assertEqual(summary["source_run_id"], manifest["run_id"])

    def test_source_and_replay_derived_corruption_are_rejected(self):
        for directory in (self.original, self.replay):
            for name in ("quality_report.json", "SPMO.csv", "SPY.events.json"):
                with self.subTest(directory=directory.name, name=name):
                    path = directory / name
                    original_bytes = path.read_bytes()
                    path.write_bytes(original_bytes + b" ")
                    try:
                        with self.assertRaises(ValueError):
                            exporter.export_summary(self.original, self.replay)
                    finally:
                        path.write_bytes(original_bytes)

    def test_wrong_replay_identity_request_or_capture_is_rejected(self):
        path = self.replay / "manifest.json"
        original_bytes = path.read_bytes()
        mutations = [
            lambda m: m.update(mode="live"),
            lambda m: m.update(provider="other_provider"),
            lambda m: m.update(source_raw_manifest_sha256="0" * 64),
            lambda m: m.update(script_sha256="1" * 64),
            lambda m: m["request"].update(start="2024-03-07"),
            lambda m: m["captures"][0].update(sha256="2" * 64),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                manifest = json.loads(original_bytes)
                mutate(manifest)
                self.write(path, manifest)
                with self.assertRaises(ValueError):
                    exporter.export_summary(self.original, self.replay)
                path.write_bytes(original_bytes)

    def test_public_whitelist_omits_price_action_and_private_diagnostic_fields(self):
        def add_private_fields(quality):
            quality["private_price_rows"] = [{"close": 999.123456, "secret_note": "DO_NOT_PUBLISH"}]
            quality["private_events"] = [{"amount": 987.654321, "pay_date": "private"}]
            quality["symbols"][0]["vendor_rows"] = [{"open": 999.123456}]
            quality["symbols"][0]["vendor_events"] = {"dividend": "DO_NOT_PUBLISH"}

        self.alter_both_quality_reports(add_private_fields)
        summary = exporter.export_summary(self.original, self.replay)
        serialized = json.dumps(summary)
        for private in ("DO_NOT_PUBLISH", "999.123456", "987.654321", "private_price_rows", "vendor_events"):
            self.assertNotIn(private, serialized)
        self.assertEqual(set(summary), {
            "schema_version", "generated_at_utc", "source_run_id", "replay_run_id", "source_script_sha256",
            "quality_report_sha256", "requested_start", "requested_end", "diagnostic_passed", "research_ready",
            "calendar_coverage", "price_adjustment_semantics", "cache_replay_verified", "symbols",
            "cross_symbol_dates_agree", "global_error_count", "warnings",
        })
        for symbol in summary["symbols"]:
            self.assertEqual(set(symbol), {"symbol", "observed_start", "observed_end", "rows", "complete_ohlc_rows",
                                          "missing_ohlc_rows", "invalid_ohlc_rows", "error_count", "warning_count",
                                          "raw_sha256", "retrieved_at_utc"})

    def test_freeform_or_nested_public_warnings_cannot_leak_private_data(self):
        for warning in ({"private_price": 999.123456}, "private_price=999.123456"):
            with self.subTest(warning=warning):
                self.alter_both_quality_reports(lambda quality: quality.update(warnings=[warning]))
                with self.assertRaises(ValueError):
                    exporter.export_summary(self.original, self.replay)

    def test_failed_cli_export_preserves_existing_public_summary(self):
        output = self.folder / "public.json"
        previous = b'{"previous_valid_summary":true}\n'
        output.write_bytes(previous)
        (self.replay / "SPMO.csv").write_bytes(b"corrupt")
        arguments = ["export_ingestion_summary.py", "--processed-dir", str(self.original),
                     "--replay-dir", str(self.replay), "--output", str(output)]
        with mock.patch("sys.argv", arguments), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(exporter.main(), 1)
        self.assertEqual(output.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
