"""Offline guarantees for immutable bulk price capture; no market requests."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import stock_pilot_prices as prices
from scripts.ingest_diagnostic import DiagnosticError, NY


def payload(symbol="AAPL"):
    dates = [int(datetime.fromisoformat(d).replace(hour=9, minute=30, tzinfo=NY).timestamp())
             for d in ("2024-03-08", "2024-03-11")]
    return json.dumps({"chart": {"error": None, "result": [{
        "meta": {"symbol": symbol, "currency": "USD", "exchangeTimezoneName": "America/New_York",
                 "dataGranularity": "1d", "exchangeName": "NMS"},
        "timestamp": dates,
        "indicators": {"quote": [{"open": [100, 110], "high": [102, 112], "low": [99, 109],
                                   "close": [101, 111], "volume": [1000, 1200]}],
                       "adjclose": [{"adjclose": [100.5, 110.5]}]}, "events": {},
    }]}}).encode()


class StockPilotPriceTests(unittest.TestCase):
    def acquire(self, folder, symbols=None):
        return prices.acquire_prices(symbols or ["AAPL"], "2024-03-08", "2024-03-11", folder,
                                     reuse_private_probes=False)

    def test_exact_bytes_and_original_manifest_survive_network_free_resume(self):
        body = payload()
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(prices, "fetch_bytes", return_value=(200, body)) as fetch:
                first, manifest = self.acquire(folder)
                self.assertTrue(manifest["all_symbols_passed"])
                fetch.assert_called_once()
            original = first.read_bytes()
            self.assertEqual((Path(folder) / "AAPL.json").read_bytes(), body)
            with mock.patch.object(prices, "fetch_bytes", side_effect=AssertionError("unexpected network")):
                second, resumed = self.acquire(folder)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(resumed["captures"][0]["acquisition"], "reused_verified_output")

    def test_hash_tampering_blocks_resume_without_redownload_or_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(prices, "fetch_bytes", return_value=(200, payload())):
                self.acquire(folder)
            path = Path(folder) / "AAPL.json"
            path.chmod(0o644)
            path.write_bytes(b"tampered")
            with mock.patch.object(prices, "fetch_bytes", side_effect=AssertionError("unexpected network")):
                _, result = self.acquire(folder)
            self.assertFalse(result["all_symbols_passed"])
            self.assertEqual(result["captures"][0]["error"], "reuse_capture_hash_or_size_mismatch")
            self.assertEqual(path.read_bytes(), b"tampered")

    def test_404_is_explicit_and_never_automatically_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(prices, "fetch_bytes", side_effect=DiagnosticError("http_status_404")) as fetch:
                _, result = self.acquire(folder)
                _, resumed = self.acquire(folder)
                fetch.assert_called_once()
            item = result["captures"][0]
            self.assertEqual(item["http_status"], 404)
            self.assertEqual(item["automatic_retries"], 0)
            self.assertFalse(result["all_symbols_passed"])
            self.assertEqual(resumed["captures"][0]["acquisition"], "reused_recorded_failure")
            self.assertFalse((Path(folder) / "AAPL.json").exists())

    def test_partial_success_retains_supplied_order_and_every_failure(self):
        def fetch(url):
            if "/GOOG?" in url:
                raise DiagnosticError("http_status_404")
            return 200, payload("AAPL")
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(prices, "fetch_bytes", side_effect=fetch), \
                    mock.patch.object(prices.StartThrottle, "wait"):
                _, result = self.acquire(folder, ["GOOG", "AAPL"])
            self.assertEqual([c["symbol"] for c in result["captures"]], ["GOOG", "AAPL"])
            self.assertEqual(result["passed_symbol_count"], 1)
            self.assertEqual(result["failed_symbol_count"], 1)
            self.assertEqual(result["workers"], 3)

    def test_wrong_symbol_payload_remains_immutable_failed_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(prices, "fetch_bytes", return_value=(200, payload("GOOG"))):
                _, result = self.acquire(folder)
            self.assertFalse(result["all_symbols_passed"])
            self.assertEqual(result["captures"][0]["audit"]["errors"], ["metadata_mismatch_symbol"])
            self.assertTrue((Path(folder) / "AAPL.json").exists())

    def test_invalid_universes_fail_before_any_request(self):
        for symbols in ([], ["AAPL", "AAPL"], ["../AAPL"], [None], [{"ticker": "AAPL"}]):
            with self.subTest(symbols=symbols), mock.patch.object(prices, "fetch_bytes") as fetch:
                with self.assertRaises(DiagnosticError):
                    prices.validate_symbols(symbols, "2024-03-08", "2024-03-11")
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
