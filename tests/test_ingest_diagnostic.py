"""Offline fixtures for diagnostic capture, validation and replay guarantees."""

import contextlib
import csv
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ingest_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("ingest_diagnostic", SCRIPT)
ingest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingest)


def stamp(day, hour=9, minute=30):
    return int(datetime.fromisoformat(day).replace(hour=hour, minute=minute, tzinfo=ingest.NY).timestamp())


def fixture(symbol="SPMO"):
    dates = [stamp("2024-03-08"), stamp("2024-03-11")]
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": symbol, "currency": "USD", "exchangeTimezoneName": "America/New_York",
                 "dataGranularity": "1d", "exchangeName": "PCX"},
        "timestamp": dates,
        "indicators": {"quote": [{"open": [100, 110], "high": [102, 112], "low": [99, 109],
                                   "close": [101, 111], "volume": [1000, 1200]}],
                       "adjclose": [{"adjclose": [100.5, 110.5]}]},
        "events": {"dividends": {str(dates[0]): {"date": dates[0], "amount": 0.25}},
                   "splits": {str(dates[1]): {"date": dates[1], "numerator": 2, "denominator": 1, "splitRatio": "2:1"}}},
    }]}}


def encoded(payload):
    return json.dumps(payload).encode()


def inspect(payload):
    return ingest.inspect_payload(encoded(payload), "SPMO", ingest.request_spec(["SPMO"], "2024-03-08", "2024-03-11"))


class DiagnosticTests(unittest.TestCase):
    def test_valid_payload_keeps_prices_actions_and_readiness_separate(self):
        report, rows, event_rows, events = inspect(fixture())
        self.assertTrue(report["diagnostic_passed"])
        self.assertFalse(report["research_ready"])
        self.assertEqual(rows[0]["close"], 101)
        self.assertEqual(rows[0]["adjclose"], 100.5)
        self.assertEqual(report["actual_date_bounds"], {"first": "2024-03-08", "last": "2024-03-11"})
        self.assertTrue(all(n == 0 for n in report["per_field_missingness"].values()))
        self.assertEqual(report["complete_ohlc_rows"], 2)
        self.assertEqual(report["incomplete_ohlc_rows"], 0)
        self.assertEqual(report["event_counts"], {"dividends": 1, "splits": 1})
        self.assertEqual(events, fixture()["chart"]["result"][0]["events"])
        self.assertNotIn("pay_date", event_rows[0])
        self.assertIn("exchange_calendar_coverage_unverified", report["warnings"])

    def test_null_ohlc_is_retained_and_is_an_error(self):
        payload = fixture()
        payload["chart"]["result"][0]["indicators"]["quote"][0]["high"][0] = None
        report, rows, _, _ = inspect(payload)
        self.assertFalse(report["diagnostic_passed"])
        self.assertEqual(report["per_field_missingness"]["high"], 1)
        self.assertEqual(report["missing_ohlc_rows"], 1)
        self.assertEqual(report["invalid_ohlc_rows"], 0)
        self.assertEqual(report["complete_ohlc_rows"] + report["incomplete_ohlc_rows"], 2)
        self.assertIsNone(rows[0]["high"])
        self.assertEqual(len(rows), 2)

    def test_array_length_mismatch_does_not_zip_away_rows(self):
        payload = fixture()
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"].pop()
        report, rows, _, _ = inspect(payload)
        self.assertIn("array_length_mismatch_close", report["errors"])
        self.assertEqual(report["row_count"], 2)
        self.assertIsNone(report["complete_ohlc_rows"])
        self.assertEqual(rows, [])
        self.assertFalse(report["events_extracted"])

    def test_duplicate_nonmonotonic_and_duplicate_session_dates_fail(self):
        for dates in ([stamp("2024-03-08")] * 2,
                      [stamp("2024-03-11"), stamp("2024-03-08")],
                      [stamp("2024-03-08"), stamp("2024-03-08", 10)]):
            with self.subTest(dates=dates):
                payload = fixture()
                payload["chart"]["result"][0]["timestamp"] = dates
                report, rows, _, _ = inspect(payload)
                self.assertFalse(report["diagnostic_passed"])
                self.assertTrue(any("session_date" in e for e in report["errors"]))
                self.assertEqual([r["vendor_timestamp"] for r in rows], dates)

    def test_outside_cutoff_is_preserved_but_rejected(self):
        payload = fixture()
        payload["chart"]["result"][0]["timestamp"][1] = stamp("2024-03-12")
        report, rows, _, _ = inspect(payload)
        self.assertIn("row_1:outside_requested_dates", report["errors"])
        self.assertEqual(rows[1]["session_date"], "2024-03-12")

    def test_symbol_currency_timezone_and_interval_are_checked(self):
        for field, value in [("symbol", "QQQ"), ("currency", "EUR"),
                             ("exchangeTimezoneName", "UTC"), ("dataGranularity", "1h")]:
            with self.subTest(field=field):
                payload = fixture()
                payload["chart"]["result"][0]["meta"][field] = value
                report, _, _, _ = inspect(payload)
                self.assertIn("metadata_mismatch_" + field, report["errors"])

    def test_bad_numeric_values_and_price_bounds_fail(self):
        for field, value in [("open", -1), ("close", True), ("volume", -5), ("low", 103), ("open", 10**400)]:
            with self.subTest(field=field):
                payload = fixture()
                payload["chart"]["result"][0]["indicators"]["quote"][0][field][0] = value
                self.assertFalse(inspect(payload)[0]["diagnostic_passed"])
        body = encoded(fixture()).replace(b'"open": [100,', b'"open": [1e999,')
        report, _, _, _ = ingest.inspect_payload(body, "SPMO", ingest.request_spec(["SPMO"], "2024-03-08", "2024-03-11"))
        self.assertIn("row_0:missing_or_invalid_open", report["errors"])
        self.assertEqual(report["invalid_ohlc_rows"], 1)
        self.assertEqual(report["missing_ohlc_rows"], 0)

    def test_chart_json_and_event_errors_fail_without_vendor_messages(self):
        payload = fixture()
        payload["chart"]["error"] = {"code": "NoData", "description": "private-server-details"}
        report, _, _, _ = inspect(payload)
        self.assertEqual(report["errors"], ["chart_error"])
        self.assertNotIn("private-server-details", json.dumps(report))
        report, _, _, _ = ingest.inspect_payload(b"not JSON", "SPMO", {})
        self.assertEqual(report["errors"], ["invalid_json"])
        payload = fixture()
        event = next(iter(payload["chart"]["result"][0]["events"]["splits"].values()))
        event["denominator"] = 0
        self.assertIn("invalid_split_ratio", inspect(payload)[0]["errors"])

    def test_request_end_is_exclusive_at_new_york_midnight_across_dst(self):
        spec = ingest.request_spec(["SPMO"], "2024-03-08", "2024-03-11")
        parsed = urlsplit(ingest.request_url("SPMO", spec))
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "query1.finance.yahoo.com")
        self.assertEqual(query["period1"], [str(stamp("2024-03-08", 0, 0))])
        self.assertEqual(query["period2"], [str(stamp("2024-03-12", 0, 0))])
        self.assertEqual(int(query["period2"][0]) - int(query["period1"][0]), 4 * 86400 - 3600)
        self.assertEqual(query["events"], ["div,splits"])

    def invoke(self, folder, extra=(), fetch=None):
        output = io.StringIO()
        args = ["--data-dir", str(folder), *extra]
        with mock.patch.object(ingest, "fetch_bytes", side_effect=fetch or AssertionError("network forbidden")) as mocked:
            with contextlib.redirect_stdout(output):
                code = ingest.main(args)
        return code, json.loads(output.getvalue()), mocked

    @staticmethod
    def fake_fetch(url):
        symbol = urlsplit(url).path.rsplit("/", 1)[-1]
        return 200, encoded(fixture(symbol))

    def test_capture_and_offline_replay_have_reproducible_derived_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            code, result, network = self.invoke(folder, ["--start", "2024-03-08", "--end", "2024-03-11"], self.fake_fetch)
            self.assertEqual(code, 0)
            self.assertEqual(network.call_count, 2)
            first_raw, first_processed = Path(result["raw_dir"]), Path(result["processed_dir"])
            original_manifest = json.loads((first_raw / "manifest.json").read_text())
            self.assertEqual(original_manifest["script_sha256"], ingest.digest(SCRIPT.read_bytes()))
            code, replay, network = self.invoke(folder, ["--raw-dir", str(first_raw)])
            self.assertEqual(code, 0)
            network.assert_not_called()
            second_processed = Path(replay["processed_dir"])
            for name in ["SPMO.csv", "SPY.csv", "SPMO.events.json", "SPMO.events.csv", "quality_report.json"]:
                self.assertEqual((first_processed / name).read_bytes(), (second_processed / name).read_bytes())
            quality = json.loads((second_processed / "quality_report.json").read_text())
            self.assertFalse(quality["research_ready"])
            self.assertTrue(quality["symbol_session_agreement"])
            self.assertEqual(quality["exchange_calendar_coverage"], "unverified")
            self.assertFalse(quality["session_agreement_is_exchange_calendar_proof"])

    def test_partial_bar_warning_uses_capture_new_york_date_across_later_replay(self):
        class Clock(datetime):
            # UTC is March 12, but the capture's New York date is March 11.
            current = datetime.fromisoformat("2024-03-12T00:30:00+00:00")

            @classmethod
            def now(cls, tz=None):
                return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

        warning = "request_includes_current_or_future_date_possible_partial_bars"
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(ingest, "datetime", Clock):
            folder = Path(temporary)
            code, original, _ = self.invoke(folder, ["--start", "2024-03-08", "--end", "2024-03-11"], self.fake_fetch)
            self.assertEqual(code, 0)
            first_quality = (Path(original["processed_dir"]) / "quality_report.json").read_bytes()
            self.assertEqual(json.loads(first_quality)["warnings"].count(warning), 1)

            Clock.current = datetime.fromisoformat("2024-03-13T16:00:00+00:00")
            code, replay, network = self.invoke(folder, ["--raw-dir", original["raw_dir"]])
            self.assertEqual(code, 0)
            network.assert_not_called()
            self.assertEqual(first_quality, (Path(replay["processed_dir"]) / "quality_report.json").read_bytes())
            original_manifest = json.loads((Path(original["processed_dir"]) / "manifest.json").read_text())
            replay_manifest = json.loads((Path(replay["processed_dir"]) / "manifest.json").read_text())
            self.assertEqual(original_manifest["derived_file_sha256"], replay_manifest["derived_file_sha256"])

            # A genuinely later capture has different context, unlike a replay.
            code, later, _ = self.invoke(folder, ["--start", "2024-03-08", "--end", "2024-03-11"], self.fake_fetch)
            self.assertEqual(code, 0)
            later_quality = json.loads((Path(later["processed_dir"]) / "quality_report.json").read_text())
            self.assertNotIn(warning, later_quality["warnings"])

    def test_partial_bar_warning_applies_if_any_capture_precedes_new_york_midnight(self):
        class Clock(datetime):
            current = datetime.fromisoformat("2024-03-12T03:59:00+00:00")

            @classmethod
            def now(cls, tz=None):
                return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

        def fetch_across_midnight(url):
            if urlsplit(url).path.endswith("/SPY"):
                Clock.current = datetime.fromisoformat("2024-03-12T04:01:00+00:00")
            return self.fake_fetch(url)

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(ingest, "datetime", Clock):
            code, result, _ = self.invoke(Path(temporary), ["--start", "2024-03-08", "--end", "2024-03-11"], fetch_across_midnight)
            self.assertEqual(code, 0)
            quality = json.loads((Path(result["processed_dir"]) / "quality_report.json").read_text())
            self.assertEqual(quality["warnings"].count("request_includes_current_or_future_date_possible_partial_bars"), 1)

    def test_replay_rejects_missing_malformed_or_naive_retrieval_timestamps(self):
        for retrieved_at in (None, "not-a-date", "2024-03-12T00:30:00"):
            with self.subTest(retrieved_at=retrieved_at), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                code, original, _ = self.invoke(folder, ["--start", "2024-03-08", "--end", "2024-03-11"], self.fake_fetch)
                self.assertEqual(code, 0)
                source_path = Path(original["raw_dir"]) / "manifest.json"
                source = json.loads(source_path.read_text())
                source["captures"][0]["retrieved_at"] = retrieved_at
                source_path.chmod(0o644)
                source_path.write_text(json.dumps(source))
                code, result, network = self.invoke(folder, ["--raw-dir", original["raw_dir"]])
                self.assertEqual(code, 1)
                network.assert_not_called()
                manifest = json.loads((Path(result["raw_dir"]) / "manifest.json").read_text())
                self.assertIn({"code": "invalid_retrieval_timestamp"}, manifest["failures"])
                self.assertEqual(manifest["captures"], [])

    def test_missing_values_are_blank_in_csv_and_raw_corruption_blocks_replay(self):
        def missing_fetch(url):
            value = fixture(urlsplit(url).path.rsplit("/", 1)[-1])
            value["chart"]["result"][0]["indicators"]["quote"][0]["close"][0] = None
            return 200, encoded(value)

        with tempfile.TemporaryDirectory() as temporary:
            code, result, _ = self.invoke(Path(temporary), ["--start", "2024-03-08", "--end", "2024-03-11"], missing_fetch)
            self.assertEqual(code, 1)
            raw, processed = Path(result["raw_dir"]), Path(result["processed_dir"])
            with (processed / "SPMO.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["close"], "")
            file = raw / "SPMO.json"
            file.chmod(0o644)
            file.write_bytes(file.read_bytes() + b" ")
            code, replay, network = self.invoke(Path(temporary), ["--raw-dir", str(raw)])
            self.assertEqual(code, 1)
            network.assert_not_called()
            manifest = json.loads((Path(replay["raw_dir"]) / "manifest.json").read_text())
            self.assertIn({"code": "replay_raw_hash_or_size_mismatch"}, manifest["failures"])
            self.assertEqual(manifest["captures"], [])

    def test_unsafe_symbols_and_transport_failures_leave_safe_failure_manifests(self):
        for symbols in (["SPMO", "SPMO"], ["../SPMO"]):
            with self.subTest(symbols=symbols), tempfile.TemporaryDirectory() as temporary:
                code, result, network = self.invoke(Path(temporary), ["--symbols", *symbols])
                self.assertEqual(code, 1)
                network.assert_not_called()
                self.assertTrue((Path(result["raw_dir"]) / "manifest.json").exists())
        with mock.patch.object(ingest.urllib.request, "urlopen", side_effect=urllib.error.URLError("secret-proxy-details")):
            with self.assertRaisesRegex(ingest.DiagnosticError, "^transport_failure$"):
                ingest.fetch_bytes("https://query1.finance.yahoo.com/test")
        with tempfile.TemporaryDirectory() as temporary:
            code, result, _ = self.invoke(Path(temporary), fetch=ingest.DiagnosticError("transport_failure"))
            self.assertEqual(code, 1)
            manifest = json.loads((Path(result["raw_dir"]) / "manifest.json").read_text())
            self.assertEqual(len(manifest["failures"]), 2)
            self.assertFalse(manifest["research_ready"])

    def test_malformed_replay_manifests_fail_with_structured_failure_records(self):
        valid_request = ingest.request_spec(["SPMO"], "2024-03-08", "2024-03-11")
        for source in ([], None, {"schema_version": 1, "provider": "yahoo_chart", "request": valid_request, "captures": [None]}):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                cached = folder / "old"
                cached.mkdir()
                (cached / "manifest.json").write_text(json.dumps(source))
                code, result, network = self.invoke(folder, ["--raw-dir", str(cached)])
                self.assertEqual(code, 1)
                network.assert_not_called()
                manifest = json.loads((Path(result["raw_dir"]) / "manifest.json").read_text())
                self.assertTrue(manifest["failures"])
                self.assertFalse(manifest["diagnostic_passed"])


if __name__ == "__main__":
    unittest.main()
