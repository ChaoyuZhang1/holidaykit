#!/usr/bin/env python3
"""Collect China 调休 (arranged rest) and 补班 (make-up workdays) into data/cn_calendar.json.

Sources:
1. chinese-days npm ICS (2025–2027, Chinese names, marks 休/班) via jsDelivr
2. chinese_calendar python package (fallback / cross-check, up to 2026)

Output:
{
  "meta": {"generatedAt": ..., "coverage": [2025, 2026, 2027], "sources": [...]},
  "years": {
    "2026": {
      "rest": [{"date": "2026-01-01", "name": "元旦"}],
      "work": [{"date": "2026-01-04", "name": "元旦"}]
    }
  }
}
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cn_calendar.json"
RAW = ROOT / "data" / "cn_raw.ics"
CURL = shutil.which("curl.exe") or shutil.which("curl") or "curl"
ICS_URL = "https://cdn.jsdelivr.net/npm/chinese-days/dist/holidays.ics"


def fetch_ics() -> bool:
    for attempt in range(3):
        try:
            subprocess.run(
                [CURL, "-s", "--max-time", "40", "-o", str(RAW), ICS_URL],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=50,
                check=False,
            )
        except Exception:
            pass
        if RAW.exists() and RAW.stat().st_size > 1000:
            return True
    return False


def decode(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "big5"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def clean_name(summary: str) -> str:
    name = summary.strip()
    for token in ("（休）", "(休)", "（班）", "(班)", "休", "班"):
        name = name.replace(token, "")
    return name.strip(" -—")


def parse_ics(text: str) -> dict:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    years: dict[str, dict] = {}
    current: dict | None = None
    for line in unfolded:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                start = current.get("start")
                end = current.get("end") or ""
                summary = current.get("summary", "")
                if start and len(start) == 8:
                    try:
                        first = date(int(start[:4]), int(start[4:6]), int(start[6:8]))
                    except ValueError:
                        first = None
                    if first:
                        if len(end) == 8:
                            try:
                                last = date(int(end[:4]), int(end[4:6]), int(end[6:8]))
                            except ValueError:
                                last = first + timedelta(days=1)
                        else:
                            last = first + timedelta(days=1)
                        if last <= first:
                            last = first + timedelta(days=1)
                        bucket = "work" if "班" in summary else ("rest" if "休" in summary else "")
                        if bucket:
                            day = first
                            while day < last:
                                years.setdefault(str(day.year), {"rest": [], "work": []})[bucket].append(
                                    {"date": day.isoformat(), "name": clean_name(summary)}
                                )
                                day += timedelta(days=1)
            current = None
            continue
        if current is None:
            continue
        if line.startswith("DTSTART"):
            current["start"] = line.rsplit(":", 1)[-1].strip()[:8]
        elif line.startswith("DTEND"):
            current["end"] = line.rsplit(":", 1)[-1].strip()[:8]
        elif line.startswith("SUMMARY"):
            current["summary"] = line.split(":", 1)[-1].strip()
    for year_data in years.values():
        year_data["rest"].sort(key=lambda r: r["date"])
        year_data["work"].sort(key=lambda r: r["date"])
    return years


def supplement_python_holidays(years: dict) -> list[str]:
    """Fill/cross-check 2025–2026 from the chinese_calendar package."""
    try:
        import chinese_calendar as cn
    except ImportError:
        return ["python package chinesecalendar not installed (skipped supplement)"]
    notes: list[str] = []
    for year in (2025, 2026):
        try:
            rest_map = getattr(cn, "holidays", {})
            work_map = getattr(cn, "workdays", {})
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{year}: {exc}")
            continue
        rest = [{"date": d.isoformat(), "name": str(n)} for d, n in sorted(rest_map.items()) if d.year == year]
        work = [{"date": d.isoformat(), "name": str(n)} for d, n in sorted(work_map.items()) if d.year == year]
        if not rest and not work:
            continue
        bucket = years.setdefault(str(year), {"rest": [], "work": []})
        existing_rest = {item["date"] for item in bucket["rest"]}
        existing_work = {item["date"] for item in bucket["work"]}
        added = 0
        for item in rest:
            if item["date"] not in existing_rest:
                bucket["rest"].append({"date": item["date"], "name": ""})
                added += 1
        for item in work:
            if item["date"] not in existing_work:
                bucket["work"].append({"date": item["date"], "name": ""})
                added += 1
        if added:
            notes.append(f"{year}: supplemented {added} dates from chinesecalendar")
        bucket["rest"].sort(key=lambda r: r["date"])
        bucket["work"].sort(key=lambda r: r["date"])
    return notes


def main() -> int:
    sources = []
    years: dict = {}
    if fetch_ics():
        text = decode(RAW.read_bytes())
        years = parse_ics(text)
        sources.append({"name": "chinese-days (npm ICS)", "url": ICS_URL})
    else:
        print("WARN: failed to fetch chinese-days ICS")

    notes = supplement_python_holidays(years)
    if any("chinesecalendar" not in n for n in notes):
        sources.append({"name": "chinese_calendar (PyPI)"})

    coverage = sorted(int(y) for y in years)
    payload = {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "coverage": coverage,
            "sources": sources,
            "notes": notes,
        },
        "years": {y: years[y] for y in sorted(years)},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total_rest = sum(len(v["rest"]) for v in years.values())
    total_work = sum(len(v["work"]) for v in years.values())
    print(f"CN_DONE years={coverage} rest={total_rest} work={total_work} -> {OUT}")
    if notes:
        print("notes:", "; ".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
