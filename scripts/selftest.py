#!/usr/bin/env python3
"""HolidayKit self-test.

一条命令验证：数据可读 → 长周末引擎可跑 → 静态站能构建 → 关键产物存在。

用法
  python scripts/selftest.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import build_site  # noqa: E402


def load_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload.get("holidays") or []
    return payload or []


def main() -> int:
    real = ROOT / "data" / "holidays.json"
    sample = ROOT / "data" / "sample-holidays.json"
    data_path = real if real.exists() else sample
    if not data_path.exists():
        print("FAIL: no data file (run scripts/collect.py or restore sample-holidays.json)")
        return 1

    rows = load_rows(data_path)
    if not rows:
        print(f"FAIL: {data_path} has no holidays")
        return 1

    runs = build_site.compute_long_weekends(rows, 2026, include_regional=True)
    print(f"data: {data_path.name} ({len(rows)} rows), long-weekend runs 2026: {len(runs)}")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "dist"
        sys.argv = [
            "build_site.py",
            "--data", str(data_path),
            "--out", str(out),
            "--site-url", "https://example.test",
        ]
        rc = build_site.main()
        if rc != 0:
            print(f"FAIL: build returned {rc}")
            return 1

        must = [
            "index.html", "sitemap.xml", "robots.txt", "widget.js", "_headers", "ads.txt",
            "api/v1/countries.json", "api/index.html",
            "premium/index.html", "embed/index.html",
            "holidays/index.html", "days-until/index.html",
            "privacy/index.html", "about/index.html",
        ]
        missing = [p for p in must if not (out / p).exists()]
        if missing:
            print(f"FAIL: missing outputs: {missing}")
            return 1

        countries = sorted({r["country"] for r in rows})
        for cc in countries[:2]:
            name = build_site.country_name(cc)
            slug = build_site.slugify(name)
            if not (out / slug / "index.html").exists():
                print(f"FAIL: country page missing: {slug}")
                return 1
            ics_files = sorted((out / slug).glob("calendar-*.ics"))
            if not ics_files:
                print(f"FAIL: no ICS for {slug}")
                return 1
            year = ics_files[-1].stem.split("-")[-1]
            api_file = out / "api" / "v1" / "holidays" / cc / f"{year}.json"
            if not api_file.exists():
                print(f"FAIL: API json missing: {api_file}")
                return 1

    print("selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
