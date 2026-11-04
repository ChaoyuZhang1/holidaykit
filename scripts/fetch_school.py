#!/usr/bin/env python3
"""Fetch school holidays from OpenHolidays and assemble data/school.json.

Output structure:
{
  "meta": {"generatedAt": ..., "countries": 30},
  "countryNames": {"DE": "Germany", ...},
  "countries": {
    "DE": {"2026": [{"name": "Christmas Holidays", "start": "2025-12-17",
                     "end": "2026-01-02", "days": 17, "region": "HH"}, ...]},
    ...
  }
}

Usage: python scripts/fetch_school.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "school_raw"
OUT = ROOT / "data" / "school.json"
CURL = shutil.which("curl.exe") or shutil.which("curl") or "curl"
YEARS = [2025, 2026, 2027, 2028]
BASE = "https://openholidaysapi.org"


def curl_json(url: str, out_path: Path) -> bool:
    for attempt in range(3):
        try:
            subprocess.run(
                [CURL, "-s", "--max-time", "40", "-o", str(out_path), url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=50,
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
        time.sleep(0.5 * (attempt + 1))
    return False


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "data" / "tmp_oh_countries.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if not curl_json(f"{BASE}/Countries?languageIsoCode=EN", tmp):
        print("failed to fetch OpenHolidays country list")
        return 1
    country_list = json.loads(tmp.read_text(encoding="utf-8"))
    country_names = {}
    for item in country_list:
        code = str(item.get("isoCode") or "").upper()
        if not code:
            continue
        name = ""
        for entry in item.get("name") or []:
            if isinstance(entry, dict) and str(entry.get("language", "")).upper() == "EN":
                name = str(entry.get("text") or "")
                break
        country_names[code] = name or code
    codes = sorted(country_names)

    assembled: dict[str, dict] = {}
    total_ranges = 0
    for cc in codes:
        years: dict[str, list] = {}
        for year in YEARS:
            url = (
                f"{BASE}/SchoolHolidays?countryIsoCode={cc}"
                f"&validFrom={year}-01-01&validTo={year}-12-31&languageIsoCode=EN"
            )
            out = RAW / cc / f"{year}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            if not curl_json(url, out):
                continue
            try:
                raw = json.loads(out.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            ranges = []
            seen = set()
            for item in raw or []:
                start = str(item.get("startDate") or "")[:10]
                end = str(item.get("endDate") or "")[:10]
                if len(start) != 10 or len(end) != 10:
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
                name = name or "School holiday"
                regions = item.get("subdivisions") or []
                region = ", ".join(str(r.get("shortName") or r.get("code") or "") for r in regions) or "Nationwide"
                try:
                    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
                except ValueError:
                    continue
                key = (start, end, name, region)
                if key in seen:
                    continue
                seen.add(key)
                ranges.append({
                    "name": name,
                    "start": start,
                    "end": end,
                    "days": days,
                    "region": region,
                })
            if ranges:
                ranges.sort(key=lambda r: (r["start"], r["region"]))
                years[str(year)] = ranges
                total_ranges += len(ranges)
        if years:
            assembled[cc] = years

    tmp.unlink(missing_ok=True)
    payload = {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "OpenHolidays API",
            "countries": len(assembled),
            "ranges": total_ranges,
        },
        "countryNames": country_names,
        "countries": assembled,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SCHOOL_DONE countries={len(assembled)} ranges={total_ranges} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
