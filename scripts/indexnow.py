#!/usr/bin/env python3
"""Submit all sitemap URLs to IndexNow (Bing, Yandex and partners).

Usage:
  python scripts/indexnow.py --key <INDEXNOW_KEY> [--site-url https://holidaykit.pages.dev]

The key file must already be deployed at https://<host>/<key>.txt
(build with: python scripts/build_site.py --indexnow-key <KEY>).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURL = shutil.which("curl.exe") or shutil.which("curl") or "curl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit sitemap URLs via IndexNow")
    parser.add_argument("--key", required=True)
    parser.add_argument("--site-url", default="https://holidaykit.pages.dev")
    parser.add_argument("--sitemap", default=str(ROOT / "dist" / "sitemap.xml"))
    parser.add_argument("--limit", type=int, default=10000)
    args = parser.parse_args()

    sitemap = Path(args.sitemap)
    if not sitemap.exists():
        print(f"sitemap not found: {sitemap}\nBuild the site first.")
        return 1
    text = sitemap.read_text(encoding="utf-8")
    urls = re.findall(r"<loc>(.*?)</loc>", text)[: args.limit]
    if not urls:
        print("no URLs found in sitemap")
        return 1

    host = args.site_url.replace("https://", "").replace("http://", "").rstrip("/")
    payload = {
        "host": host,
        "key": args.key,
        "keyLocation": f"{args.site_url.rstrip('/')}/{args.key}.txt",
        "urlList": urls,
    }
    payload_path = ROOT / "data" / "indexnow-payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    print(f"submitting {len(urls)} URLs to IndexNow for {host}")
    result = subprocess.run(
        [
            CURL, "-s", "--max-time", "60",            "-X", "POST",
            "-H", "content-type: application/json; charset=utf-8",
            "--data-binary", f"@{payload_path}",
            "-w", "\nstatus=%{http_code}",
            "https://api.indexnow.org/indexnow",
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = (result.stdout or "").strip()
    print(f"IndexNow response: {output}")
    status = "000"
    if "status=" in output:
        status = output.rsplit("status=", 1)[-1].strip()
    payload_path.unlink(missing_ok=True)
    return 0 if status in {"200", "202"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
