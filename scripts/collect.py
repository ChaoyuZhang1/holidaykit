#!/usr/bin/env python3
"""HolidayKit collector — 采集各国公共假期，标准化写入 data/holidays.json。

数据源
- Nager.Date  https://date.nager.at/api/v3  （公共假期，MIT）
- OpenHolidays https://openholidaysapi.org   （学校假期，可选，--with-school）

每次采集会同时写一份快照到 data/snapshots/，供 scripts/audit.py 做 diff。

用法
  python scripts/collect.py
  python scripts/collect.py --countries US,GB,DE,FR,JP --years 2025,2026,2027
  python scripts/collect.py --with-school --no-snapshot
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 覆盖 90 个国家/地区（Nager.Date 支持的范围；个别国家失败会记录在 meta.failed）
DEFAULT_COUNTRIES = [
    # 北美 / 大洋洲 / 欧洲英语区
    "US", "CA", "MX", "GB", "IE", "AU", "NZ",
    # 西欧 / 北欧
    "DE", "FR", "ES", "IT", "NL", "BE", "AT", "CH", "PT", "LU",
    "SE", "NO", "DK", "FI", "IS",
    # 中东欧
    "PL", "CZ", "SK", "HU", "RO", "BG", "GR", "HR", "SI", "EE", "LV", "LT",
    "UA", "RS", "MT", "CY",
    # 东亚 / 东南亚 / 南亚
    "JP", "KR", "CN", "HK", "TW", "SG", "MY", "TH", "VN", "ID", "PH", "IN",
    "PK", "BD", "LK", "MN",
    # 拉美
    "BR", "AR", "CL", "CO", "PE", "UY", "CR", "PA", "EC", "VE",
    # 非洲 / 中东
    "ZA", "EG", "NG", "KE", "MA", "TN", "MU",
    "AE", "SA", "IL", "TR", "QA", "KW", "BH", "OM", "JO", "LB",
    # 欧亚
    "RU", "KZ", "GE", "AM", "AZ", "UZ",
]
DEFAULT_YEARS = [2025, 2026, 2027, 2028]

NAGER_BASE = "https://date.nager.at/api/v3"
OPENHOLIDAYS_BASE = "https://openholidaysapi.org"
UA = "HolidayKit/0.2 (holiday data collector)"


def http_json(url: str, *, retries: int = 3, timeout: int = 20):
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": UA, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(1.2 * (attempt + 1))
    print(f"  ! fetch failed: {url} ({last_exc})", file=sys.stderr)
    return None


def fetch_nager(cc: str, year: int):
    return http_json(f"{NAGER_BASE}/PublicHolidays/{year}/{cc}")


def normalize_nager(cc: str, year: int, raw) -> list[dict]:
    out: list[dict] = []
    for item in raw or []:
        day = str(item.get("date") or "")[:10]
        name = str(item.get("name") or item.get("localName") or "").strip()
        if len(day) != 10 or not name:
            continue
        out.append({
            "country": cc,
            "date": day,
            "name": name,
            "localName": str(item.get("localName") or name),
            "types": [str(t) for t in (item.get("types") or [])],
            "global": bool(item.get("global")),
            "counties": [str(c) for c in (item.get("counties") or [])],
            "year": year,
            "source": "nager.date",
        })
    return out


def fetch_school(cc: str, year: int, lang: str = "EN"):
    url = (
        f"{OPENHOLIDAYS_BASE}/SchoolHolidays?countryIsoCode={cc}"
        f"&validFrom={year}-01-01&validTo={year}-12-31&languageIsoCode={lang}"
    )
    return http_json(url, retries=2)


def normalize_school(cc: str, year: int, raw) -> list[dict]:
    out: list[dict] = []
    for item in raw or []:
        start = str(item.get("startDate") or "")[:10]
        end = str(item.get("endDate") or "")[:10]
        if len(start) != 10:
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
        out.append({
            "country": cc,
            "date": start,
            "endDate": end if len(end) == 10 else start,
            "name": name or "School holiday",
            "localName": name or "School holiday",
            "types": ["School"],
            "global": True,
            "counties": [],
            "year": year,
            "source": "openholidays.api",
        })
    return out


def dedupe(rows: list[dict]) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for row in rows:
        key = (
            row["country"],
            row["date"],
            row.get("endDate", ""),
            row["name"],
            tuple(sorted(row["types"])),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public holidays into data/holidays.json")
    parser.add_argument("--countries", default=",".join(DEFAULT_COUNTRIES))
    parser.add_argument("--years", default=",".join(str(y) for y in DEFAULT_YEARS))
    parser.add_argument("--out", default=str(ROOT / "data" / "holidays.json"))
    parser.add_argument("--snapshot-dir", default=str(ROOT / "data" / "snapshots"))
    parser.add_argument("--no-snapshot", action="store_true", help="不写 data/snapshots 快照")
    parser.add_argument("--sleep", type=float, default=0.15, help="请求间隔（秒），默认 0.15")
    parser.add_argument("--with-school", action="store_true", help="额外采集 OpenHolidays 学校假期")
    args = parser.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    years = [int(y) for y in args.years.split(",") if y.strip()]

    rows: list[dict] = []
    failed: list[str] = []
    for cc in countries:
        for year in years:
            raw = fetch_nager(cc, year)
            if raw is None:
                failed.append(f"{cc}-{year}")
                continue
            part = normalize_nager(cc, year, raw)
            rows.extend(part)
            print(f"  {cc} {year}: {len(part)} holidays")
            if args.with_school:
                school = fetch_school(cc, year)
                if school:
                    part_s = normalize_school(cc, year, school)
                    rows.extend(part_s)
                    print(f"  {cc} {year}: {len(part_s)} school ranges")
            if args.sleep > 0:
                time.sleep(args.sleep)

    rows = dedupe(rows)
    rows.sort(key=lambda r: (r["country"], r["date"], r["name"]))

    generated = datetime.now(timezone.utc)
    payload = {
        "meta": {
            "generatedAt": generated.isoformat(),
            "countries": sorted({r["country"] for r in rows}),
            "years": sorted({r["year"] for r in rows}),
            "failed": failed,
            "sources": [
                {"name": "Nager.Date", "url": "https://date.nager.at", "license": "MIT"},
                {"name": "OpenHolidays API", "url": "https://openholidaysapi.org", "license": "see site terms"},
            ],
            "note": "Publish only after spot-checking against official government sources.",
        },
        "holidays": rows,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")

    if not args.no_snapshot:
        snap_dir = Path(args.snapshot_dir)
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"holidays-{generated.date().isoformat()}.json"
        snap_path.write_text(text, encoding="utf-8")
        print(f"Snapshot -> {snap_path}")

    print(f"\nWrote {len(rows)} rows -> {out_path}")
    if failed:
        print(f"Fetch failures ({len(failed)}): {', '.join(failed[:20])}{' ...' if len(failed) > 20 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
