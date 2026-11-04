#!/usr/bin/env python3
"""Generate the social share image (assets/og-cover.png, 1200x630).

Run once (or whenever branding changes):
  python scripts/make_og.py
Requires Pillow (pip install pillow, or use the bundled runtime python).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "og-cover.png"

W, H = 1200, 630
BG = (21, 22, 26)
INK = (251, 250, 247)
MUTED = (167, 163, 154)
ACCENT = (15, 107, 92)
AMBER = (194, 118, 26)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\georgiab.ttf",
    r"C:\Windows\Fonts\georgia.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # accent bar
    draw.rectangle([0, 0, W, 10], fill=ACCENT)

    title_font = load_font(96)
    sub_font = load_font(34)
    meta_font = load_font(24)

    draw.text((80, 96), "HolidayKit", font=title_font, fill=INK)
    draw.text((84, 224), "Public holidays & long weekends", font=sub_font, fill=INK)
    draw.text((84, 272), "for every country", font=sub_font, fill=INK)

    # stats row
    stats = [("95", "countries"), ("5,600+", "holidays"), ("2025–2028", "covered")]
    x = 84
    for num, label in stats:
        num_font = load_font(52)
        draw.text((x, 396), num, font=num_font, fill=INK)
        draw.text((x, 462), label, font=meta_font, fill=MUTED)
        x += 340

    # accent dot + footer
    draw.ellipse([84, 536, 100, 552], fill=ACCENT)
    draw.text((112, 528), "holidaykit.pages.dev", font=meta_font, fill=MUTED)
    draw.text((W - 300, 528), "free calendar subscriptions", font=meta_font, fill=AMBER)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
