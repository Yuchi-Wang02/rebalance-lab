#!/usr/bin/env python3
"""Probe public documentation without credentials; not a market-data connector."""

import argparse
import concurrent.futures
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def probe(url, timeout):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query:
        return {"url": url.split("?", 1)[0], "status": "refused_nonpublic_documentation_url"}
    request = urllib.request.Request(url, headers={"User-Agent": "SPMO-Fast-Lab-documentation-check/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            response.read(4096)
            return {"url": url, "status": "reachable_not_data_validated", "http_status": response.status}
    except urllib.error.HTTPError as error:
        return {"url": url, "status": "http_error", "http_status": error.code}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = str(getattr(error, "reason", error))
        category = "proxy_connect_denied" if "Tunnel connection failed: 403" in reason else "transport_or_tls_error"
        return {"url": url, "status": category, "error_type": type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-unverified", action="store_true", help="Also probe product references whose contracts have not been read.")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if args.timeout <= 0 or args.timeout > 30:
        parser.error("--timeout must be greater than 0 and at most 30 seconds")
    catalog = json.loads((ROOT / "configs/data-sources.json").read_text())
    urls = set()
    for route in catalog["routes"]:
        urls.update(route["documentation_sources"])
        if args.include_unverified:
            urls.update(route.get("unread_product_references", []))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda url: probe(url, args.timeout), sorted(urls)))
    print(json.dumps({"scope": "credential_free_documentation_only", "market_data_downloaded": False, "results": results}, indent=2))
    return 0 if all(result["status"] == "reachable_not_data_validated" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
