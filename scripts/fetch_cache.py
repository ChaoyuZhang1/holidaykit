#!/usr/bin/env python3
"""Fetch holiday JSON into data/cache/{CC}/{year}.json using curl.exe + threads.

Windows PowerShell on this machine is 5.1 (no -Parallel), and Python urllib hits TLS
handshake timeouts on this network, so we shell out to curl.exe which is reliable.

Usage: python scripts/fetch_cache.py
"""
from __future__ import annotations

import concurrent.futures
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
CURL = shutil.which("curl.exe") or shutil.which("curl") or "curl"
YEARS = [2025, 2026, 2027, 2028]
URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/{cc}"
WORKERS = 8

COUNTRIES = [
    "US", "CA", "MX", "GB", "IE", "AU", "NZ",
    "DE", "FR", "ES", "IT", "NL", "BE", "AT", "CH", "PT", "LU",
    "SE", "NO", "DK", "FI", "IS",
    "PL", "CZ", "SK", "HU", "RO", "BG", "GR", "HR", "SI", "EE", "LV", "LT",
    "UA", "RS", "MT", "CY",
    "JP", "KR", "CN", "HK", "TW", "SG", "MY", "TH", "VN", "ID", "PH", "IN",
    "PK", "BD", "LK", "MN",
    "BR", "AR", "CL", "CO", "PE", "UY", "CR", "PA", "EC", "VE",
    "ZA", "EG", "NG", "KE", "MA", "TN", "MU",
    "AE", "SA", "IL", "TR", "QA", "KW", "BH", "OM", "JO", "LB",
    "RU", "KZ", "GE", "AM", "AZ", "UZ",
]


def fetch_one(cc: str, year: int) -> str:
    out = CACHE / cc / f"{year}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 2:
        return "cached"
    for attempt in range(4):
        try:
            subprocess.run(
                [CURL, "-s", "--max-time", "30", "-o", str(out), URL.format(year=year, cc=cc)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=40,
                check=False,
            )
        except Exception:
            pass
        if out.exists() and out.stat().st_size > 2:
            return "ok"
        time.sleep(0.3 * (attempt + 1))
    return "fail"


def main() -> int:
    tasks = [(cc, year) for cc in COUNTRIES for year in YEARS]
    results: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for status in pool.map(lambda item: fetch_one(*item), tasks):
            results.append(status)
    ok = sum(1 for r in results if r in ("ok", "cached"))
    fail = [t for t, r in zip(tasks, results) if r == "fail"]
    print(f"FETCH_DONE total={len(tasks)} ok={ok} failed={len(fail)}")
    if fail:
        print("failed sample: " + ", ".join(f"{cc}-{year}" for cc, year in fail[:20]))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
