#!/usr/bin/env python3
"""Fill missing country-year data with the `holidays` Python library.

For every country/year where data/cache/{CC}/{year}.json is absent or empty,
generate rows from python-holidays and write data/cache_lib/{CC}/{year}.json.

Usage:
  python -m pip install holidays
  python scripts/fetch_lib.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUT = ROOT / "data" / "cache_lib"
YEARS = [2025, 2026, 2027, 2028]

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
    try:
        import holidays as holidays_lib
    except ImportError:
        print("python-holidays not installed. Run: python -m pip install holidays")
        return 1

    supported = holidays_lib.list_supported_countries()
    filled = 0
    skipped = 0
    unsupported: list[str] = []
    failures: list[str] = []

    for cc in COUNTRIES:
        if cc not in supported:
            unsupported.append(cc)
            continue
        for year in YEARS:
            if nager_ok(cc, year):
                skipped += 1
                continue
            try:
                cal = holidays_lib.country_holidays(cc, years=[year], language="en_US")
                rows = []
                for day, name in sorted(cal.items()):
                    rows.append({
                        "date": day.isoformat(),
                        "name": str(name).strip(),
                        "localName": str(name).strip(),
                        "types": ["Public"],
                        "global": True,
                        "counties": [],
                    })
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{cc}-{year}: {exc}")
                continue
            if not rows:
                failures.append(f"{cc}-{year}: empty")
                continue
            out_dir = OUT / cc
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{year}.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            filled += 1

    print(f"LIB_DONE filled={filled} skipped(Nager ok)={skipped} unsupported={len(unsupported)}")
    if unsupported:
        print("unsupported:", ", ".join(unsupported))
    if failures:
        print(f"failures ({len(failures)}): " + "; ".join(failures[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
