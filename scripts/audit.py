#!/usr/bin/env python3
"""HolidayKit data audit.

检查 data/holidays.json：
- schema（必填字段、日期格式）
- 重复行
- 覆盖率（国家×年份缺失、假期数量异常）
- 官方源清单缺失
- 周末假期占比（信息性）
- 与 data/snapshots/ 上一份快照的 diff（新增/删除）

退出码：0 = 通过（可能有 warning）；1 = 有 error（schema/重复）。
报告写到 data/audit-report.json，方便 CI 存档。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("country", "date", "name", "types", "global", "year")


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows_of(payload) -> list[dict]:
    if isinstance(payload, dict):
        return payload.get("holidays") or []
    return payload or []


def keyset(rows: list[dict]) -> list[tuple]:
    return sorted((r.get("country"), r.get("date"), r.get("name")) for r in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit holiday data")
    parser.add_argument("--data", default=str(ROOT / "data" / "holidays.json"))
    parser.add_argument("--snapshot-dir", default=str(ROOT / "data" / "snapshots"))
    parser.add_argument("--countries-file", default=str(ROOT / "data" / "official_sources.json"))
    parser.add_argument("--report", default=str(ROOT / "data" / "audit-report.json"))
    parser.add_argument("--min-holidays", type=int, default=4)
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Run: python scripts/collect.py")
        return 1

    payload = load_json(data_path)
    rows = rows_of(payload)
    errors: list[str] = []
    warnings: list[str] = []

    # 1) schema
    for i, row in enumerate(rows):
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            errors.append(f"row {i}: missing fields {missing}")
            continue
        raw_date = str(row.get("date") or "")
        if len(raw_date) != 10:
            errors.append(f"row {i}: bad date {raw_date!r}")
            continue
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            errors.append(f"row {i}: unparsable date {raw_date!r}")
        if not str(row.get("name") or "").strip():
            errors.append(f"row {i}: empty name")

    # 2) duplicates
    seen: dict[tuple, int] = defaultdict(int)
    for row in rows:
        seen[(row.get("country"), row.get("date"), row.get("name"))] += 1
    for key, count in seen.items():
        if count > 1:
            errors.append(f"duplicate row x{count}: {key}")

    # 3) coverage
    by_cy: dict[tuple, list] = defaultdict(list)
    for row in rows:
        try:
            year = int(row.get("year") or str(row["date"])[:4])
        except (KeyError, ValueError):
            continue
        by_cy[(row.get("country"), year)].append(row)
    countries = sorted({c for c, _ in by_cy})
    years = sorted({y for _, y in by_cy})
    for cc in countries:
        for year in years:
            count = len(by_cy.get((cc, year), []))
            if count == 0:
                warnings.append(f"{cc} {year}: no data")
            elif count < args.min_holidays:
                warnings.append(f"{cc} {year}: only {count} holidays")

    # 4) official source checklist
    sources: dict = {}
    source_path = Path(args.countries_file)
    if source_path.exists():
        try:
            sources = load_json(source_path)
        except ValueError:
            warnings.append(f"cannot parse {source_path}")
    else:
        warnings.append(f"official sources file missing: {source_path}")
    missing_sources = [c for c in countries if c not in sources]
    if missing_sources:
        warnings.append("no official source entry for: " + ", ".join(missing_sources))

    # 5) weekend share (informational)
    weekend = 0
    for row in rows:
        try:
            if date.fromisoformat(str(row["date"])).weekday() >= 5:
                weekend += 1
        except (KeyError, ValueError):
            continue
    weekend_share = round(100.0 * weekend / len(rows), 1) if rows else 0.0

    # 6) diff against previous snapshot
    diff: dict = {}
    snap_dir = Path(args.snapshot_dir)
    if snap_dir.exists():
        candidates = sorted(snap_dir.glob("holidays-*.json"), reverse=True)
        current_keys = keyset(rows)
        previous = None
        for candidate in candidates:
            try:
                candidate_rows = rows_of(load_json(candidate))
            except (OSError, ValueError):
                continue
            if keyset(candidate_rows) != current_keys:
                previous = candidate
                break
        if previous is not None:
            prev_rows = rows_of(load_json(previous))
            prev_set = set(keyset(prev_rows))
            cur_set = set(current_keys)
            added = sorted(cur_set - prev_set)
            removed = sorted(prev_set - cur_set)
            diff = {
                "previous": str(previous),
                "added": len(added),
                "removed": len(removed),
                "addedSample": added[:10],
                "removedSample": removed[:10],
            }
            if added or removed:
                warnings.append(f"diff vs {previous.name}: +{len(added)} added, -{len(removed)} removed")

    report = {
        "data": str(data_path),
        "rows": len(rows),
        "countries": len(countries),
        "years": years,
        "weekendSharePct": weekend_share,
        "errors": errors,
        "warnings": warnings,
        "diff": diff,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"rows={len(rows)} countries={len(countries)} years={years} weekend={weekend_share}%")
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")
    print(f"report -> {report_path}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s)")
        return 1
    print("\nOK (with warnings)" if warnings else "\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
