#!/usr/bin/env python3
"""Assemble data/holidays.json from curl-fetched cache (data/cache/{CC}/{year}.json).

Why: Python urllib suffers TLS handshake timeouts on some networks; curl.exe is reliable.
Run scripts/fetch_cache.ps1 first, then this script.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from collect import dedupe, normalize_nager  # noqa: E402


def merge_rows(rows: list[dict]) -> list[dict]:
    """同一 (country, date, name) 的多行（不同 types / counties）合并成一行。"""
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (row["country"], row["date"], row["name"])
        if key not in merged:
            merged[key] = dict(row)
            continue
        cur = merged[key]
        cur["types"] = sorted(set(cur.get("types") or []) | set(row.get("types") or []))
        cur["global"] = bool(cur.get("global") or row.get("global"))
        cur["counties"] = sorted(
            set(cur.get("counties") or []) | set(row.get("counties") or [])
        )
    return list(merged.values())


def main() -> int:
    cache = ROOT / "data" / "cache"
    out_path = ROOT / "data" / "holidays.json"
    if not cache.exists():
        print(f"cache not found: {cache}\nRun: powershell -ExecutionPolicy Bypass -File scripts/fetch_cache.ps1")
        return 1

    rows: list[dict] = []
    failed: list[str] = []
    for cc_dir in sorted(p for p in cache.iterdir() if p.is_dir()):
        cc = cc_dir.name
        for file in sorted(cc_dir.glob("*.json")):
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                failed.append(f"{cc}-{file.stem}")
                continue
            if not isinstance(raw, list):
                failed.append(f"{cc}-{file.stem}")
                continue
            year = int(file.stem)
            rows.extend(normalize_nager(cc, year, raw))

    rows = dedupe(rows)
    rows = merge_rows(rows)
    rows.sort(key=lambda r: (r["country"], r["date"], r["name"]))
    if not rows:
        print("No rows assembled; check data/cache content.")
        return 1

    generated = datetime.now(timezone.utc)
    payload = {
        "meta": {
            "generatedAt": generated.isoformat(),
            "countries": sorted({r["country"] for r in rows}),
            "years": sorted({r["year"] for r in rows}),
            "failed": failed,
            "sources": [
                {"name": "Nager.Date", "url": "https://date.nager.at", "license": "MIT"},
            ],
            "note": "Assembled from curl cache; spot-check against official sources before publishing.",
        },
        "holidays": rows,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")

    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / f"holidays-{generated.date().isoformat()}.json").write_text(text, encoding="utf-8")

    print(f"countries={len(payload['meta']['countries'])} years={payload['meta']['years']} rows={len(rows)}")
    if failed:
        print(f"failed={len(failed)}: {', '.join(failed[:20])}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
