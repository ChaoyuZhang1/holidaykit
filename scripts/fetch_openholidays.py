#!/usr/bin/env python3
"""Fetch OpenHolidays public holiday data into data/cache_oh/{CC}/{year}.json.

OpenHolidays covers ~36 countries (mostly Europe) and is used as the second-priority
source, after Nager.Date and before python-holidays.

Usage: python scripts/fetch_openholidays.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cache_oh"
CACHE = ROOT / "data" / "cache"
CURL = shutil.which("curl.exe") or shutil.which("curl") or "curl"
YEARS = [2025, 2026, 2027, 2028]
BASE = "https://openholidaysapi.org"


def curl_json(url: str, out_path: Path) -> bool:
    for attempt in range(3):
        try:
            subprocess.run(
                [CURL, "-s", "--max-time", "30", "-o", str(out_path), url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=40,
                check=False,
            )
        except Exception:
            pass
        if out_path.exists() and out_path.stat().st_size > 2:
            try:
                data = json.loads(out_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return True
            except (OSError, ValueError):
                pass
        time.sleep(0.4 * (attempt + 1))
    return False


def nager_ok(cc: str, year: int) -> bool:
    path = CACHE / cc / f"{year}.json"
    if not path.exists() or path.stat().st_size <= 2:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, list) and len(data) > 0


def main() -> int:
    tmp = ROOT / "data" / "tmp_oh_countries.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if not curl_json(f"{BASE}/Countries?languageIsoCode=EN", tmp):
        print("failed to fetch OpenHolidays country list")
        return 1
    countries = json.loads(tmp.read_text(encoding="utf-8"))
    codes = sorted({str(c.get("isoCode")) for c in countries if c.get("isoCode")})
    print(f"OpenHolidays countries: {len(codes)}")

    filled = 0
    for cc in codes:
        for year in YEARS:
            if nager_ok(cc, year):
                continue
            url = (
                f"{BASE}/PublicHolidays?countryIsoCode={cc}"
                f"&validFrom={year}-01-01&validTo={year}-12-31&languageIsoCode=EN"
            )
            out = OUT / cc / f"{year}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            if not curl_json(url, out):
                continue
            raw = json.loads(out.read_text(encoding="utf-8")) if out.stat().st_size > 2 else []
            rows = []
            for item in raw or []:
                day = str(item.get("startDate") or "")[:10]
                if len(day) != 10:
                    continue
                name = ""
                for entry in item.get("name") or []:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("language", "")).upper() == "EN":
                        name = str(entry.get("text") or "")
                        break
                    if not name:
                        name = str(entry.get("text") or "")
                if not name:
                    continue
                rows.append({
                    "date": day,
                    "name": name,
                    "localName": name,
                    "types": ["Public"],
                    "global": True,
                    "counties": [],
                })
            if rows:
                out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
                filled += 1
            else:
                out.unlink(missing_ok=True)

    tmp.unlink(missing_ok=True)
    print(f"OPENHOLIDAYS_DONE filled={filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
