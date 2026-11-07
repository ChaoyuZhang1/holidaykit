#!/usr/bin/env python3
"""HolidayKit static site builder.

读取 data/holidays.json（scripts/collect.py 生成），输出纯静态站到 dist/：
  /                                  首页（国家列表）
  /{country}/                        国家页（最新两年假期 + 长周末 + ICS）
  /{country}/{year}/                 年份页
  /{country}/{year}/long-weekends/   长周末 / 桥假规划页
  /{country}/calendar/               日历订阅页
  /{country}/calendar-{year}.ics     ICS 订阅
  /privacy/ /about/                  合规页
  /sitemap.xml /robots.txt

纯标准库，Python 3.10+。

用法
  python scripts/build_site.py
  python scripts/build_site.py --data data/sample-holidays.json --out dist
  python scripts/build_site.py --site-url https://your-domain.com
"""
from __future__ import annotations

import argparse
import calendar
import html
import json
from urllib.parse import urljoin
import re
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

try:
    import qrcode  # type: ignore
except ImportError:  # pragma: no cover
    qrcode = None

ROOT = Path(__file__).resolve().parents[1]

SITE_NAME = "HolidayKit"
SITE_TAGLINE = "Public holidays and long weekends for every country"

# 运行期全局配置（main() 根据命令行参数注入）
SITE_URL = "https://holidaykit.example"
AFFILIATE_URL = ""
CONTACT_EMAIL = "hello@example.com"
ADSENSE_CLIENT = ""
OFFICIAL_SOURCES: dict[str, dict] = {}
OG_IMAGE = False
GOOGLE_VERIFY = ""
SCHOOL_DATA: dict = {}
SCHOOL_NAMES: dict = {}
CN_CAL: dict = {}

MONTHS_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
    "NZ": "New Zealand", "IE": "Ireland", "DE": "Germany", "FR": "France", "ES": "Spain",
    "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "AT": "Austria",
    "CH": "Switzerland", "PT": "Portugal", "SE": "Sweden", "NO": "Norway",
    "DK": "Denmark", "FI": "Finland", "PL": "Poland", "CZ": "Czechia",
    "GR": "Greece", "HU": "Hungary", "RO": "Romania", "JP": "Japan",
    "KR": "South Korea", "SG": "Singapore", "IN": "India", "BR": "Brazil",
    "MX": "Mexico", "ID": "Indonesia", "PH": "Philippines", "VN": "Vietnam",
    "ZA": "South Africa", "AE": "United Arab Emirates", "TR": "Turkey",
    "TH": "Thailand", "MY": "Malaysia",
    "AM": "Armenia", "AR": "Argentina", "AZ": "Azerbaijan", "BD": "Bangladesh",
    "BG": "Bulgaria", "BH": "Bahrain", "CL": "Chile", "CN": "China",
    "CO": "Colombia", "CR": "Costa Rica", "CY": "Cyprus", "EC": "Ecuador",
    "EE": "Estonia", "EG": "Egypt", "GE": "Georgia", "HK": "Hong Kong",
    "HR": "Croatia", "IS": "Iceland", "KE": "Kenya", "KZ": "Kazakhstan",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MA": "Morocco",
    "MN": "Mongolia", "MT": "Malta", "NG": "Nigeria", "PA": "Panama",
    "PE": "Peru", "RS": "Serbia", "RU": "Russia", "SI": "Slovenia",
    "SK": "Slovakia", "TN": "Tunisia", "TW": "Taiwan", "UA": "Ukraine",
    "UY": "Uruguay", "VE": "Venezuela", "BG": "Bulgaria", "PK": "Pakistan",
    "AD": "Andorra", "AL": "Albania", "BY": "Belarus", "IL": "Israel",
    "JO": "Jordan", "KW": "Kuwait", "LB": "Lebanon", "LI": "Liechtenstein",
    "LK": "Sri Lanka", "MC": "Monaco", "MD": "Moldova", "MU": "Mauritius",
    "OM": "Oman", "QA": "Qatar", "SA": "Saudi Arabia", "SM": "San Marino",
    "UZ": "Uzbekistan", "VA": "Vatican City", "ME": "Montenegro", "BA": "Bosnia and Herzegovina",
}

# Localized homepage copy (server-rendered language homepages /zh/ /ja/ ...)
HOME_I18N = {
    "zh": {
        "title": "HolidayKit — 各国公共假期与长周末",
        "desc": "浏览各国公共假期、长周末与桥假，一键订阅日历。",
        "eyebrow": "公共假期 · 长周末",
        "h1": "围绕长周末规划你的一年。",
        "lede": "每个国家的公共假期、能拼出的最长假期，以及一键订阅日历。",
        "cta_browse": "浏览国家",
        "cta_country": "查看 {name} 假期",
        "stats": ["国家", "假期", "覆盖年份"],
        "browse": "浏览国家",
        "browse_sub": "按国家查看每个公共假期、长周末与桥假。",
        "how": "HolidayKit 怎么用",
        "how_cards": [
            ("1 · 选择国家", "查看全部法定假期，包括地区性假期。"),
            ("2 · 找到长周末", "桥假告诉你请几天假能连休 4–6 天。"),
            ("3 · 加入日历", "一个 .ics 链接支持 Google、Apple、Outlook。"),
        ],
        "cal_open": "打开完整日历",
        "foot_note": "数据来自公开来源，并对照官方公告核对。",
    },
    "ja": {
        "title": "HolidayKit — 各国の祝日とロングウィークエンド",
        "desc": "各国の祝日・長い週末・橋渡し休暇を確認し、カレンダーを購読できます。",
        "eyebrow": "祝日 · 長い週末",
        "h1": "長い週末を中心に一年を計画しよう。",
        "lede": "各国の祝日、作れる最長の連休、ワンクリックのカレンダー購読。",
        "cta_browse": "国を見る",
        "cta_country": "{name} の祝日を見る",
        "stats": ["国", "祝日", "対象年"],
        "browse": "国一覧",
        "browse_sub": "国ごとに祝日・長い週末・橋渡し休暇を確認。",
        "how": "HolidayKit の使い方",
        "how_cards": [
            ("1 · 国を選ぶ", "地域ごとの祝日も含めて確認できます。"),
            ("2 · 長い週末を探す", "有給を何日使うと 4〜6 連休になるかが分かります。"),
            ("3 · カレンダーに追加", "1 つの .ics リンクで Google / Apple / Outlook に対応。"),
        ],
        "cal_open": "カレンダーを開く",
        "foot_note": "データは公開情報を基に公式発表と照合しています。",
    },
    "ko": {
        "title": "HolidayKit — 국가별 공휴일과 긴 주말",
        "desc": "국가별 공휴일과 긴 주말, 징검다리 휴일을 확인하고 캘린더를 구독하세요.",
        "eyebrow": "공휴일 · 긴 주말",
        "h1": "긴 주말 중심으로 한 해를 계획하세요.",
        "lede": "모든 공휴일, 만들 수 있는 가장 긴 연휴, 원클릭 캘린더 구독.",
        "cta_browse": "국가 보기",
        "cta_country": "{name} 공휴일 보기",
        "stats": ["국가", "공휴일", "대상 연도"],
        "browse": "국가 목록",
        "browse_sub": "국가별 공휴일·긴 주말·징검다리 휴일을 확인하세요.",
        "how": "HolidayKit 사용법",
        "how_cards": [
            ("1 · 국가 선택", "지역별 공휴일까지 모두 확인할 수 있습니다."),
            ("2 · 긴 주말 찾기", "연차 며칠로 4~6일 연휴를 만들 수 있는지 보여줍니다."),
            ("3 · 캘린더에 추가", "하나의 .ics 링크로 Google·Apple·Outlook 지원."),
        ],
        "cal_open": "전체 캘린더 열기",
        "foot_note": "공개 데이터와 공식 발표를 대조했습니다.",
    },
    "es": {
        "title": "HolidayKit — Días festivos y fines de semana largos",
        "desc": "Consulta días festivos, fines de semana largos y suscríbete al calendario.",
        "eyebrow": "Días festivos · fines de semana largos",
        "h1": "Planifica tu año según los fines de semana largos.",
        "lede": "Todos los días festivos, los descansos más largos y suscripción al calendario en un clic.",
        "cta_browse": "Ver países",
        "cta_country": "Ver festivos de {name}",
        "stats": ["Países", "Festivos", "Años"],
        "browse": "Países",
        "browse_sub": "Cada festivo, fin de semana largo y puente, país por país.",
        "how": "Cómo funciona HolidayKit",
        "how_cards": [
            ("1 · Elige un país", "Todos los festivos oficiales, incluidos los regionales."),
            ("2 · Encuentra el fin de semana largo", "Los puentes muestran cuántos días de permiso dan 4–6 días libres."),
            ("3 · Añádelo a tu calendario", "Un enlace .ics para Google Calendar, Apple Calendar y Outlook."),
        ],
        "cal_open": "Abrir calendario completo",
        "foot_note": "Datos de fuentes abiertas, verificados con anuncios oficiales.",
    },
    "fr": {
        "title": "HolidayKit — Jours fériés et longs week-ends",
        "desc": "Consultez les jours fériés, les longs week-ends et abonnez-vous au calendrier.",
        "eyebrow": "Jours fériés · longs week-ends",
        "h1": "Planifiez votre année autour des longs week-ends.",
        "lede": "Tous les jours fériés, les plus longues pauses et un abonnement calendrier en un clic.",
        "cta_browse": "Voir les pays",
        "cta_country": "Voir les fériés de {name}",
        "stats": ["Pays", "Jours fériés", "Années"],
        "browse": "Pays",
        "browse_sub": "Chaque férié, long week-end et pont, pays par pays.",
        "how": "Comment fonctionne HolidayKit",
        "how_cards": [
            ("1 · Choisissez un pays", "Tous les jours fériés, y compris régionaux."),
            ("2 · Trouvez le long week-end", "Les ponts montrent combien de congés donnent 4 à 6 jours."),
            ("3 · Ajoutez-le à votre calendrier", "Un lien .ics pour Google, Apple et Outlook."),
        ],
        "cal_open": "Ouvrir le calendrier",
        "foot_note": "Données ouvertes, recoupées avec les annonces officielles.",
    },
    "de": {
        "title": "HolidayKit — Feiertage und lange Wochenenden",
        "desc": "Feiertage, lange Wochenenden und Brückentage ansehen, Kalender abonnieren.",
        "eyebrow": "Feiertage · lange Wochenenden",
        "h1": "Plane dein Jahr um lange Wochenenden.",
        "lede": "Alle Feiertage, die längsten Pausen und Kalender-Abo mit einem Klick.",
        "cta_browse": "Länder ansehen",
        "cta_country": "{name} Feiertage ansehen",
        "stats": ["Länder", "Feiertage", "Jahre"],
        "browse": "Länder",
        "browse_sub": "Jeder Feiertag, jedes lange Wochenende, Land für Land.",
        "how": "So funktioniert HolidayKit",
        "how_cards": [
            ("1 · Land wählen", "Alle offiziellen Feiertage, auch regionale."),
            ("2 · Langes Wochenende finden", "Brückentage zeigen, wie viel Urlaub 4–6 Tage frei bringt."),
            ("3 · Zum Kalender hinzufügen", "Ein .ics-Link für Google, Apple und Outlook."),
        ],
        "cal_open": "Ganzen Kalender öffnen",
        "foot_note": "Offene Daten, abgeglichen mit offiziellen Bekanntmachungen.",
    },
}
LANG_LABELS = {"en": "EN", "zh": "中文", "ja": "日本語", "ko": "한국어", "es": "ES", "fr": "FR", "de": "DE"}



CSS = """
:root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--soft:#f9fafb;--brand:#0f766e;--accent:#f59e0b}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff;line-height:1.6}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:980px;margin:0 auto;padding:0 18px}
.site-head{border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(255,255,255,.94);backdrop-filter:blur(6px);z-index:10}
.head-inner{display:flex;align-items:center;justify-content:space-between;height:56px}
.brand{font-weight:800;font-size:1.15rem;letter-spacing:-.02em;color:var(--ink)}
.site-head nav a{margin-left:16px;color:var(--muted);font-size:.92rem}
.hero{padding:44px 0 20px}
.hero h1{font-size:clamp(1.7rem,4vw,2.5rem);line-height:1.15;margin:0 0 12px;letter-spacing:-.02em}
.hero p.lede{font-size:1.05rem;color:var(--muted);max-width:760px}
.badge{display:inline-block;font-size:.72rem;background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--muted);vertical-align:middle}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:18px 0 8px}
.card{border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:#fff;transition:box-shadow .15s}
.card:hover{box-shadow:0 6px 20px rgba(17,24,39,.07)}
.card h3{margin:6px 0 4px;font-size:1rem}
.card p{margin:0;color:var(--muted);font-size:.85rem}
table{width:100%;border-collapse:collapse;margin:10px 0}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);font-size:.93rem;vertical-align:top}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}
.tbl-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:14px}
.btn{display:inline-block;background:var(--brand);color:#fff;border-radius:10px;padding:10px 16px;font-weight:600;font-size:.93rem;margin:4px 6px 4px 0}
.btn.ghost{background:#fff;color:var(--brand);border:1px solid var(--brand)}
.btn:hover{text-decoration:none;opacity:.92}
.ad{border:1px dashed var(--line);border-radius:12px;padding:16px;text-align:center;color:var(--muted);font-size:.8rem;margin:22px 0;background:var(--soft)}
.sec{margin:32px 0}
.sec h2{font-size:1.25rem;margin:0 0 6px}
.muted{color:var(--muted)}
.faq dt{font-weight:600;margin-top:14px}
.faq dd{margin:4px 0 0;color:var(--muted)}
.years{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 18px}
.years a{border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:.88rem;color:var(--ink)}
.years a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.callout{border-left:3px solid var(--accent);background:#fffbeb;padding:12px 16px;border-radius:10px;font-size:.92rem}
.site-foot{border-top:1px solid var(--line);margin-top:48px;padding:22px 0 40px;color:var(--muted);font-size:.84rem}
.site-foot p{margin:6px 0}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 9px;margin:2px 4px 2px 0;font-size:.8rem;color:var(--ink);background:var(--soft)}
@media(max-width:600px){td,th{padding:8px 6px;font-size:.86rem}}
.code{background:#0b1020;color:#e5e7eb;border-radius:10px;padding:12px 14px;overflow-x:auto;font-size:.8rem;line-height:1.55;white-space:pre-wrap;word-break:break-word}
.countdown{font-weight:800;font-size:clamp(2rem,6vw,3.4rem);letter-spacing:-.02em;margin:10px 0;color:var(--brand)}
.price-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:16px 0}
.price{border:1px solid var(--line);border-radius:16px;padding:18px;background:#fff}
.price.featured{border-color:var(--brand);box-shadow:0 8px 24px rgba(15,118,110,.12)}
.price h3{margin:0 0 6px}
.price .amount{font-size:1.6rem;font-weight:800;margin-bottom:8px}
.price ul{padding-left:18px;margin:8px 0 0;font-size:.9rem;color:var(--muted)}
"""

# ── V2 design layer（在基础 CSS 之后加载，同名选择器后者覆盖前者）────────────
CSS2 = """
:root{
  --ink:#15161a;--ink-soft:#2a2c33;--muted:#6b6f78;--line:#e8e5dd;
  --bg:#fbfaf7;--surface:#ffffff;--soft:#f4f1ea;
  --accent:#0f6b5c;--accent-ink:#0b4f44;--amber:#c2761a;
  --brand:#0f6b5c;--radius:18px;--radius-sm:12px;
  --font-body:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;
  --font-display:ui-serif,Georgia,"Iowan Old Style","Times New Roman","Songti SC",serif;
}
body{background:var(--bg);color:var(--ink);font-family:var(--font-body);line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
.wrap{max-width:1080px;padding:0 22px}
.site-head{background:rgba(251,250,247,.88);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.head-inner{height:64px}
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:700;letter-spacing:-.02em;color:var(--ink);font-size:1.05rem}
.brand:hover{text-decoration:none}
.brand-mark{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:9px;background:var(--ink);color:#fff;font-size:.8rem}
.site-head nav{display:flex;gap:22px;margin:0}
.site-head nav a{margin:0;color:var(--ink-soft);font-size:.9rem;font-weight:500}
.site-head nav a:hover{color:var(--accent);text-decoration:none}
.hero{padding:64px 0 26px}
.hero-inner{display:grid;grid-template-columns:1.35fr .9fr;gap:44px;align-items:center}
.eyebrow{display:inline-block;font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:var(--amber);font-weight:700;margin:0 0 14px}
.hero h1,.hero-country h1{font-family:var(--font-display);font-size:clamp(2.1rem,4.6vw,3.5rem);line-height:1.08;letter-spacing:-.02em;margin:0 0 18px;font-weight:600}
.hero .lede,.hero-country .lede{font-size:1.06rem;color:var(--muted);max-width:36em;margin:0 0 24px}
.cta-row{display:flex;gap:12px;flex-wrap:wrap}
.btn{background:var(--ink);color:#fff;border:1px solid var(--ink);border-radius:999px;padding:11px 22px;font-weight:600;font-size:.92rem;transition:transform .15s ease,box-shadow .15s ease}
.btn:hover{text-decoration:none;transform:translateY(-1px);box-shadow:0 10px 24px rgba(21,22,26,.18)}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line)}
.btn.ghost:hover{border-color:var(--ink);box-shadow:none}
.stats{display:flex;gap:36px;margin:38px 0 0;padding:22px 0 0;border-top:1px solid var(--line);flex-wrap:wrap}
.stat .num{font-family:var(--font-display);font-size:1.75rem;line-height:1.1}
.stat .lbl{font-size:.74rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.hero-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px;box-shadow:0 18px 50px rgba(21,22,26,.08)}
.hero-card h3{margin:8px 0 2px;font-size:1.05rem}
.hero-card .days{font-family:var(--font-display);font-size:2.5rem;line-height:1;margin:14px 0 0;color:var(--accent)}
.hero-card .days span{font-size:.85rem;color:var(--muted);font-family:var(--font-body);margin-left:8px}
.hero-card p{margin:0;font-size:.86rem}
.grid{grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:14px}
.card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:16px 18px;color:var(--ink);transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease}
.card:hover{text-decoration:none;transform:translateY(-2px);border-color:#d8d3c7;box-shadow:0 14px 34px rgba(21,22,26,.08)}
.card .flag{font-size:1.35rem;line-height:1}
.card h3{margin:8px 0 3px;font-size:1rem;font-weight:650}
.card p{font-size:.84rem}
.sec{margin:46px 0}
.sec h2{font-family:var(--font-display);font-size:clamp(1.4rem,2.2vw,1.9rem);font-weight:600;letter-spacing:-.01em;margin:0 0 8px}
.sec .sub{color:var(--muted);margin:0 0 18px;font-size:.95rem}
.tbl-wrap{background:var(--surface);border-radius:var(--radius-sm)}
th,td{padding:12px 14px}
th{background:var(--soft);font-size:.72rem;letter-spacing:.08em}
tbody tr:hover{background:#fcfbf8}
.badge,.pill{background:var(--surface)}
.callout{background:#fdf6e9;border-left:3px solid var(--amber);border-radius:10px;margin:18px 0}
.ad{border:1px dashed #d8d3c7;background:#f7f4ee;color:#9a958a;border-radius:var(--radius-sm);padding:18px;min-height:96px;display:grid;place-items:center;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;margin:30px 0}
.years a{border-radius:999px;padding:6px 14px;font-size:.86rem}
.years a:hover{border-color:var(--ink);text-decoration:none}
.faq dt{font-weight:650;margin-top:16px}
.faq dd{font-size:.94rem}
.code{background:#16181d;color:#e9e6df;border-radius:var(--radius-sm)}
.countdown{font-family:var(--font-display);font-weight:600;font-size:clamp(2.2rem,6vw,3.6rem);margin:12px 0;color:var(--accent);line-height:1}
.price{background:var(--surface);border-radius:var(--radius);padding:22px}
.price.featured{border-color:var(--accent)}
.price h3{font-family:var(--font-display);font-size:1.2rem}
.site-foot{margin-top:64px;padding:34px 0 46px;font-size:.85rem}
.foot-grid{display:grid;grid-template-columns:1.6fr 1fr 1fr 1fr;gap:26px}
.foot-grid strong{display:block;color:var(--ink);font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px}
.foot-grid a{display:block;color:var(--muted);margin:5px 0;font-size:.85rem}
.foot-grid a:hover{color:var(--accent)}
.foot-brand{font-weight:700;color:var(--ink);font-size:1.02rem;margin-bottom:8px}
.foot-note{margin-top:26px;padding-top:18px;border-top:1px solid var(--line);font-size:.78rem;color:#8d8a82}
.flag{font-size:1.3rem;line-height:1}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 0}
.chip{font-size:.8rem;border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:5px 12px;color:var(--ink-soft)}
.hero-country{padding:52px 0 18px;display:grid;grid-template-columns:1.5fr .8fr;gap:34px;align-items:start}
.next-holiday{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:22px;box-shadow:0 16px 40px rgba(21,22,26,.06)}
.activity{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:18px 0}
.activity .card h3{font-size:.98rem}
@media(max-width:900px){.hero-inner,.hero-country{grid-template-columns:1fr}.foot-grid{grid-template-columns:1fr 1fr}}
@media(max-width:600px){td,th{padding:10px 8px;font-size:.86rem}.hero{padding:44px 0 18px}.stats{gap:20px}}
.lw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin:18px 0}
.lw-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:20px;transition:transform .15s ease,box-shadow .15s ease}
.lw-card:hover{transform:translateY(-2px);box-shadow:0 14px 34px rgba(21,22,26,.08)}
.lw-days{font-family:var(--font-display);font-size:2.6rem;line-height:1;color:var(--accent)}
.lw-days span{font-size:.72rem;color:var(--muted);font-family:var(--font-body);margin-left:8px;text-transform:uppercase;letter-spacing:.1em}
.lw-card h3{margin:10px 0 2px;font-size:1.02rem}
.lw-card .chips{margin-top:12px}
.cal-year{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.cal-month{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);padding:12px}
.cal-title{font-weight:650;font-size:.9rem;margin-bottom:6px}
.cal-head{display:grid;grid-template-columns:repeat(7,1fr);font-size:.66rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;text-align:center}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.cal-cell{font-size:.74rem;text-align:center;padding:5px 0;border-radius:6px;color:var(--ink)}
.cal-cell.muted{color:transparent}
.cal-weekend{background:var(--soft)}
.cal-holiday{background:var(--accent);color:#fff;font-weight:700}
.cal-legend{margin-top:14px;font-size:.78rem;color:var(--muted);display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.cal-key{display:inline-block;width:12px;height:12px;border-radius:4px;margin-left:12px}
.cal-holiday-key{background:var(--accent)}
.cal-weekend-key{background:var(--soft);border:1px solid var(--line)}
.mobile-cta{display:none}
@media(max-width:720px){.mobile-cta{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:30;gap:8px;padding:10px 14px;background:rgba(251,250,247,.97);border-top:1px solid var(--line);backdrop-filter:blur(12px)}.mobile-cta .btn{flex:1;padding:12px 16px}.site-foot{padding-bottom:104px}}
.hero-cal{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:0 18px 50px rgba(21,22,26,.08)}
.cal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.cal-month-label{font-weight:650;font-size:1rem}
.cal-nav-btn{width:32px;height:32px;border-radius:10px;border:1px solid var(--line);background:var(--surface);cursor:pointer;font-size:1.05rem;line-height:1;color:var(--ink)}
.cal-nav-btn:hover{border-color:var(--ink)}
.cal-single .cal-grid{margin-top:6px}
.cal-single .cal-cell{padding:8px 0;font-size:.8rem}
.cal-foot{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:.84rem;color:var(--muted);display:flex;gap:6px;flex-wrap:wrap}
.cal-country{color:var(--ink);font-weight:600}
.cal-rest{background:#fff7e6;color:#8a5a00}
.cal-makeup{background:#fee2e2;color:#991b1b;font-weight:700}
.cal-rest-key{background:#fff7e6;border:1px solid #f3d9a4}
.cal-makeup-key{background:#fee2e2;border:1px solid #fca5a5}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:12px}
.two-col h3{margin:0 0 8px;font-size:.98rem}
@media(max-width:760px){.two-col{grid-template-columns:1fr}}
.cal-list{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:4px;font-size:.8rem}
.cal-list li{display:flex;gap:8px;align-items:baseline;color:var(--ink-soft);line-height:1.35}
.cal-date{flex:0 0 auto;color:var(--muted);font-variant-numeric:tabular-nums;min-width:50px}
.cal-month .cal-list{font-size:.7rem;margin-top:8px;gap:3px}
.cal-month .cal-date{min-width:42px}
.cal-cell[data-date]{cursor:pointer}
.cal-detail{position:fixed;z-index:60;max-width:280px;background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:0 18px 50px rgba(21,22,26,.18);padding:14px 16px;font-size:.86rem;display:none}
.cal-detail.open{display:block}
.cal-detail .d-date{font-weight:700;margin-bottom:6px;color:var(--ink)}
.cal-detail .d-hol{color:var(--accent);margin:4px 0}
.cal-detail .d-note{color:var(--amber);font-size:.8rem;margin-top:6px}
.cal-detail .d-count{color:var(--muted);font-size:.8rem;margin-top:6px}
.lang-select{border:1px solid var(--line);background:var(--surface);color:var(--ink-soft);border-radius:9px;padding:4px 6px;font-size:.8rem;margin-left:12px}
@media(max-width:900px){
  .head-inner{height:auto;min-height:56px;flex-wrap:wrap;row-gap:6px;padding:8px 0}
  .site-head nav{order:3;width:100%;overflow-x:auto;gap:14px;padding:0 0 4px;white-space:nowrap}
  .site-head nav a{white-space:nowrap;font-size:.82rem}
  .lang-select{margin-left:auto}
  body{padding-bottom:76px}
  .site-foot{padding-bottom:110px}
  .hero-inner{grid-template-columns:1fr;gap:24px}
  .hero-cal{width:100%;max-width:100%;min-width:0}
  .stats{flex-wrap:wrap}
  .hero-cal .cal-single,.cal-single{min-width:0;width:100%}
}
@media(max-width:600px){
  .hero-inner{gap:18px}
  .hero h1,.hero-country h1{font-size:clamp(1.55rem,6.4vw,2.1rem)}
  .hero .lede,.hero-country .lede{font-size:.98rem}
  .hero-cal{padding:14px}
  .cal-single{min-width:0}
  .cal-single .cal-cell{padding:10px 0;font-size:.88rem}
  .grid{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
  .card{padding:14px}
  .foot-grid{grid-template-columns:1fr 1fr;gap:18px}
  .cal-list li{font-size:.76rem}
  .cal-date{min-width:44px}
  .two-col{grid-template-columns:1fr}
  .cal-year{grid-template-columns:1fr}
  .stats{gap:18px 26px}
  .stat .num{font-size:1.5rem}
  .cta-row .btn{flex:1 1 auto}
}
/* premium motion layer */
html{scroll-behavior:smooth}
.reveal{opacity:0;transform:translateY(14px);transition:opacity .62s cubic-bezier(.16,1,.3,1),transform .62s cubic-bezier(.16,1,.3,1)}
.reveal.in{opacity:1;transform:none}
.site-head{transition:box-shadow .3s cubic-bezier(.16,1,.3,1),background .3s}
.site-head.scrolled{box-shadow:0 10px 34px rgba(21,22,26,.08)}
.btn{transition:transform .18s cubic-bezier(.16,1,.3,1),box-shadow .25s,opacity .2s}
.btn:hover{transform:translateY(-1px);box-shadow:0 12px 28px rgba(21,22,26,.18)}
.card,.hero-cal{transition:transform .28s cubic-bezier(.16,1,.3,1),box-shadow .28s,border-color .28s}
.card:hover{transform:translateY(-3px);box-shadow:0 20px 48px rgba(21,22,26,.10)}
.hero{position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;inset:-50% -10% auto -10%;height:130%;background:radial-gradient(600px 300px at 18% 6%,rgba(15,107,92,.09),transparent 62%),radial-gradient(520px 260px at 88% 0%,rgba(194,118,26,.09),transparent 60%);pointer-events:none}
.hero>*{position:relative}
.cal-cell{transition:background .15s,transform .15s,box-shadow .15s,color .15s}
.cal-cell[data-date]:hover{transform:translateY(-1px);box-shadow:inset 0 0 0 1.5px var(--accent)}
tbody tr{transition:background .15s}
tbody tr:hover{background:#faf7f0}
nav a{position:relative}
::selection{background:rgba(15,107,92,.18)}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
.sub-actions{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 18px}
.sub-actions .btn{font-size:.88rem}
.sub-help{display:grid;gap:8px;margin:10px 0 14px}
.sub-help details{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:10px 14px}
.sub-help summary{cursor:pointer;font-weight:600;font-size:.9rem}
.sub-help ol{margin:8px 0 2px 18px;padding:0;color:var(--ink-soft);font-size:.88rem}
.sub-help li{margin:4px 0}
.sub-help code{background:var(--soft);padding:1px 6px;border-radius:6px;font-size:.82rem;word-break:break-all}
.cal-cell{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;gap:1px;padding:4px 2px}
.cal-day{font-size:.84rem;line-height:1.15;font-variant-numeric:tabular-nums}
.cal-hol{font-size:.56rem;line-height:1.1;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--accent);font-weight:600}
.cal-note{font-size:.5rem;line-height:1.2;background:#fee2e2;color:#991b1b;border-radius:4px;padding:0 3px;font-weight:700}
.cal-rest .cal-note{background:#fff7e6;color:#8a5a00}
.cal-single .cal-day{font-size:.9rem}
.cal-single .cal-hol{font-size:.62rem}
.cal-year .cal-hol{font-size:.5rem}
.cal-year .cal-note{font-size:.46rem}
"""

JS = """
(function(){
  var els = document.querySelectorAll('[data-countdown]');
  if(!els.length) return;
  var now = new Date(); now.setHours(0,0,0,0);
  els.forEach(function(el){
    var raw = el.getAttribute('data-date');
    if(!raw) return;
    var d = new Date(raw + 'T00:00:00');
    if(isNaN(d.getTime())) return;
    var days = Math.round((d - now) / 86400000);
    if(days < 0){ el.textContent = 'passed'; }
    else if(days === 0){ el.textContent = 'today'; }
    else if(days === 1){ el.textContent = 'tomorrow'; }
    else { el.textContent = 'in ' + days + ' days'; }
  });
})();
(function(){
  var links = document.querySelectorAll('a[href$=".ics"]');
  links.forEach(function(a){
    a.addEventListener('click', function(){
      try {
        if(navigator.sendBeacon){
          navigator.sendBeacon('/ics-count', JSON.stringify({href: a.getAttribute('href') || ''}));
        }
      } catch(e){}
    });
  });
})();
"""

# Homepage calendar: detect visitor country (edge geo → timezone → language) and render a month calendar
HOME_CAL_JS = r"""
(function(){
  var root = document.getElementById('hk-home-cal');
  if (!root) return;
  var body = root.querySelector('[data-cal-body]');
  var titleEl = root.querySelector('[data-cal-title]');
  var countryEl = root.querySelector('[data-cal-country]');
  var linkEl = root.querySelector('[data-cal-link]');
  var today = new Date();
  var state = {
    cc: (root.getAttribute('data-default-country') || 'US').toUpperCase(),
    year: today.getFullYear(),
    month: today.getMonth(),
    name: '', slug: '', data: null, countries: null
  };
  var TZ = {
    'Asia/Shanghai':'CN','Asia/Chongqing':'CN','Asia/Urumqi':'CN','Asia/Harbin':'CN',
    'Asia/Hong_Kong':'HK','Asia/Macau':'MO','Asia/Taipei':'TW','Asia/Tokyo':'JP',
    'Asia/Seoul':'KR','Asia/Singapore':'SG','Asia/Kuala_Lumpur':'MY','Asia/Bangkok':'TH',
    'Asia/Jakarta':'ID','Asia/Manila':'PH','Asia/Kolkata':'IN','Asia/Calcutta':'IN',
    'Asia/Karachi':'PK','Asia/Dhaka':'BD','Asia/Dubai':'AE','Asia/Riyadh':'SA',
    'Asia/Jerusalem':'IL','Asia/Istanbul':'TR','Asia/Ho_Chi_Minh':'VN','Asia/Saigon':'VN',
    'Europe/London':'GB','Europe/Dublin':'IE','Europe/Paris':'FR','Europe/Berlin':'DE',
    'Europe/Madrid':'ES','Europe/Rome':'IT','Europe/Amsterdam':'NL','Europe/Brussels':'BE',
    'Europe/Vienna':'AT','Europe/Zurich':'CH','Europe/Lisbon':'PT','Europe/Stockholm':'SE',
    'Europe/Oslo':'NO','Europe/Copenhagen':'DK','Europe/Helsinki':'FI','Europe/Warsaw':'PL',
    'Europe/Prague':'CZ','Europe/Budapest':'HU','Europe/Athens':'GR','Europe/Moscow':'RU',
    'Europe/Kiev':'UA','Europe/Kyiv':'UA','America/New_York':'US','America/Chicago':'US',
    'America/Denver':'US','America/Los_Angeles':'US','America/Toronto':'CA',
    'America/Vancouver':'CA','America/Mexico_City':'MX','America/Sao_Paulo':'BR',
    'America/Argentina/Buenos_Aires':'AR','America/Bogota':'CO','America/Lima':'PE',
    'Australia/Sydney':'AU','Australia/Melbourne':'AU','Australia/Brisbane':'AU',
    'Pacific/Auckland':'NZ','Africa/Johannesburg':'ZA','Africa/Cairo':'EG',
    'Africa/Lagos':'NG','Africa/Nairobi':'KE'
  };
  var LOC = {
    'zh-cn':'CN','zh-sg':'SG','zh-tw':'TW','zh-hk':'HK','zh':'CN','ja':'JP','ko':'KR',
    'th':'TH','vi':'VN','id':'ID','ms':'MY','en-gb':'GB','en-au':'AU','en-ca':'CA',
    'en-nz':'NZ','en-ie':'IE','en-in':'IN','de':'DE','fr':'FR','es':'ES','it':'IT',
    'pt':'PT','nl':'NL','pl':'PL','ru':'RU','tr':'TR','ar':'AE','he':'IL'
  };
  function pad(n){ return (n < 10 ? '0' : '') + n; }
  function key(d){ return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function monthLabel(){
    var loc = (window.HKI18N ? window.HKI18N.locale() : undefined);
    return new Date(state.year, state.month, 1).toLocaleDateString(loc, { month: 'long', year: 'numeric' });
  }
  function holidayMap(){
    var map = {};
    ((state.data && state.data.holidays) || []).forEach(function (h) {
      map[h.date] = { name: h.name, localName: h.localName || h.name };
    });
    return map;
  }
  function cnMaps(){
    var rest = {}, work = {};
    var sup = state.data && state.data.supplementary;
    if (sup) {
      (sup.rest || []).forEach(function(x){ rest[x.date] = x.name || ''; });
      (sup.work || []).forEach(function(x){ work[x.date] = x.name || ''; });
    }
    return { rest: rest, work: work };
  }
  function render(){
    if (!body) return;
    var hol = holidayMap(), cn = cnMaps();
    var first = new Date(state.year, state.month, 1);
    var start = (first.getDay() + 6) % 7;
    var days = new Date(state.year, state.month + 1, 0).getDate();
    var heads = ((window.HKI18N ? window.HKI18N.t('cal.week') : 'M,T,W,T,F,S,S'))
      .split(',').map(function (w) { return '<span>' + w + '</span>'; }).join('');
    var html = '<div class="cal-head">' + heads + '</div><div class="cal-grid">';
    var i;
    for (i = 0; i < start; i++) html += '<div class="cal-cell muted"></div>';
    for (i = 1; i <= days; i++) {
      var d = new Date(state.year, state.month, i);
      var k = key(d), cls = 'cal-cell';
      if (d.getDay() === 0 || d.getDay() === 6) cls += ' cal-weekend';
      var info = hol[k];
      if (info) cls += ' cal-holiday';
      if (cn.rest[k]) cls += ' cal-rest';
      if (cn.work[k]) cls += ' cal-makeup';
      var note = cn.work[k] ? '补班' : (cn.rest[k] ? '调休' : '');
      var label = '';
      if (info) {
        var isZh = window.HKI18N && window.HKI18N.lang() === 'zh';
        label = (isZh && info.localName && info.localName !== info.name) ? info.localName : info.name;
      }
      if (!label) label = note;
      if (!label && cn.rest[k]) label = cn.rest[k];
      if (!label && cn.work[k]) label = cn.work[k];
      var safeLabel = label.replace(/"/g, '&quot;');
      var labelHtml = label ? '<span class="cal-hol" title="' + safeLabel + '">' + safeLabel + '</span>' : '';
      var noteHtml = note ? '<span class="cal-note">' + note + '</span>' : '';
      html += '<div class="' + cls + '" data-date="' + k + '" data-hol="' +
        (info ? info.name.replace(/"/g, '&quot;') : '') + '" data-note="' + note +
        '" title="' + safeLabel + '"><span class="cal-day">' + i + '</span>' + labelHtml + noteHtml + '</div>';
    }
    html += '</div>';
    var listItems = [];
    Object.keys(hol).sort().forEach(function (k) {
      var d = new Date(k + 'T00:00:00');
      if (d.getFullYear() === state.year && d.getMonth() === state.month) {
        var info2 = hol[k];
        var isZh2 = window.HKI18N && window.HKI18N.lang() === 'zh';
        var nm = (isZh2 && info2.localName && info2.localName !== info2.name) ? info2.localName : info2.name;
        listItems.push('<li><span class="cal-date">' + d.getDate() + ' ' +
          d.toLocaleDateString(undefined, { month: 'short' }) + '</span>' + nm + '</li>');
      }
    });
    if (listItems.length) html += '<ul class="cal-list">' + listItems.join('') + '</ul>';
    body.innerHTML = html;
    if (titleEl) titleEl.textContent = monthLabel();
  }
  function loadYear(cb){
    fetch('/api/v1/holidays/' + state.cc + '/' + state.year + '.json')
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ state.data = d; if (cb) cb(); })
      .catch(function(){ state.data = null; if (cb) cb(); });
  }
  function setCountry(cc){
    var info = state.countries && state.countries[cc];
    if (!info) { info = state.countries && state.countries[state.cc]; }
    if (!info) return;
    state.cc = info.code; state.name = info.name; state.slug = info.slug;
    if (countryEl) countryEl.textContent = info.name;
    if (linkEl) linkEl.href = '/' + info.slug + '/index.html';
    var cta = document.querySelector('[data-home-country-cta]');
    if (cta) {
      var focusYear = today.getFullYear() + 1;
      cta.href = '/' + info.slug + '/' + focusYear + '/index.html';
      cta.textContent = info.name + ' holidays';
    }
    loadYear(render);
  }
  function guess(){
    try {
      var tz = (Intl.DateTimeFormat().resolvedOptions().timeZone || '');
      if (TZ[tz]) return TZ[tz];
    } catch (e) {}
    var lang = (navigator.language || '').toLowerCase();
    if (LOC[lang]) return LOC[lang];
    var base = lang.split('-')[0];
    if (LOC[base]) return LOC[base];
    if (lang === 'en-us') return 'US';
    return 'US';
  }
  function init(){
    Promise.all([
      fetch('/api/v1/countries.json').then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
        var map = {};
        ((d && d.countries) || []).forEach(function(c){ map[c.code] = c; });
        return map;
      }).catch(function(){ return null; }),
      fetch('/geo').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
    ]).then(function(res){
      state.countries = res[0] || {};
      var geo = res[1] || {};
      var cc = (geo.country || '').toUpperCase();
      if (!state.countries[cc]) cc = guess();
      if (!state.countries[cc]) cc = 'US';
      setCountry(cc);
    });
  }
  var prev = root.querySelector('[data-cal-prev]');
  var next = root.querySelector('[data-cal-next]');
  if (prev) prev.addEventListener('click', function(){
    state.month--; if (state.month < 0) { state.month = 11; state.year--; loadYear(render); } else { render(); }
  });
  if (next) next.addEventListener('click', function(){
    state.month++; if (state.month > 11) { state.month = 0; state.year++; loadYear(render); } else { render(); }
  });
  document.addEventListener('hk-lang-changed', function(){ render(); });
  init();
})();
"""

HOME_NEXT_JS = r"""
(function(){
  var root = document.getElementById('hk-home-next');
  if (!root) return;
  var MAP = window.HK_NEXT || {};
  var nameEl = root.querySelector('[data-hn-name]');
  var dateEl = root.querySelector('[data-hn-date]');
  var daysEl = root.querySelector('[data-hn-days]');
  var barEl = root.querySelector('[data-hn-bar]');
  var linkEl = root.querySelector('[data-hn-link]');
  function apply(cc){
    var m = MAP[cc];
    if (!m) return;
    var when = new Date(m.d + 'T00:00:00');
    var now = new Date();
    now.setHours(0, 0, 0, 0);
    var days = Math.max(0, Math.round((when - now) / 86400000));
    if (nameEl) nameEl.textContent = m.n;
    if (dateEl) dateEl.textContent = when.toLocaleDateString(undefined, {year:'numeric', month:'short', day:'numeric'}) + ' · ' + (m.cn || cc);
    if (daysEl) daysEl.textContent = String(days);
    if (barEl) barEl.style.width = Math.max(4, Math.min(100, Math.round(100 - days / 365 * 100))) + '%';
    if (linkEl && m.s) linkEl.setAttribute('href', m.s + '/index.html');
    root.setAttribute('data-country', cc);
  }
  fetch('/geo').then(function(r){ return r.ok ? r.json() : null; }).then(function(g){
    if (g && g.country && MAP[g.country]) apply(g.country);
  }).catch(function(){});
})();
"""

HOME_COMPARE_JS = r"""
(function(){
  var data = window.HK_COMPARE;
  if (!data || !data.countries || !data.countries.length) return;
  var root = document.getElementById('hk-compare');
  if (!root) return;
  var selectA = root.querySelector('[data-cm-a]');
  var selectB = root.querySelector('[data-cm-b]');
  var out = root.querySelector('[data-cm-out]');
  var by = {};
  data.countries.forEach(function(c){ by[c.c] = c; });
  function opt(c){
    var o = document.createElement('option');
    o.value = c.c; o.textContent = c.n + ' (' + c.y + ')';
    return o;
  }
  var sorted = data.countries.slice().sort(function(x, y){ return x.n.localeCompare(y.n); });
  sorted.forEach(function(c){ selectA.appendChild(opt(c)); selectB.appendChild(opt(c)); });
  function escHtml(t){
    return String(t == null ? '' : t).replace(/[&<>"]/g, function(ch){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch];
    });
  }
  function fmt(iso){
    if (!iso) return null;
    var d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, {month:'short', day:'numeric'});
  }
  function hlist(c){
    return (c.h || []).map(function(row){
      return { d: row[0], n: row[1] || '', l: row[2] || row[1] || '' };
    });
  }
  function months(list){
    var m = [0,0,0,0,0,0,0,0,0,0,0,0];
    list.forEach(function(row){ m[parseInt(row.d.slice(5, 7), 10) - 1] += 1; });
    return m;
  }
  function weekend(list){
    return list.filter(function(row){
      var w = new Date(row.d + 'T00:00:00').getDay();
      return w === 0 || w === 6;
    }).length;
  }
  function norm(name){ return String(name || '').toLowerCase().replace(/\s+/g, ' ').trim(); }
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var COLORS = ['#34d399', '#f59e0b'];
  function render(){
    var a = by[selectA.value], b = by[selectB.value];
    if (!a || !b) return;
    if (a.c === b.c) { out.innerHTML = '<p class="cm-note">Pick two different countries.</p>'; return; }
    var la = hlist(a), lb = hlist(b);
    var ma = months(la), mb = months(lb);
    var peak = Math.max.apply(null, ma.concat(mb).concat([1]));
    var datesA = {}, datesB = {};
    la.forEach(function(r){ datesA[r.d] = r; });
    lb.forEach(function(r){ datesB[r.d] = r; });
    var strict = 0;
    Object.keys(datesA).forEach(function(d){ if (datesB[d]) strict += 1; });
    function barCol(arr, cls){
      return arr.map(function(v){
        var h = v ? Math.max(7, Math.round(v / peak * 100)) : 0;
        return '<i class="' + cls + '" style="height:' + h + '%"></i>';
      }).join('');
    }
    var barA = barCol(ma, 'a'), barB = barCol(mb, 'b');
    function barGroups(){
      var out = '';
      for (var k = 0; k < 12; k++) {
        out += '<div class="cm-m"><i class="a" style="height:' + barH(ma[k]) + '%"></i>'
          + '<i class="b" style="height:' + barH(mb[k]) + '%"></i></div>';
      }
      return out;
    }
    function barH(v){
      return v ? Math.max(7, Math.round(v / peak * 100)) : 0;
    }
    var xlab = MONTHS.map(function(t){ return '<span>' + t + '</span>'; }).join('');
    var rows = '';
    var seenA = {}, seenB = {};
    la.forEach(function(r){ seenA[norm(r.n)] = r; });
    lb.forEach(function(r){ seenB[norm(r.n)] = r; });
    var names = {};
    function labelOf(r){ return r.l && r.l !== r.n ? r.n + ' · ' + r.l : r.n; }
    la.forEach(function(r){ names[norm(r.n)] = labelOf(r); });
    lb.forEach(function(r){ names[norm(r.n)] = names[norm(r.n)] || labelOf(r); });
    var keys = Object.keys(names).sort();
    var onlyA = 0, onlyB = 0, both = 0;
    keys.forEach(function(k){
      var ra = seenA[k], rb = seenB[k];
      if (ra && rb) both += 1;
      else if (ra) onlyA += 1;
      else onlyB += 1;
      var label = escHtml(names[k]);
      var ca = ra ? '<td>' + fmt(ra.d) + '</td>' : '<td class="miss">—</td>';
      var cb = rb ? '<td>' + fmt(rb.d) + '</td>' : '<td class="miss">—</td>';
      rows += '<tr><td>' + label + '</td>' + ca + cb + '</tr>';
    });
    if (keys.length > 40) {
      rows = rows.split('</tr>').slice(0, 40).join('</tr>') + '</tr>';
    }
    var wa = weekend(la), wb = weekend(lb);
    out.innerHTML =
      '<div class="kpi-row">' +
        '<div class="kpi"><span class="kpi-ico">🎉</span><span class="kpi-b"><span class="kpi-n" data-static="' + la.length + '">' + la.length + '</span>' +
          '<span class="kpi-l">' + escHtml(a.n) + ' holidays</span></span></div>' +
        '<div class="kpi"><span class="kpi-ico">🎊</span><span class="kpi-b"><span class="kpi-n" data-static="' + lb.length + '">' + lb.length + '</span>' +
          '<span class="kpi-l">' + escHtml(b.n) + ' holidays</span></span></div>' +
        '<div class="kpi"><span class="kpi-ico">🎯</span><span class="kpi-b"><span class="kpi-n" data-static="' + both + '">' + both + '</span>' +
          '<span class="kpi-l">same-name holidays</span></span></div>' +
      '</div>' +
      '<div class="cm-card"><h2>Holidays by month</h2>' +
        '<p class="cm-sub">' + escHtml(a.n) + ' vs ' + escHtml(b.n) + ' in ' + a.y + ' — how the holidays spread across the year.</p>' +
        '<div class="cm-bars">' + barGroups() + '</div>' +
        '<div class="cm-x">' + xlab + '</div>' +
        '<div class="vz-legend"><span><i style="background:' + COLORS[0] + '"></i>' + escHtml(a.n) + '</span>' +
          '<span><i style="background:' + COLORS[1] + '"></i>' + escHtml(b.n) + '</span>' +
          '<span>Weekend holidays: ' + wa + ' vs ' + wb + ' · same date: ' + strict + '</span></div>' +
      '</div>' +
      '<div class="cm-card"><h2>Key holidays side by side</h2>' +
        '<p class="cm-sub">' + both + ' shared by name · ' + onlyA + ' only in ' + escHtml(a.n) + ' · ' + onlyB + ' only in ' + escHtml(b.n) + '.</p>' +
        '<table class="cm-table"><thead><tr><th>Holiday</th><th>' + escHtml(a.c) + '</th><th>' + escHtml(b.c) + '</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table>' +
      '</div>';
    var url = new URL(window.location.href);
    url.searchParams.set('a', a.c);
    url.searchParams.set('b', b.c);
    history.replaceState(null, '', url.pathname + '?' + url.searchParams.toString());
  }
  function pickRandom(exclude){
    var pool = data.countries.filter(function(c){ return c.c !== exclude; });
    return pool[Math.floor(Math.random() * pool.length)].c;
  }
  selectA.addEventListener('change', render);
  selectB.addEventListener('change', render);
  var qs = new URLSearchParams(window.location.search);
  var qa = qs.get('a'), qb = qs.get('b');
  if (qa && by[qa]) selectA.value = qa; else selectA.value = (by.US ? 'US' : sorted[0].c);
  if (qb && by[qb] && qb !== selectA.value) selectB.value = qb;
  else selectB.value = pickRandom(selectA.value);
  render();
  fetch('/geo').then(function(r){ return r.ok ? r.json() : null; }).then(function(g){
    if (!g || !g.country || !by[g.country]) return;
    if (qs.get('a')) return;
    if (g.country === selectB.value) selectB.value = pickRandom(g.country);
    selectA.value = g.country;
    render();
  }).catch(function(){});
})();
"""

# UI i18n (chrome strings only; holiday names stay in their original/local form)
I18N_JS = r"""
(function(){
  var D = {
    en: {
      'nav.countries':'Countries','nav.guides':'Holiday guides',
      'nav.lw':'Long weekends','nav.countdowns':'Countdowns',
      'nav.compare':'Compare','nav.api':'API',
      'hero.eyebrow':'Public holidays · long weekends','hero.title':'Plan your year around long weekends.',
      'hero.lede':'Every public holiday, the longest breaks you can build around them, and one-click calendar subscriptions.',
      'hero.cta.browse':'Browse countries',
      'stats.countries':'Countries','stats.holidays':'Holidays','stats.years':'Years covered',
      'sec.browse':'Browse countries','sec.browse.sub':'Every holiday, long weekend and bridge day, country by country.',
      'sec.how':'How HolidayKit works',
      'how.1.t':'1 · Pick a country','how.1.p':'See every official public holiday, including regional ones.',
      'how.2.t':'2 · Find the long weekend','how.2.p':'Bridge days show how much leave turns a holiday into 4–6 days off.',
      'how.3.t':'3 · Add it to your calendar','how.3.p':'One .ics link for Google Calendar, Apple Calendar and Outlook.',
      'cal.open':'Open full calendar','cal.week':'M,T,W,T,F,S,S',
      'foot.explore':'Explore','foot.developers':'Developers','foot.data':'Data',
      'foot.all':'All countries','foot.school':'School holidays','foot.embed':'Embed widget',
      'foot.premium':'Premium','foot.about':'About & sources','foot.privacy':'Privacy',
      'foot.note':'Data from open sources, cross-checked against official announcements.',
      'cta.browse':'Browse countries'
    },
    zh: {
      'nav.countries':'国家','nav.guides':'节日指南',
      'nav.lw':'长周末','nav.countdowns':'倒计时',
      'nav.compare':'国家对比','nav.api':'API',
      'hero.eyebrow':'公共假期 · 长周末','hero.title':'围绕长周末规划你的一年。',
      'hero.lede':'每个国家的公共假期、能拼出的最长假期，以及一键订阅日历。',
      'hero.cta.browse':'浏览国家',
      'stats.countries':'国家','stats.holidays':'假期','stats.years':'覆盖年份',
      'sec.browse':'浏览国家','sec.browse.sub':'按国家查看每个公共假期、长周末与桥假。',
      'sec.how':'HolidayKit 怎么用',
      'how.1.t':'1 · 选择国家','how.1.p':'查看全部法定假期，包括地区性假期。',
      'how.2.t':'2 · 找到长周末','how.2.p':'桥假告诉你请几天假能连休 4–6 天。',
      'how.3.t':'3 · 加入日历','how.3.p':'一个 .ics 链接支持 Google、Apple、Outlook 日历。',
      'cal.open':'打开完整日历','cal.week':'一,二,三,四,五,六,日',
      'foot.explore':'探索','foot.developers':'开发者','foot.data':'数据',
      'foot.all':'全部国家','foot.school':'学校假期','foot.embed':'嵌入组件',
      'foot.premium':'会员','foot.about':'关于与数据来源','foot.privacy':'隐私政策',
      'foot.note':'数据来自公开来源，并对照官方公告核对。',
      'cta.browse':'浏览国家'
    },
    ja: {
      'nav.countries':'国一覧','nav.guides':'祝日ガイド',
      'nav.lw':'連休','nav.countdowns':'カウントダウン',
      'nav.compare':'国比較','nav.api':'API',
      'hero.eyebrow':'祝日 · 長い週末','hero.title':'長い週末を中心に一年を計画しよう。',
      'hero.lede':'各国の祝日、作れる最長の連休、ワンクリックのカレンダー購読。',
      'hero.cta.browse':'国を見る',
      'stats.countries':'国','stats.holidays':'祝日','stats.years':'対象年',
      'sec.browse':'国一覧','sec.browse.sub':'国ごとに祝日・長い週末・橋渡し休暇を確認。',
      'sec.how':'HolidayKit の使い方',
      'how.1.t':'1 · 国を選ぶ','how.1.p':'地域ごとの祝日も含めて確認できます。',
      'how.2.t':'2 · 長い週末を探す','how.2.p':'有給を何日使うと 4〜6 連休になるかが分かります。',
      'how.3.t':'3 · カレンダーに追加','how.3.p':'1 つの .ics リンクで Google / Apple / Outlook に対応。',
      'cal.open':'カレンダーを開く','cal.week':'月,火,水,木,金,土,日',
      'foot.explore':'探索','foot.developers':'開発者','foot.data':'データ',
      'foot.all':'すべての国','foot.school':'学校休暇','foot.embed':'埋め込み',
      'foot.premium':'プレミアム','foot.about':'概要と出典','foot.privacy':'プライバシー',
      'foot.note':'データは公開情報を基に公式発表と照合しています。',
      'cta.browse':'国を見る'
    },
    ko: {
      'nav.countries':'국가','nav.guides':'공휴일 가이드',
      'nav.lw':'연휴','nav.countdowns':'카운트다운',
      'nav.compare':'국가 비교','nav.api':'API',
      'hero.eyebrow':'공휴일 · 긴 주말','hero.title':'긴 주말 중심으로 한 해를 계획하세요.',
      'hero.lede':'모든 공휴일, 만들 수 있는 가장 긴 연휴, 원클릭 캘린더 구독.',
      'hero.cta.browse':'국가 보기',
      'stats.countries':'국가','stats.holidays':'공휴일','stats.years':'대상 연도',
      'sec.browse':'국가 목록','sec.browse.sub':'국가별 공휴일·긴 주말·징검다리 휴일을 확인하세요.',
      'sec.how':'HolidayKit 사용법',
      'how.1.t':'1 · 국가 선택','how.1.p':'지역별 공휴일까지 모두 확인할 수 있습니다.',
      'how.2.t':'2 · 긴 주말 찾기','how.2.p':'연차 며칠로 4~6일 연휴를 만들 수 있는지 보여줍니다.',
      'how.3.t':'3 · 캘린더에 추가','how.3.p':'하나의 .ics 링크로 Google·Apple·Outlook 지원.',
      'cal.open':'전체 캘린더 열기','cal.week':'월,화,수,목,금,토,일',
      'foot.explore':'둘러보기','foot.developers':'개발자','foot.data':'데이터',
      'foot.all':'모든 국가','foot.school':'방학','foot.embed':'임베드',
      'foot.premium':'프리미엄','foot.about':'소개 및 출처','foot.privacy':'개인정보',
      'foot.note':'공개 데이터와 공식 발표를 대조했습니다.',
      'cta.browse':'국가 보기'
    },
    es: {
      'nav.countries':'Países','nav.guides':'Guías de festivos',
      'nav.lw':'Fines de semana largos','nav.countdowns':'Cuentas atrás',
      'nav.compare':'Comparar','nav.api':'API',
      'hero.eyebrow':'Días festivos · fines de semana largos',
      'hero.title':'Planifica tu año según los fines de semana largos.',
      'hero.lede':'Todos los días festivos, los descansos más largos y suscripción al calendario en un clic.',
      'hero.cta.browse':'Ver países',
      'stats.countries':'Países','stats.holidays':'Festivos','stats.years':'Años',
      'sec.browse':'Países','sec.browse.sub':'Cada festivo, fin de semana largo y puente, país por país.',
      'sec.how':'Cómo funciona HolidayKit',
      'how.1.t':'1 · Elige un país','how.1.p':'Todos los festivos oficiales, incluidos los regionales.',
      'how.2.t':'2 · Encuentra el fin de semana largo','how.2.p':'Los puentes muestran cuántos días de permiso dan 4–6 días libres.',
      'how.3.t':'3 · Añádelo a tu calendario','how.3.p':'Un enlace .ics para Google Calendar, Apple Calendar y Outlook.',
      'cal.open':'Abrir calendario completo','cal.week':'L,M,X,J,V,S,D',
      'foot.explore':'Explorar','foot.developers':'Desarrolladores','foot.data':'Datos',
      'foot.all':'Todos los países','foot.school':'Vacaciones escolares','foot.embed':'Widget',
      'foot.premium':'Premium','foot.about':'Acerca de y fuentes','foot.privacy':'Privacidad',
      'foot.note':'Datos de fuentes abiertas, verificados con anuncios oficiales.',
      'cta.browse':'Ver países'
    },
    fr: {
      'nav.countries':'Pays','nav.guides':'Guides des fêtes',
      'nav.lw':'Longs week-ends','nav.countdowns':'Comptes à rebours',
      'nav.compare':'Comparer','nav.api':'API',
      'hero.eyebrow':'Jours fériés · longs week-ends',
      'hero.title':'Planifiez votre année autour des longs week-ends.',
      'hero.lede':'Tous les jours fériés, les plus longues pauses et un abonnement calendrier en un clic.',
      'hero.cta.browse':'Voir les pays',
      'stats.countries':'Pays','stats.holidays':'Jours fériés','stats.years':'Années',
      'sec.browse':'Pays','sec.browse.sub':'Chaque férié, long week-end et pont, pays par pays.',
      'sec.how':'Comment fonctionne HolidayKit',
      'how.1.t':'1 · Choisissez un pays','how.1.p':'Tous les jours fériés, y compris régionaux.',
      'how.2.t':'2 · Trouvez le long week-end','how.2.p':'Les ponts montrent combien de congés donnent 4 à 6 jours.',
      'how.3.t':'3 · Ajoutez-le à votre calendrier','how.3.p':'Un lien .ics pour Google, Apple et Outlook.',
      'cal.open':'Ouvrir le calendrier','cal.week':'L,M,M,J,V,S,D',
      'foot.explore':'Explorer','foot.developers':'Développeurs','foot.data':'Données',
      'foot.all':'Tous les pays','foot.school':'Vacances scolaires','foot.embed':'Widget',
      'foot.premium':'Premium','foot.about':'À propos et sources','foot.privacy':'Confidentialité',
      'foot.note':'Données ouvertes, recoupées avec les annonces officielles.',
      'cta.browse':'Voir les pays'
    },
    de: {
      'nav.countries':'Länder','nav.guides':'Feiertags-Guides',
      'nav.lw':'Lange Wochenenden','nav.countdowns':'Countdowns',
      'nav.compare':'Vergleichen','nav.api':'API',
      'hero.eyebrow':'Feiertage · lange Wochenenden',
      'hero.title':'Plane dein Jahr um lange Wochenenden.',
      'hero.lede':'Alle Feiertage, die längsten Pausen und Kalender-Abo mit einem Klick.',
      'hero.cta.browse':'Länder ansehen',
      'stats.countries':'Länder','stats.holidays':'Feiertage','stats.years':'Jahre',
      'sec.browse':'Länder','sec.browse.sub':'Jeder Feiertag, jedes lange Wochenende, Land für Land.',
      'sec.how':'So funktioniert HolidayKit',
      'how.1.t':'1 · Land wählen','how.1.p':'Alle offiziellen Feiertage, auch regionale.',
      'how.2.t':'2 · Langes Wochenende finden','how.2.p':'Brückentage zeigen, wie viel Urlaub 4–6 Tage frei bringt.',
      'how.3.t':'3 · Zum Kalender hinzufügen','how.3.p':'Ein .ics-Link für Google, Apple und Outlook.',
      'cal.open':'Ganzen Kalender öffnen','cal.week':'Mo,Di,Mi,Do,Fr,Sa,So',
      'foot.explore':'Entdecken','foot.developers':'Entwickler','foot.data':'Daten',
      'foot.all':'Alle Länder','foot.school':'Schulferien','foot.embed':'Widget',
      'foot.premium':'Premium','foot.about':'Über uns & Quellen','foot.privacy':'Datenschutz',
      'foot.note':'Offene Daten, abgeglichen mit offiziellen Bekanntmachungen.',
      'cta.browse':'Länder ansehen'
    }
  };
  var LOCALES = { en:'en-US', zh:'zh-CN', ja:'ja-JP', ko:'ko-KR', es:'es-ES', fr:'fr-FR', de:'de-DE' };
  var lang = 'en';
  try { var saved = localStorage.getItem('hk_lang'); if (saved && D[saved]) lang = saved; } catch (e) {}
  function detect(){
    var n = (navigator.language || 'en').toLowerCase();
    var base = n.split('-')[0];
    return D[base] ? base : 'en';
  }
  var forced = window.HK_FORCE_LANG;
  if (forced && D[forced]) { lang = forced; }
  else if (!lang || lang === 'en') { try { var s2 = localStorage.getItem('hk_lang'); if (!s2) lang = detect(); } catch (e) { lang = detect(); } }
  var SUFFIX = { en:'holidays', zh:'假期', ja:'の祝日', ko:'공휴일', es:'festivos', fr:'jours fériés', de:'Feiertage' };
  function t(key){
    var d = D[lang] || D.en;
    if (d[key]) return d[key];
    if (D.en[key]) return D.en[key];
    if (key === 'hero.holidaysSuffix') return SUFFIX[lang] || SUFFIX.en;
    return key;
  }
  function apply(){
    document.documentElement.lang = LOCALES[lang] || 'en-US';
    var nodes = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = t(nodes[i].getAttribute('data-i18n'));
    }
    var sels = document.querySelectorAll('[data-hk-lang]');
    for (var j = 0; j < sels.length; j++) sels[j].value = lang;
    document.dispatchEvent(new CustomEvent('hk-lang-changed', { detail: { lang: lang } }));
  }
  function set(l){ if (!D[l]) return; lang = l; try { localStorage.setItem('hk_lang', l); } catch (e) {} apply(); }
  function locale(){ return LOCALES[lang] || 'en-US'; }
  window.HKI18N = { t: t, apply: apply, set: set, lang: function(){ return lang; }, locale: locale };
  document.addEventListener('DOMContentLoaded', function(){
    apply();
    var sels = document.querySelectorAll('[data-hk-lang]');
    for (var k = 0; k < sels.length; k++) {
      sels[k].addEventListener('change', function(){ set(this.value); });
    }
  });
})();
"""

# Calendar day detail popover (works with server-rendered and JS-rendered cells)
CAL_JS = r"""
(function(){
  var pop = null;
  function ensure(){
    if (pop) return pop;
    pop = document.createElement('div');
    pop.className = 'cal-detail';
    document.body.appendChild(pop);
    return pop;
  }
  function hide(){ if (pop) pop.classList.remove('open'); }
  function fmtDate(iso){
    try {
      var d = new Date(iso + 'T00:00:00');
      var loc = (window.HKI18N ? window.HKI18N.locale() : undefined);
      return d.toLocaleDateString(loc, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) { return iso; }
  }
  function show(cell){
    var el = ensure();
    var iso = cell.getAttribute('data-date');
    var hol = cell.getAttribute('data-hol') || '';
    var note = cell.getAttribute('data-note') || '';
    var days = null;
    try {
      var t = new Date(); t.setHours(0, 0, 0, 0);
      var d = new Date(iso + 'T00:00:00');
      days = Math.round((d - t) / 86400000);
    } catch (e) {}
    var html = '<div class="d-date">' + fmtDate(iso) + '</div>';
    if (hol) html += '<div class="d-hol">' + hol + '</div>';
    if (note) html += '<div class="d-note">' + note + '</div>';
    if (days !== null) {
      var label = days === 0 ? 'Today' : (days > 0 ? ('in ' + days + ' days') : (Math.abs(days) + ' days ago'));
      html += '<div class="d-count">' + label + '</div>';
    }
    el.innerHTML = html;
    el.classList.add('open');
    var r = cell.getBoundingClientRect();
    var top = r.bottom + 8;
    var left = Math.min(r.left, window.innerWidth - 300);
    if (top + 170 > window.innerHeight) top = Math.max(8, r.top - 170);
    el.style.top = Math.max(8, top) + 'px';
    el.style.left = Math.max(8, left) + 'px';
  }
  document.addEventListener('click', function(e){
    var cell = e.target && e.target.closest ? e.target.closest('.cal-cell[data-date]') : null;
    if (cell) { e.preventDefault(); show(cell); return; }
    if (pop && !(e.target && e.target.closest && e.target.closest('.cal-detail'))) hide();
  });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') hide(); });
  window.addEventListener('scroll', hide, true);
})();
""" 


# Premium motion layer: reveal-on-scroll, header elevation, stat count-up
MOTION_JS = r"""
(function(){
  var head = document.querySelector('.site-head');
  function onScroll(){ if (head) head.classList.toggle('scrolled', window.scrollY > 8); }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(en){ if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { rootMargin: '0px 0px -40px 0px', threshold: 0.08 });
  var targets = document.querySelectorAll('.sec, .card, .hero-cal, .cal-month, .tbl-wrap, .activity, .grid > *');
  for (var i = 0; i < targets.length; i++) { targets[i].classList.add('reveal'); io.observe(targets[i]); }
  var nums = document.querySelectorAll('.stat .num');
  if (nums.length) {
    var io2 = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if (!en.isIntersecting) return;
        var el = en.target; io2.unobserve(el);
        var raw = el.textContent.trim();
        if (!/^[0-9][0-9,]*$/.test(raw)) return;
        var txt = raw.replace(/,/g, '');
        var n = parseInt(txt, 10);
        if (isNaN(n) || n > 1000000) return;
        var t0 = performance.now();
        function step(t){
          var p = Math.min(1, (t - t0) / 900);
          el.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))).toLocaleString();
          if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }, { threshold: 0.4 });
    for (var j = 0; j < nums.length; j++) io2.observe(nums[j]);
  }
  // ── data-viz: count-up numbers, growing bars, comparison fills, animated donuts ──
  (function(){
    var vizIO = 'IntersectionObserver' in window ? new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting) { en.target.classList.add('viz-in'); runViz(en.target); vizIO.unobserve(en.target); } });
    }, { threshold: 0.18 }) : null;
    function runViz(el){
      if (el.hasAttribute('data-countup')) {
        var target = parseFloat(el.getAttribute('data-countup')) || 0;
        var dec = parseInt(el.getAttribute('data-dec') || '0', 10) || 0;
        if (reduce) { el.textContent = target.toLocaleString(undefined, {minimumFractionDigits:dec, maximumFractionDigits:dec}); return; }
        var t0 = performance.now();
        function tick(t){
          var p = Math.min(1, (t - t0) / 1100), e = 1 - Math.pow(1 - p, 3);
          el.textContent = (target * e).toLocaleString(undefined, {minimumFractionDigits:dec, maximumFractionDigits:dec});
          if (p < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        return;
      }
      if (el.classList.contains('vz-bars')) {
        var bars = el.querySelectorAll('.bz');
        for (var i = 0; i < bars.length; i++) {
          (function(bar, idx){
            var h = parseFloat(bar.getAttribute('data-h')) || 0;
            if (reduce) { bar.style.height = Math.max(h, 0) + '%'; return; }
            setTimeout(function(){ bar.style.height = Math.max(h, 1) + '%'; }, idx * 45);
          })(bars[i], i);
        }
        return;
      }
      if (el.classList.contains('vz-cmp')) {
        var fills = el.querySelectorAll('.fill');
        for (var f = 0; f < fills.length; f++) {
          (function(fill, idx){
            var w = parseFloat(fill.getAttribute('data-w')) || 0;
            if (reduce) { fill.style.width = w + '%'; return; }
            setTimeout(function(){ fill.style.width = Math.min(w, 100) + '%'; }, idx * 120);
          })(fills[f], f);
        }
        return;
      }
      if (el.hasAttribute('data-donut')) {
        var fg2 = el.querySelector('.fg');
        if (!fg2) return;
        var pct = Math.max(0, Math.min(1, parseFloat(el.getAttribute('data-donut')) || 0));
        var r = parseFloat(fg2.getAttribute('r')) || 50;
        var C = 2 * Math.PI * r;
        fg2.style.strokeDasharray = C;
        if (reduce) { fg2.style.strokeDashoffset = C * (1 - pct); return; }
        fg2.style.strokeDashoffset = C;
        setTimeout(function(){ fg2.style.strokeDashoffset = C * (1 - pct); }, 160);
        return;
      }
    }
    var pending = document.querySelectorAll('[data-countup], .vz-bars, .vz-cmp, [data-donut]');
    for (var p = 0; p < pending.length; p++) {
      if (vizIO) vizIO.observe(pending[p]); else runViz(pending[p]);
    }
  })();
  var ua = navigator.userAgent || '';
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && /Safari/.test(ua));
  var isAndroid = /Android/i.test(ua);
  document.body.className += (isAndroid ? ' is-android' : (isIOS ? ' is-ios' : ' is-desktop'));
  var subDetails = document.querySelectorAll('.sub-help details');
  for (var sd = 0; sd < subDetails.length; sd++) {
    var sm = subDetails[sd].querySelector('summary');
    var smText = sm ? sm.textContent : '';
    var match = (isAndroid && smText.indexOf('Android') >= 0) ||
                (isIOS && (smText.indexOf('iPhone') >= 0 || smText.indexOf('Mac') >= 0));
    subDetails[sd].open = match || (!isAndroid && !isIOS && sd === 0);
  }
  var copyBtns = document.querySelectorAll('[data-copy]');  for (var c = 0; c < copyBtns.length; c++) {
    (function(btn){
      btn.addEventListener('click', function(){
        var text = btn.getAttribute('data-copy');
        function done(){ btn.textContent = 'Copied!'; setTimeout(function(){ btn.textContent = 'Copy .ics link'; }, 1600); }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function(){});
        } else {
          var ta = document.createElement('textarea');
          ta.value = text; document.body.appendChild(ta); ta.select();
          try { document.execCommand('copy'); } catch (e) {}
          ta.parentNode.removeChild(ta); done();
        }
      });
    })(copyBtns[c]);
  }
})();
"""


# ── helpers ────────────────────────────────────────────────────────────────

def esc(value) -> str:
    return html.escape(str(value), quote=True)


def slugify(text: str) -> str:
    out = []
    prev_dash = False
    for ch in str(text).lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def country_name(cc: str) -> str:
    return COUNTRY_NAMES.get(cc, cc)


ICONS = {
    "gift": '<rect x="3" y="8.5" width="18" height="4" rx="1"/><path d="M4.5 12.5V20a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-7.5"/><path d="M12 8.5v13"/><path d="M12 8.5S10.5 3 7.8 3 4.6 6.7 7 7.8s5 .7 5 .7z"/><path d="M12 8.5S13.5 3 16.2 3s3.2 3.7.8 4.8-5 .7-5 .7z"/>',
    "sparkle": '<path d="M12 3.5l1.7 4.6 4.6 1.7-4.6 1.7-1.7 4.6-1.7-4.6L5.7 9.8l4.6-1.7z"/><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
    "beach": '<path d="M3 12a9 9 0 0 1 18 0z"/><path d="M12 12v8.5"/><path d="M9 21h6"/><path d="M12 3v1.4"/>',
    "calendar": '<rect x="3" y="4.5" width="18" height="16" rx="2.5"/><path d="M8 2.5v4M16 2.5v4M3 10h18"/>',
    "calendar-grid": '<rect x="3" y="4.5" width="18" height="16" rx="2.5"/><path d="M8 2.5v4M16 2.5v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01M16 17.5h.01"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7"/><path d="M2.5 21.5h19"/>',
    "target": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.6 2.5 4 5.7 4 9s-1.4 6.5-4 9c-2.6-2.5-4-5.7-4-9s1.4-6.5 4-9z"/>',
    "scale": '<path d="M12 3.5v17M7.5 20.5h9"/><path d="M4 8.5l-1.5 4.5h5z"/><path d="M20 8.5l-1.5 4.5h5z"/><path d="M4 8.5h16"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
    "book": '<path d="M4.5 5.5A2.5 2.5 0 0 1 7 3h12.5v18H7a2.5 2.5 0 0 0-2.5 2.5z"/><path d="M4.5 18.5A2.5 2.5 0 0 1 7 16h12.5"/>',
    "coffee": '<path d="M4 8.5h12.5V15a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"/><path d="M16.5 9.5h2.2a2.6 2.6 0 0 1 0 5.2h-2.2"/><path d="M7 2.5v2.5M11 2.5v2.5M15 2.5v2.5"/>',
    "star": '<path d="M12 3.2l2.7 5.8 6.2.7-4.6 4.2 1.3 6.1-5.6-3.1-5.6 3.1 1.3-6.1L3.1 9.7l6.2-.7z"/>',
    "heart": '<path d="M12 20.2S4 15.6 4 10.4A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 8 2.8c0 5.2-8 9.8-8 9.8z"/>',
    "check": '<path d="M4 12.5l5.2 5.2L20 6.8"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "ban": '<circle cx="12" cy="12" r="9"/><path d="M5.8 5.8l12.4 12.4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l3.4 2"/>',
    "share": '<path d="M12 15V3.5"/><path d="M8 7.5l4-4 4 4"/><path d="M5 12.5v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
}

EMOJI_ICON = {
    "🎉": "gift",
    "🎊": "sparkle",
    "🎯": "target",
    "🏖️": "beach",
    "🏖": "beach",
    "📅": "calendar",
    "🗓️": "calendar-grid",
    "🗓": "calendar-grid",
    "📊": "chart",
    "⚖️": "scale",
    "⚖": "scale",
    "🌍": "globe",
    "🌐": "globe",
    "✨": "sparkle",
    "☕": "coffee",
    "★": "star",
    "♥": "heart",
    "✓": "check",
    "📱": "phone",
    "🎒": "book",
    "📈": "trend",
    "🚫": "ban",
    "⏱️": "clock",
    "⏱": "clock",
    "◷": "clock",
    "⏳": "clock",
    "⌛": "clock",
}


def _svg(name: str, size: str = "1em", js: bool = False) -> str:
    body = ICONS.get(name) or ICONS["sparkle"]
    q = "\x22" if js else '"'
    attrs = (
        f'{q}class={q}ic{q} width={q}{size}{q} height={q}{size}{q} '
        f'viewBox={q}0 0 24 24{q} fill={q}none{q} stroke={q}currentColor{q} '
        f'stroke-width={q}1.7{q} stroke-linecap={q}round{q} stroke-linejoin={q}round{q} '
        f'aria-hidden={q}true{q}'
    )
    return "<svg " + attrs + ">" + body + "</svg>"


def _deemoji_text(html: str, js: bool) -> str:
    for char, name in EMOJI_ICON.items():
        if char in html:
            html = html.replace(char, _svg(name, js=js))
    return html


def deemoji(html: str) -> str:
    """Replace decorative emoji with monochrome inline SVG icons (script-safe)."""
    parts = re.split(r"(<script\b.*?</script>)", html, flags=re.S)
    out = []
    for part in parts:
        if part.startswith("<script"):
            out.append(_deemoji_text(part, js=True))
        else:
            out.append(_deemoji_text(part, js=False))
    return "".join(out)


def flag_emoji(cc: str) -> str:
    """ISO code chip; crisp on every OS (flag emoji do not render on Windows)."""
    code = str(cc or "").upper()
    if len(code) != 2 or not code.isalpha():
        return _svg("globe", "0.95em")
    return code


PAGE_SHARE_JS = r"""
(function(){
  function mk(openFn,label){
    var b=document.createElement('button');
    b.type='button'; b.className='share-fab';
    b.setAttribute('aria-label','Share this page');
    b.innerHTML='<span class="sf-ic" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3.5"/><path d="M8 7.5l4-4 4 4"/><path d="M5 12.5v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg></span><span class="sf-txt">'+label+'</span>';
    b.addEventListener('click', openFn);
    document.body.appendChild(b);
  }
  function fallback(){
    var url=location.href, title=document.title;
    if(navigator.share){ navigator.share({title:title,url:url}).catch(function(){}); return; }
    if(navigator.clipboard){ navigator.clipboard.writeText(url).then(function(){
      var t=document.createElement('div');
      t.textContent='Link copied — share it anywhere.';
      t.style.cssText='position:fixed;left:50%;bottom:110px;transform:translateX(-50%);z-index:99;background:#111;color:#fff;padding:10px 16px;border-radius:999px;font-size:.85rem;opacity:.95';
      document.body.appendChild(t); setTimeout(function(){t.remove();},2200);
    }).catch(function(){}); }
  }
  window.addEventListener('load', function(){
    setTimeout(function(){
      if(document.querySelector('.share-fab')) return;
      var lang=(document.documentElement.lang||'en').slice(0,2);
      var TXT={zh:'分享',ja:'共有',ko:'공유',es:'Compartir',fr:'Partager',de:'Teilen'};
      mk(fallback, TXT[lang]||'Share');
    }, 400);
  });
})();
"""


def next_date_from_rows(rows: list[dict], today: date) -> date | None:
    dates = []
    for row in rows:
        try:
            dates.append(date.fromisoformat(str(row["date"])))
        except (KeyError, ValueError):
            continue
    if not dates:
        return None
    future = sorted(d for d in dates if d >= today)
    return future[0] if future else sorted(dates)[-1]


def ad_unit() -> str:
    """广告位：未配置 AdSense 时输出空占位；配置后输出自适应广告单元。"""
    if not ADSENSE_CLIENT:
        return '<section class="ad" aria-hidden="true"></section>'
    client = esc(ADSENSE_CLIENT)
    return (
        '<section class="ad"><ins class="adsbygoogle" style="display:block;width:100%" '
        f'data-ad-client="ca-{client}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
        "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script></section>"
    )


FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#15161a"/>'
    '<rect x="14" y="18" width="36" height="32" rx="6" fill="none" stroke="#fbfaf7" stroke-width="3"/>'
    '<path d="M14 28h36" stroke="#fbfaf7" stroke-width="3"/>'
    '<path d="M23 14v8M41 14v8" stroke="#fbfaf7" stroke-width="3" stroke-linecap="round"/>'
    '<circle cx="32" cy="38" r="4" fill="#0f6b5c"/>'
    "</svg>"
)


def fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_ABBR[d.month - 1]} {d.year}"


def fmt_weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def fmt_range(start: date, end: date) -> str:
    if start == end:
        return fmt_date(start)
    if start.month == end.month and start.year == end.year:
        return f"{start.day}–{end.day} {MONTHS_ABBR[start.month - 1]} {start.year}"
    return f"{start.day} {MONTHS_ABBR[start.month - 1]} – {end.day} {MONTHS_ABBR[end.month - 1]} {end.year}"


def is_public(row: dict) -> bool:
    types = set(row.get("types") or [])
    return bool(types & {"Public", "Bank"})


def ics_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


# ── long weekend (bridge day) engine ───────────────────────────────────────

def _is_off(day: date, off_days: set[date]) -> bool:
    return day.weekday() >= 5 or day in off_days


def _extend_run(start: date, end: date, off_days: set[date], pto: int, step: int) -> tuple[date, date]:
    """沿 step 方向请假 pto 天，并把请假后新接上的连续休息日一起吞掉。

    返回延伸后的 (start, end)。例如感恩节（周四）向前请 1 天：
    周五是请假日，周六周日随之并入，得到 Thu–Sun 共 4 天。
    """
    cur = start - timedelta(days=1) if step < 0 else end + timedelta(days=1)
    boundary = cur
    used = 0
    guard = 0
    while used < pto and guard < 400:
        guard += 1
        if not _is_off(cur, off_days):
            used += 1
            boundary = cur
        cur += timedelta(days=step)
    while _is_off(cur, off_days) and guard < 800:
        guard += 1
        boundary = cur
        cur += timedelta(days=step)
    if step < 0:
        return boundary, end
    return start, boundary


def compute_long_weekends(rows: list[dict], year: int, include_regional: bool = False) -> list[dict]:
    """返回某年的长周末候选：每个假期所在的连续休息段 + 请假 1/2/3 天可延伸的方案。"""
    off_days = {date.fromisoformat(r["date"]) for r in rows if is_public(r)}
    seeds: dict[date, str] = {}
    for row in rows:
        if not is_public(row):
            continue
        if not include_regional and not row.get("global"):
            continue
        try:
            d = date.fromisoformat(row["date"])
        except ValueError:
            continue
        seeds.setdefault(d, row["name"])

    runs: list[dict] = []
    visited: set[date] = set()
    for holiday in sorted(seeds):
        if holiday.year != year or holiday in visited:
            continue
        start = holiday
        while _is_off(start - timedelta(days=1), off_days):
            start -= timedelta(days=1)
        end = holiday
        while _is_off(end + timedelta(days=1), off_days):
            end += timedelta(days=1)
        span = (end - start).days + 1
        for i in range(span):
            visited.add(start + timedelta(days=i))

        base_total = span
        options = [{"pto": 0, "start": start, "end": end, "total": base_total, "direction": "none"}]
        for pto in (1, 2, 3):
            best = None
            for step, direction in ((-1, "before"), (1, "after")):
                cand_start, cand_end = _extend_run(start, end, off_days, pto, step)
                if cand_start.year != year or cand_end.year != year:
                    continue
                total = (cand_end - cand_start).days + 1
                cand = {
                    "pto": pto,
                    "start": cand_start,
                    "end": cand_end,
                    "total": total,
                    "direction": direction,
                }
                if best is None or cand["total"] > best["total"]:
                    best = cand
            if best and best["total"] > base_total:
                options.append(best)

        runs.append({
            "holiday": holiday,
            "name": seeds[holiday],
            "start": start,
            "end": end,
            "baseTotal": base_total,
            "options": options,
        })

    runs.sort(key=lambda r: (-max(o["total"] for o in r["options"]), r["holiday"]))
    return runs


# ── HTML building blocks ───────────────────────────────────────────────────

def nav_html(base: str) -> str:
    return (
        '<header class="site-head"><div class="wrap head-inner">'
        f'<a class="brand" href="{base}index.html"><span class="brand-mark">◷</span>{SITE_NAME}</a>'
        '<button type="button" class="nav-search" data-search-open aria-label="Search">'
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.9" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/>'
        '<path d="M15.5 15.5L21 21"/></svg><span>Search</span><kbd>⌘K</kbd></button>'
        "<nav>"
        f'<a href="{base}index.html#countries" data-i18n="nav.countries">Countries</a>'
        f'<a href="{base}holidays/index.html" data-i18n="nav.guides">Holiday guides</a>'
        f'<a href="{base}long-weekends/index.html" data-i18n="nav.lw">Long weekends</a>'
        f'<a href="{base}days-until/index.html" data-i18n="nav.countdowns">Countdowns</a>'
        f'<a href="{base}compare/index.html" data-i18n="nav.compare">Compare</a>'
        f'<a href="{base}api/index.html" data-i18n="nav.api">API</a>'
        "</nav>"
        '<select class="lang-select" data-hk-lang aria-label="Language">'
        '<option value="en">EN</option><option value="zh">中文</option>'
        '<option value="ja">日本語</option><option value="ko">한국어</option>'
        '<option value="es">ES</option><option value="fr">FR</option><option value="de">DE</option>'
        "</select>"
        "</div></header>"
    )


def hreflang_links(site_url: str) -> str:
    parts = [f'<link rel="alternate" hreflang="en" href="{site_url}/">']
    for code in HOME_I18N:
        parts.append(f'<link rel="alternate" hreflang="{code}" href="{site_url}/{code}/">')
    parts.append(f'<link rel="alternate" hreflang="x-default" href="{site_url}/">')
    return "".join(parts)


def footer_html(base: str, verified: str) -> str:
    return (
        '<footer class="site-foot"><div class="wrap">'
        '<div class="foot-grid">'
        '<div>'
        f'<div class="foot-brand">{SITE_NAME}</div>'
        f'<p class="muted">Public holidays, long weekends and bridge days for every country. '
        "Free calendar subscriptions and an open JSON API.</p>"
        "</div>"
        '<div><strong data-i18n="foot.explore">Explore</strong>'
        f'<a href="{base}index.html#countries" data-i18n="foot.all">All countries</a>'
        f'<a href="{base}calendar/index.html">Holidays by month</a>'
        f'<a href="{base}long-weekends/index.html" data-i18n="nav.lw">Long weekends</a>'
        f'<a href="{base}holidays/index.html" data-i18n="nav.guides">Holiday guides</a>'
        f'<a href="{base}days-until/index.html" data-i18n="nav.countdowns">Countdowns</a>'
        f'<a href="{base}compare/index.html" data-i18n="nav.compare">Compare countries</a>'
        f'<a href="{base}school-holidays/index.html" data-i18n="foot.school">School holidays</a></div>'
        f'<div><strong data-i18n="foot.developers">Developers</strong>'
        f'<a href="{base}api/index.html" data-i18n="nav.api">Free API</a>'
        f'<a href="{base}embed/index.html" data-i18n="foot.embed">Embed widget</a>'
        '<a href="https://workdaykit.pages.dev">Business days calculator</a>'
        f'<a href="{base}premium/index.html" data-i18n="foot.premium">Premium</a></div>'
        f'<div><strong data-i18n="foot.data">Data</strong>'
        f'<a href="{base}about/index.html" data-i18n="foot.about">About &amp; sources</a>'
        f'<a href="{base}privacy/index.html" data-i18n="foot.privacy">Privacy</a>'
        f'<a href="{base}support/index.html">♥ Support · 打赏</a>'
        '<a href="https://date.nager.at" rel="nofollow noopener" target="_blank">Nager.Date</a></div>'
        "</div>"
        f'<div class="foot-note" data-i18n="foot.note">Data from open sources, cross-checked against official government '
        "announcements. Dates are for planning — always confirm before booking non-refundable travel.</div>"
        "</div></footer>"
    )


SEARCH_CSS = """
.nav-search{display:inline-flex;align-items:center;gap:7px;background:transparent;border:1px solid var(--line);
  border-radius:999px;padding:7px 13px;font-size:.82rem;color:var(--muted);cursor:pointer;font-family:inherit}
.nav-search:hover{color:var(--ink);border-color:var(--ink)}
.nav-search kbd{font-family:inherit;font-size:.7rem;border:1px solid var(--line);border-radius:5px;padding:1px 5px;opacity:.8}
.srch{position:fixed;inset:0;z-index:95;background:rgba(12,16,22,.55);backdrop-filter:blur(6px);display:none;align-items:flex-start;justify-content:center;padding:9vh 16px 16px}
.srch.on{display:flex}
.srch-panel{width:100%;max-width:640px;background:var(--surface,#fff);border:1px solid var(--line);border-radius:16px;
  box-shadow:0 30px 80px rgba(12,16,22,.32);overflow:hidden}
.srch-top{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)}
.srch-top svg{flex:none;opacity:.55}
.srch input{flex:1;border:0;outline:0;background:transparent;font:inherit;font-size:1rem;color:inherit}
.srch-esc{font-size:.72rem;color:var(--muted);border:1px solid var(--line);border-radius:6px;padding:2px 6px}
.srch-list{max-height:56vh;overflow:auto;padding:6px}
.srch-item{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;text-decoration:none;color:inherit;cursor:pointer}
.srch-item:hover,.srch-item.sel{background:rgba(15,23,42,.055)}
.srch-k{font-size:.62rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#0f766e;
  background:rgba(15,118,110,.10);border-radius:6px;padding:3px 7px;flex:none;min-width:58px;text-align:center}
.srch-t{font-size:.95rem;font-weight:600;line-height:1.25}
.srch-s{font-size:.78rem;color:var(--muted)}
.srch-empty{padding:22px 16px;color:var(--muted);font-size:.9rem}
@media(max-width:720px){.nav-search span,.nav-search kbd{display:none}.nav-search{padding:7px 10px}}
"""

SEARCH_JS = r"""
(function(){
  var BASE=window.HK_BASE||'/';
  var idx=null, sel=-1, loading=false;
  var PH={zh:'搜索国家、节日、年份…',ja:'国・祝日・年を検索…',ko:'국가, 공휴일, 연도 검색…',
    es:'Buscar países, festivos, años…',fr:'Rechercher pays, jours fériés, années…',
    de:'Länder, Feiertage, Jahre suchen…'};
  function lang(){return (document.documentElement.lang||'en').slice(0,2);}
  function build(){
    var box=document.createElement('div'); box.className='srch'; box.id='hk-srch';
    box.innerHTML='<div class="srch-panel"><div class="srch-top">'
      +'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/></svg>'
      +'<input type="text" autocomplete="off" spellcheck="false" placeholder="'+(PH[lang()]||'Search countries, holidays, years…')+'">'
      +'<span class="srch-esc">ESC</span></div><div class="srch-list"></div></div>';
    document.body.appendChild(box);
    box.addEventListener('click',function(e){ if(e.target===box) close(); });
    var input=box.querySelector('input');
    input.addEventListener('input',function(){ render(input.value); });
    input.addEventListener('keydown',function(e){
      if(e.key==='Escape'){ close(); }
      else if(e.key==='ArrowDown'){ e.preventDefault(); move(1); }
      else if(e.key==='ArrowUp'){ e.preventDefault(); move(-1); }
      else if(e.key==='Enter'){ e.preventDefault();
        var a=box.querySelector('.srch-item.sel')||box.querySelector('.srch-item');
        if(a) location.href=a.getAttribute('href'); }
    });
    return box;
  }
  function load(cb){
    if(idx){ cb(); return; }
    if(loading) return;
    loading=true;
    fetch(BASE+'search-index.json').then(function(r){return r.json();}).then(function(d){
      idx=d; loading=false; cb();
    }).catch(function(){
      loading=false;
      var box=document.getElementById('hk-srch');
      if(box) box.querySelector('.srch-list').innerHTML='<div class="srch-empty">Search is unavailable right now — browse the country list instead.</div>';
    });
  }
  function score(it,q){
    var t=(it.t||'').toLowerCase(), sub=(it.s||'').toLowerCase();
    if(t===q) return 100;
    if(t.indexOf(q)===0) return 90;
    if(t.indexOf(q)>-1) return 70;
    if(sub.indexOf(q)>-1) return 45;
    var parts=q.split(/\s+/).filter(Boolean), ok=true;
    for(var i=0;i<parts.length;i++){ if(t.indexOf(parts[i])<0 && sub.indexOf(parts[i])<0){ ok=false; break; } }
    return ok?35:0;
  }
  function render(q){
    var box=document.getElementById('hk-srch');
    if(!box) return;
    var list=box.querySelector('.srch-list');
    q=(q||'').trim().toLowerCase();
    if(!idx){ list.innerHTML='<div class="srch-empty">Loading…</div>'; return; }
    var res=idx.map(function(it){ return {it:it, s:q?score(it,q):1}; })
      .filter(function(r){ return r.s>0; })
      .sort(function(a,b){ return b.s-a.s; })
      .slice(0,10);
    if(!res.length){ list.innerHTML='<div class="srch-empty">No matches.</div>'; sel=-1; return; }
    var root=BASE.replace(/[^/]*$/,'');
    list.innerHTML=res.map(function(r){
      return '<a class="srch-item" href="'+root+r.it.u.replace(/^\//,'')+'">'
        +'<span class="srch-k">'+(r.it.k||'page')+'</span><span><span class="srch-t">'+r.it.t
        +'</span><br><span class="srch-s">'+(r.it.s||'')+'</span></span></a>';
    }).join('');
    sel=-1;
  }
  function move(d){
    var nodes=document.querySelectorAll('.srch-item'); if(!nodes.length) return;
    if(sel>=0) nodes[sel].classList.remove('sel');
    sel=(sel+d+nodes.length)%nodes.length;
    nodes[sel].classList.add('sel');
    nodes[sel].scrollIntoView({block:'nearest'});
  }
  function open(){
    var box=document.getElementById('hk-srch')||build();
    box.classList.add('on');
    load(function(){ render(box.querySelector('input').value); });
    box.querySelector('input').focus();
  }
  function close(){
    var box=document.getElementById('hk-srch');
    if(box) box.classList.remove('on');
  }
  window.HK_SEARCH_OPEN=open;
  var _q=new URLSearchParams(location.search).get('q');
  if(_q){ setTimeout(function(){ open(); var i=document.getElementById('hk-srch').querySelector('input'); i.value=_q; render(_q); }, 400); }
  document.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('[data-search-open]'):null;
    if(t){ e.preventDefault(); open(); }
  });
  document.addEventListener('keydown',function(e){
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){ e.preventDefault(); open(); }
    else if(e.key==='/' && !/input|textarea|select/i.test((document.activeElement||{}).tagName||'')){ e.preventDefault(); open(); }
  });
})();
"""


CRUMB_CSS = """
.crumbs{font-size:.78rem;color:var(--muted);margin:2px 0 18px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.crumbs a{color:var(--muted);text-decoration:none;border-bottom:1px solid transparent}
.crumbs a:hover{color:var(--ink);border-bottom-color:currentColor}
.crumbs span[aria-current]{color:var(--ink);font-weight:600}
.crumbs .sep{opacity:.45}
"""


def render_page(*, title: str, description: str, canonical: str, base: str,
                body: str, verified: str, json_ld: str = "",
                cta_href: str = "", cta_label: str = "Browse countries",
                extra_js: str = "", lang_code: str = "en", alternates: str = "",
                robots: str = "index,follow", crumbs: list | None = None) -> str:
    head = (
        f'<!doctype html><html lang="{esc(lang_code)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title>"
        f'<meta name="description" content="{esc(description)}">'
        f'<link rel="canonical" href="{esc(canonical)}">'
        '<meta name="robots" content="' + esc(robots) + '">'
        f'<meta property="og:site_name" content="{SITE_NAME}">'
        f'<meta property="og:title" content="{esc(title)}">'
        f'<meta property="og:description" content="{esc(description)}">'
        '<meta property="og:type" content="website">'
        '<meta name="theme-color" content="#fbfaf7">'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        f'<link rel="sitemap" type="application/xml" href="{base}sitemap.xml">'
        + alternates
        + f"<style>{CSS}{CSS2}{SHARE_CSS}{SEARCH_CSS}{CRUMB_CSS}</style>"
    )
    _site_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": SITE_NAME,
            "url": SITE_URL + "/",
            "description": SITE_TAGLINE,
            "potentialAction": {
                "@type": "SearchAction",
                "target": {"@type": "EntryPoint",
                           "urlTemplate": SITE_URL + "/?q={search_term_string}"},
                "query-input": "required name=search_term_string",
            },
        },
        ensure_ascii=False,
    )
    head += f'<script type="application/ld+json">{_site_ld}</script>'
    if ADSENSE_CLIENT:
        head += (
            f'<meta name="google-adsense-account" content="ca-{esc(ADSENSE_CLIENT)}">'
            '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client=ca-{esc(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>'
        )
    if GOOGLE_VERIFY:
        head += f'<meta name="google-site-verification" content="{esc(GOOGLE_VERIFY)}">'
    if json_ld:
        head += f'<script type="application/ld+json">{json_ld}</script>'
    crumb_html = ""
    if crumbs:
        _items = []
        _parts = []
        for _i, (_lbl, _href) in enumerate(crumbs, start=1):
            _item = {"@type": "ListItem", "position": _i, "name": _lbl}
            if _href:
                _item["item"] = urljoin(canonical, _href)
                _parts.append(f'<a href="{_href}">{esc(_lbl)}</a>')
            else:
                _parts.append(f'<span aria-current="page">{esc(_lbl)}</span>')
            _items.append(_item)
        head += '<script type="application/ld+json">' + json.dumps(
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": _items},
            ensure_ascii=False) + "</script>"
        crumb_html = ('<nav class="crumbs" aria-label="Breadcrumb">'
                      + '<span class="sep">›</span>'.join(_parts) + "</nav>")
    if OG_IMAGE:
        head += (
            f'<meta property="og:image" content="{esc(SITE_URL)}/og-cover.png">'
            '<meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{esc(title)}">'
            f'<meta name="twitter:description" content="{esc(description)}">'
        )
    body = body.replace('<section class="ad">[Ad slot]</section>', ad_unit())
    body = body.replace('<section class="ad">[Ad slot — AdSense / Ezoic]</section>', ad_unit())
    mobile_href = cta_href or (base + "index.html#countries")
    mobile_label = cta_label if cta_href else "Browse countries"
    mobile_attr = "" if cta_href else ' data-i18n="cta.browse"'
    mobile_cta = (
        '<div class="mobile-cta">'
        f'<a class="btn" href="{mobile_href}"{mobile_attr}>{esc(mobile_label)}</a>'
        f'<a class="btn ghost" href="{base}holidays/index.html" data-i18n="nav.guides">Holiday guides</a>'
        "</div>"
    )
    html = (
        head + "</head><body>"
        + nav_html(base)
        + '<main class="wrap">' + crumb_html + body + "</main>"
        + footer_html(base, verified)
        + mobile_cta
        + f"<script>{JS}</script>"
        + (f'<script>window.HK_FORCE_LANG="{esc(lang_code)}";</script>' if lang_code != "en" else "")
        + f"<script>{I18N_JS}</script>"
        + f"<script>{CAL_JS}</script>"
        + f"<script>{MOTION_JS}</script>"
        + (f"<script>{extra_js}</script>" if extra_js else "")
        + f'<script>window.HK_BASE="{base}";</script>'
        + f"<script>{SEARCH_JS}</script>"
        + f"<script>{PAGE_SHARE_JS}</script>"
        + "</body></html>"
    )
    return deemoji(html)


def holiday_table(rows: list[dict]) -> str:
    body = []
    for row in sorted(rows, key=lambda r: r["date"]):
        d = date.fromisoformat(row["date"])
        regional = ""
        if row.get("counties") and not row.get("global"):
            regional = ' <span class="badge">regional</span>'
        local_name = str(row.get("localName") or "")
        local_html = ""
        if local_name and local_name != str(row.get("name") or ""):
            local_html = f' <span class="muted">· {esc(local_name)}</span>'
        body.append(
            "<tr>"
            f"<td>{esc(fmt_date(d))}</td>"
            f"<td>{esc(fmt_weekday(d))}</td>"
            f"<td>{esc(row['name'])}{local_html}{regional}</td>"
            f'<td data-date="{esc(row["date"])}" data-countdown></td>'
            "</tr>"
        )
    return (
        '<div class="tbl-wrap"><table><thead><tr>'
        "<th>Date</th><th>Day</th><th>Holiday</th><th>Countdown</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def long_weekend_table(runs: list[dict]) -> str:
    body = []
    for run in runs:
        options = [o for o in run["options"] if o["pto"] <= 2]
        cheap = any(o["pto"] == 1 and o["total"] >= 4 for o in options)
        if run["baseTotal"] < 3 and not cheap:
            continue
        pills = []
        for opt in options:
            if opt["pto"] == 0:
                pills.append(f'<span class="pill">{opt["total"]} days off, no leave</span>')
            else:
                pills.append(f'<span class="pill">Take {opt["pto"]} day(s) → {opt["total"]} days</span>')
        body.append(
            "<tr>"
            f"<td><strong>{esc(run['name'])}</strong></td>"
            f"<td>{esc(fmt_range(run['start'], run['end']))}</td>"
            f"<td>{run['baseTotal']}</td>"
            f"<td>{''.join(pills)}</td>"
            "</tr>"
        )
    if not body:
        return '<p class="muted">No long weekends found for this year.</p>'
    return (
        '<div class="tbl-wrap"><table><thead><tr>'
        "<th>Holiday</th><th>Days off</th><th>Base days</th><th>Ways to extend</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def long_weekend_cards(runs: list[dict], limit: int = 12) -> str:
    cards: list[str] = []
    for run in runs[:limit]:
        options = [o for o in run["options"] if o["pto"] <= 2]
        cheapest = any(o["pto"] == 1 and o["total"] >= 4 for o in options)
        if run["baseTotal"] < 3 and not cheapest:
            continue
        best = max(options, key=lambda o: (o["total"], -o["pto"]))
        chips = []
        for opt in options:
            if opt["pto"] == 0:
                chips.append(f'<span class="chip">{opt["total"]} days · no leave</span>')
            else:
                chips.append(f'<span class="chip">{opt["pto"]} PTO → {opt["total"]} days</span>')
        cards.append(
            '<article class="lw-card">'
            f'<div class="lw-days">{best["total"]}<span>days off</span></div>'
            f"<h3>{esc(run['name'])}</h3>"
            f'<p class="muted">{esc(fmt_range(run["start"], run["end"]))}</p>'
            '<div class="chips">' + "".join(chips) + "</div>"
            "</article>"
        )
    if not cards:
        return '<p class="muted">No long weekends found for this year.</p>'
    return '<div class="lw-grid">' + "".join(cards) + "</div>"


def month_calendar_html(year: int, rows: list[dict], cn: dict | None = None,
                        prefer_local: bool = False) -> str:
    holidays: dict[date, list[str]] = {}
    labels: dict[date, str] = {}
    for row in rows:
        try:
            day = date.fromisoformat(str(row["date"]))
        except (KeyError, ValueError):
            continue
        if day.year == year:
            holidays.setdefault(day, []).append(str(row["name"]))
            label = str(row.get("localName") or row["name"]) if prefer_local else str(row["name"])
            if label:
                labels.setdefault(day, label)
    rest_days: dict[date, str] = {}
    work_days: dict[date, str] = {}
    if cn:
        for item in cn.get("rest") or []:
            try:
                rest_days[date.fromisoformat(item["date"])] = item.get("name") or ""
            except (KeyError, ValueError):
                continue
        for item in cn.get("work") or []:
            try:
                work_days[date.fromisoformat(item["date"])] = item.get("name") or ""
            except (KeyError, ValueError):
                continue
    months: list[str] = []
    for month in range(1, 13):
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        cells: list[str] = []
        for week in weeks:
            for day in week:
                if day == 0:
                    cells.append('<div class="cal-cell muted"></div>')
                    continue
                d = date(year, month, day)
                cls = "cal-cell"
                if d.weekday() >= 5:
                    cls += " cal-weekend"
                if d in rest_days:
                    cls += " cal-rest"
                if d in holidays:
                    cls += " cal-holiday"
                if d in work_days:
                    cls += " cal-makeup"
                titles = []
                if d in holidays:
                    titles.append(", ".join(holidays[d]))
                if d in rest_days and rest_days[d]:
                    titles.append(f"调休：{rest_days[d]}")
                if d in work_days:
                    titles.append(f"补班：{work_days[d]}")
                note = ""
                if d in work_days:
                    note = "补班"
                elif d in rest_days:
                    note = "调休"
                label = labels.get(d, "")
                if not label and d in rest_days:
                    label = rest_days[d] or "调休"
                if not label and d in work_days:
                    label = work_days[d] or "补班"
                label_html = (
                    f'<span class="cal-hol" title="{esc(label)}">{esc(label)}</span>' if label else ""
                )
                note_html = f'<span class="cal-note">{note}</span>' if note else ""
                cells.append(
                    f'<div class="{cls}" data-date="{d.isoformat()}" '
                    f'data-hol="{esc("; ".join(holidays.get(d, [])))}" data-note="{esc(note)}" '
                    f'title="{esc("; ".join(titles))}">'
                    f'<span class="cal-day">{day}</span>{label_html}{note_html}</div>'
                )
        head = "".join(f"<span>{w}</span>" for w in ["M", "T", "W", "T", "F", "S", "S"])
        month_hols = [
            (d, holidays[d]) for d in sorted(holidays)
            if d.year == year and d.month == month
        ]
        month_list = ""
        if month_hols:
            items = "".join(
                f'<li><span class="cal-date">{d.day} {MONTHS_ABBR[d.month - 1]}</span>'
                f'{esc(", ".join(names))}</li>'
                for d, names in month_hols[:6]
            )
            month_list = '<ul class="cal-list">' + items + "</ul>"
        months.append(
            '<div class="cal-month">'
            f'<div class="cal-title">{calendar.month_name[month]}</div>'
            f'<div class="cal-head">{head}</div>'
            '<div class="cal-grid">' + "".join(cells) + "</div>"
            + month_list + "</div>"
        )
    legend = (
        '<div class="cal-legend"><span class="cal-key cal-holiday-key"></span>Public holiday'
        '<span class="cal-key cal-weekend-key"></span>Weekend'
    )
    if rest_days or work_days:
        legend += (
            '<span class="cal-key cal-rest-key"></span>调休休息'
            '<span class="cal-key cal-makeup-key"></span>补班'
        )
    legend += "</div>"
    return (
        '<section class="sec"><h2>Calendar view</h2>'
        '<p class="sub">Public holidays highlighted, weekends shaded.</p>'
        '<div class="cal-year">' + "".join(months) + "</div>" + legend + "</section>"
    )


def single_month_html(year: int, month: int, rows: list[dict], cn: dict | None = None,
                      prefer_local: bool = False) -> str:
    holidays: dict[date, list[str]] = {}
    labels: dict[date, str] = {}
    for row in rows:
        try:
            day = date.fromisoformat(str(row["date"]))
        except (KeyError, ValueError):
            continue
        holidays.setdefault(day, []).append(str(row["name"]))
        label = str(row.get("localName") or row["name"]) if prefer_local else str(row["name"])
        if label:
            labels.setdefault(day, label)
    rest_days: set[date] = set()
    work_days: set[date] = set()
    if cn:
        for item in cn.get("rest") or []:
            try:
                rest_days.add(date.fromisoformat(item["date"]))
            except (KeyError, ValueError):
                continue
        for item in cn.get("work") or []:
            try:
                work_days.add(date.fromisoformat(item["date"]))
            except (KeyError, ValueError):
                continue
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    cells: list[str] = []
    for week in weeks:
        for day in week:
            if day == 0:
                cells.append('<div class="cal-cell muted"></div>')
                continue
            d = date(year, month, day)
            cls = "cal-cell"
            if d.weekday() >= 5:
                cls += " cal-weekend"
            if d in holidays:
                cls += " cal-holiday"
            if d in rest_days:
                cls += " cal-rest"
            if d in work_days:
                cls += " cal-makeup"
            title = ", ".join(holidays.get(d, []))
            note = "补班" if d in work_days else ("调休" if d in rest_days else "")
            label = labels.get(d, "")
            if note and not label:
                label = note
            label_html = (
                f'<span class="cal-hol" title="{esc(label)}">{esc(label)}</span>' if label else ""
            )
            note_html = f'<span class="cal-note">{note}</span>' if note else ""
            cells.append(
                f'<div class="{cls}" data-date="{d.isoformat()}" '
                f'data-hol="{esc(", ".join(holidays.get(d, [])))}" data-note="{esc(note)}" '
                f'title="{esc(title)}"><span class="cal-day">{day}</span>{label_html}{note_html}</div>'
            )
    head = "".join(f"<span>{w}</span>" for w in ["M", "T", "W", "T", "F", "S", "S"])
    month_hols = [
        (d, holidays[d]) for d in sorted(holidays)
        if d.year == year and d.month == month
    ]
    month_list = ""
    if month_hols:
        items = "".join(
            f'<li><span class="cal-date">{d.day} {MONTHS_ABBR[d.month - 1]}</span>'
            f'{esc(", ".join(names))}</li>'
            for d, names in month_hols[:8]
        )
        month_list = '<ul class="cal-list">' + items + "</ul>"
    return (
        '<div class="cal-head">' + head + "</div>"
        '<div class="cal-grid">' + "".join(cells) + "</div>" + month_list
    )


def faq_block(pairs: list[tuple[str, str]]) -> str:
    items = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in pairs)
    return f'<dl class="faq">{items}</dl>'


def faq_json_ld(pairs: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }
    return json.dumps(data, ensure_ascii=False)


# ── page generators ────────────────────────────────────────────────────────

def build_ics(cc: str, name: str, year: int, rows: list[dict], cn: dict | None = None) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HolidayKit//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(name)} public holidays {year}",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for row in sorted(rows, key=lambda r: r["date"]):
        if not is_public(row):
            continue
        d = date.fromisoformat(row["date"])
        desc = "Public holiday"
        if row.get("counties") and not row.get("global"):
            desc += " (regional: " + ", ".join(row["counties"]) + ")"
        uid = f"{cc}-{row['date']}-{slugify(row['name'])[:40]}@holidaykit"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{ics_escape(row['name'])}",
            f"DESCRIPTION:{ics_escape(desc)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ])
    if cn:
        holiday_dates = {str(row.get("date")) for row in rows}
        extra: list[tuple[str, str, str]] = []
        for item in cn.get("rest") or []:
            if item.get("date") and item["date"] not in holiday_dates:
                extra.append((item["date"], f"{item.get('name') or '调休'}(调休)", "rest"))
        for item in cn.get("work") or []:
            if item.get("date"):
                extra.append((item["date"], f"{item.get('name') or '补班'}(补班上班)", "work"))
        for index, (day, summary, kind) in enumerate(extra):
            try:
                d = date.fromisoformat(day)
            except ValueError:
                continue
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:cn-{kind}-{day}-{index}@holidaykit",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{ics_escape(summary)}",
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def pick_focus_year(years: list[int], today: date) -> int:
    ys = sorted(int(y) for y in years)
    for cand in (today.year + 1, today.year):
        if cand in ys:
            return cand
    return ys[-1] if ys else today.year


def year_order(years: list[int], today: date) -> list[int]:
    ys = sorted(int(y) for y in years)
    focus = pick_focus_year(ys, today)
    return [focus] + [y for y in ys if y > focus] + [y for y in ys if y < focus]


def page_lang_home(lang: str, countries: list[tuple[str, str, str]], by_country,
                   site_url: str, verified: str, today: date) -> str:
    T = HOME_I18N[lang]
    all_years = sorted({y for cc, _, _ in countries for y in by_country[cc]})
    total_holidays = sum(sum(len(by_country[cc][y]) for y in by_country[cc]) for cc, _, _ in countries)
    cards = []
    for cc, name, slug in countries:
        years = sorted(by_country[cc].keys(), reverse=True)
        count = sum(len(by_country[cc][y]) for y in years)
        cards.append(
            f'<a class="card" href="/{slug}/index.html"><div class="flag">{flag_emoji(cc)}</div>'
            f"<h3>{esc(name)}</h3><p>{count} · {', '.join(str(y) for y in years[:3])}</p></a>"
        )
    default_country = next((c for c in countries if c[0] == "US"), countries[0])
    dcc, dname, dslug = default_country
    default_year = pick_focus_year(by_country[dcc].keys(), today)
    default_rows = by_country[dcc].get(today.year) or by_country[dcc][default_year]
    fallback_cal = single_month_html(today.year, today.month, default_rows)
    cal_open = T["cal_open"]
    cal_card = (
        f'<aside class="hero-cal" id="hk-home-cal" data-default-country="{dcc}">'
        '<div class="cal-toolbar">'
        '<button type="button" class="cal-nav-btn" data-cal-prev aria-label="Previous month">‹</button>'
        f'<span class="cal-month-label" data-cal-title>{calendar.month_name[today.month]} {today.year}</span>'
        '<button type="button" class="cal-nav-btn" data-cal-next aria-label="Next month">›</button>'
        "</div>"
        '<div class="cal-single" data-cal-body>' + fallback_cal + "</div>"
        '<div class="cal-foot"><span class="cal-country" data-cal-country>' + esc(dname) + "</span>"
        f'<span>·</span><a data-cal-link href="/{dslug}/index.html">{esc(cal_open)}</a></div>'
        "</aside>"
    )
    year_label = f"{all_years[0]}–{all_years[-1]}" if len(all_years) > 1 else str(all_years[0])
    cta_country = T["cta_country"].replace("{name}", dname)
    how_cards = "".join(
        f'<div class="card"><h3>{esc(t)}</h3><p>{esc(p)}</p></div>' for t, p in T["how_cards"]
    )
    body = (
        '<section class="hero"><div class="hero-inner"><div>'
        f'<p class="eyebrow">{esc(T["eyebrow"])}</p>'
        f'<h1>{esc(T["h1"])}</h1>'
        f'<p class="lede">{esc(T["lede"])}</p>'
        '<div class="cta-row">'
        f'<a class="btn" href="#countries">{esc(T["cta_browse"])}</a>'
        f'<a class="btn ghost" href="/{dslug}/{default_year}/index.html">{esc(cta_country)}</a>'
        "</div>"
        '<div class="stats">'
        f'<div class="stat"><div class="num">{len(countries)}</div><div class="lbl">{esc(T["stats"][0])}</div></div>'
        f'<div class="stat"><div class="num">{total_holidays:,}</div><div class="lbl">{esc(T["stats"][1])}</div></div>'
        f'<div class="stat"><div class="num">{esc(year_label)}</div><div class="lbl">{esc(T["stats"][2])}</div></div>'
        "</div></div>" + cal_card + "</div></section>"
        '<section class="sec" id="countries"><h2>' + esc(T["browse"]) + "</h2>"
        '<p class="sub">' + esc(T["browse_sub"]) + "</p>"
        '<div class="grid">' + "".join(cards) + "</div></section>"
        '<section class="ad">[Ad slot]</section>'
        '<section class="sec"><h2>' + esc(T["how"]) + "</h2>"
        '<div class="activity">' + how_cards + "</div></section>"
        '<section class="ad">[Ad slot]</section>'
    )
    return render_page(
        title=T["title"],
        description=T["desc"],
        canonical=f"{site_url}/{lang}/",
        base="../",
        body=body,
        verified=verified,
        lang_code=lang,
        alternates=hreflang_links(site_url),
        extra_js=HOME_CAL_JS,
    )


def page_index(countries: list[tuple[str, str, str]], by_country, site_url: str, verified: str,
               catalog: dict | None = None, today: date | None = None) -> str:
    cards = []
    for cc, name, slug in countries:
        years = sorted(by_country[cc].keys(), reverse=True)
        count = sum(len(by_country[cc][y]) for y in years)
        fy = pick_focus_year(by_country[cc].keys(), today or date.today())
        fy_rows = by_country[cc].get(fy) or []
        mon = [0] * 12
        for _r in fy_rows:
            try:
                mon[date.fromisoformat(_r["date"]).month - 1] += 1
            except (KeyError, ValueError):
                continue
        _mx = max(mon) or 1
        spark = "".join(f'<i style="height:{max(6, v / _mx * 100):.0f}%"></i>' for v in mon)
        _yr = f"{years[-1]}–{years[0]}" if len(years) > 1 else str(years[0])
        cards.append(
            f'<a class="card" href="{slug}/index.html">'
            f'<div class="flag">{flag_emoji(cc)}</div>'
            f"<h3>{esc(name)}</h3>"
            f'<p>{len(fy_rows)} public holidays in {fy}</p>'
            f'<span class="spark" aria-hidden="true">{spark}</span>'
            f'<p class="card-note">{count} holidays · {_yr}</p>'
            "</a>"
        )
    total_holidays = sum(sum(len(by_country[cc][y]) for y in by_country[cc]) for cc, _, _ in countries)
    all_years = sorted({y for cc, _, _ in countries for y in by_country[cc]})
    year_label = f"{all_years[0]}–{all_years[-1]}" if len(all_years) > 1 else str(all_years[0])
    default_country = next((c for c in countries if c[0] == "US"), countries[0])
    default_cc, default_name, default_slug = default_country
    cal_year = today.year
    cal_month = today.month
    default_year = pick_focus_year(by_country[default_cc].keys(), today)
    default_rows = by_country[default_cc].get(cal_year) or by_country[default_cc][default_year]
    fallback_cal = single_month_html(cal_year, cal_month, default_rows)
    next_map = {}
    for _cc, _cname, _cslug in countries:
        _rows = [r for _y in by_country[_cc] for r in by_country[_cc][_y]]
        _nxt = next_date_from_rows(_rows, today)
        if not _nxt:
            continue
        _nm = next((r.get("name") for r in _rows if r.get("date") == _nxt.isoformat()),
                   "Public holiday")
        next_map[_cc] = {"d": _nxt.isoformat(), "n": _nm, "cn": _cname, "s": _cslug}
    _def_cc = default_cc if default_cc in next_map else next(iter(next_map))
    _def = next_map[_def_cc]
    _def_days = max(0, (date.fromisoformat(_def["d"]) - today).days)
    _def_pct = max(4, min(100, round(100 - _def_days / 365 * 100)))
    feature_card = (
        f'<aside class="hero-cal" id="hk-home-cal" data-default-country="{default_cc}">'
        '<div class="cal-toolbar">'
        '<button type="button" class="cal-nav-btn" data-cal-prev aria-label="Previous month">‹</button>'
        f'<span class="cal-month-label" data-cal-title>{calendar.month_name[cal_month]} {cal_year}</span>'
        '<button type="button" class="cal-nav-btn" data-cal-next aria-label="Next month">›</button>'
        "</div>"
        '<div class="cal-single" data-cal-body>' + fallback_cal + "</div>"
        '<div class="cal-foot"><span class="cal-country" data-cal-country>' + esc(default_name) + "</span>"
        f'<span>·</span><a data-cal-link href="{default_slug}/index.html" data-i18n="cal.open">Open full calendar</a></div>'
        "</aside>"
    )
    next_card = (
        f'<aside class="hero-next" id="hk-home-next" data-country="{_def_cc}">'
        '<div class="hn-top"><span aria-hidden="true">⏳</span><span>下一个假期 · Next holiday</span></div>'
        f'<h3 data-hn-name>{esc(_def["n"])}</h3>'
        f'<div class="hn-date" data-hn-date>{esc(fmt_date(date.fromisoformat(_def["d"])))} · '
        f'{esc(_def["cn"])}</div>'
        '<div class="hn-days">'
        f'<span class="hn-num" data-hn-days>{_def_days}</span>'
        '<span class="hn-lbl">天后 · days to go</span></div>'
        f'<span class="prog" aria-hidden="true"><i data-hn-bar style="width:{_def_pct}%"></i></span>'
        f'<a class="hn-link" data-hn-link href="{_def["s"]}/index.html">打开日历 · Open calendar →</a>'
        "</aside>"
    )
    body = (
        '<section class="hero"><div class="hero-inner"><div>'
        f'<p class="eyebrow">Public holidays · long weekends · {len(countries)} countries</p>'
        '<h1 data-i18n="hero.title">Plan your year around long weekends.</h1>'
        '<p class="lede" data-i18n="hero.lede">Every public holiday, the longest breaks you can build '
        "around them, and one-click calendar subscriptions — for every country and year that matter.</p>"
        '<div class="cta-row">'
        '<a class="btn" href="#countries" data-i18n="hero.cta.browse">Browse countries</a>'
        f'<a class="btn ghost" data-home-country-cta href="{default_slug}/{default_year}/index.html">'
        f"{esc(default_name)} holidays</a>"
        "</div>"
        '<div class="stats">'
        f'<div class="stat"><div class="num">{len(countries)}</div>'
        '<div class="lbl" data-i18n="stats.countries">Countries</div></div>'
        f'<div class="stat"><div class="num">{total_holidays:,}</div>'
        '<div class="lbl" data-i18n="stats.holidays">Holidays</div></div>'
        f'<div class="stat"><div class="num">{esc(year_label)}</div>'
        '<div class="lbl" data-i18n="stats.years">Years covered</div></div>'
        "</div></div><div class=\"hero-side\">" + feature_card + next_card + "</div></div></section>"
        '<section class="sec" id="countries"><h2 data-i18n="sec.browse">Browse countries</h2>'
        '<p class="sub" data-i18n="sec.browse.sub">Every holiday, long weekend and bridge day, country by country.</p>'
        '<div class="grid">' + "".join(cards) + "</div></section>"
        '<section class="ad">[Ad slot]</section>'
        '<section class="sec"><h2 data-i18n="sec.how">How HolidayKit works</h2>'
        '<div class="activity">'
        '<div class="card"><h3 data-i18n="how.1.t">1 · Pick a country</h3>'
        '<p data-i18n="how.1.p">See every official public holiday, including regional ones.</p></div>'
        '<div class="card"><h3 data-i18n="how.2.t">2 · Find the long weekend</h3>'
        '<p data-i18n="how.2.p">Bridge days show how much leave turns a holiday into 4–6 days off.</p></div>'
        '<div class="card"><h3 data-i18n="how.3.t">3 · Add it to your calendar</h3>'
        '<p data-i18n="how.3.p">One .ics link for Google Calendar, Apple Calendar and Outlook.</p></div>'
        "</div></section>"
        '<section class="ad">[Ad slot]</section>'
    )
    faq = [
        ("What is a long weekend?", "A stretch of days off created by a public holiday landing next to a weekend, "
                                    "optionally extended by taking one or two days of leave."),
        ("Can I add holidays to my calendar?", "Yes — every country page has a one-click .ics subscription link that works "
                                              "with Google Calendar, Apple Calendar and Outlook."),
        ("Are the dates official?", "Dates are collected from public sources and cross-checked against official "
                                    "government announcements. Always confirm before booking anything critical."),
    ]
    body += '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
    if catalog and today:
        body += popular_sections(catalog, today)
    return render_page(
        title=f"{SITE_NAME} — Public holidays and long weekends by country",
        description="Browse public holidays, long weekends and bridge days for every country. "
                    "Subscribe to any country's holiday calendar in one click.",
        canonical=f"{site_url}/",
        base="",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
        extra_js=HOME_CAL_JS
        + "window.HK_NEXT="
        + json.dumps(next_map, ensure_ascii=False, separators=(",", ":"))
        + ";"
        + HOME_NEXT_JS,
        alternates=hreflang_links(site_url),
    )


def page_country(cc: str, name: str, slug: str, by_country, site_url: str, verified: str) -> str:
    today = date.today()
    years = sorted(int(y) for y in by_country[cc].keys())
    latest = pick_focus_year(years, today)
    ordered = year_order(years, today)
    share_extra = (
        "window.HK_SHARE="
        + json.dumps(
            share_payload(cc, name, slug, latest, by_country[cc][latest], site_url,
                          cn_year_data(latest) if cc == "CN" else None),
            ensure_ascii=False,
        )
        + ";"
        + SHARE_JS
    )
    all_rows = [r for y in years for r in by_country[cc][y]]
    runs = compute_long_weekends(all_rows, latest)
    top_runs = runs[:6]

    year_nav = "".join(
        f'<a href="{y}/index.html">' + (f'<strong>{y}</strong>' if y == latest else str(y)) + "</a>"
        for y in years
    )
    tables = ""
    for y in ordered[:2]:
        tables += (
            f'<section class="sec"><h2>{esc(name)} public holidays {y}</h2>'
            + holiday_table(by_country[cc][y])
            + f'<p><a class="btn ghost" href="{y}/index.html">Full {y} page</a>'
            + f'<a class="btn" href="calendar-{y}.ics">Add {y} to my calendar</a></p>'
            + "</section>"
        )

    today = date.today()
    nxt = next_date_from_rows(all_rows, today)
    nxt_label = fmt_date(nxt) if nxt else "—"
    next_iso = nxt.isoformat() if nxt else ""
    years_span = f"{years[-1]}–{years[0]}" if len(years) > 1 else str(years[0])
    body = (
        '<section class="hero-country"><div>'
        f'<p class="eyebrow">{esc(cc)} · country calendar</p>'
        f'<h1><span class="flag">{flag_emoji(cc)}</span> {esc(name)} public holidays</h1>'
        f'<p class="lede">All public holidays in {esc(name)} with long weekends, bridge days and '
        "one-click calendar subscriptions.</p>"
        '<div class="chips">'
        f'<span class="chip">{len(all_rows)} public holidays</span>'
        f'<span class="chip">{esc(years_span)}</span>'
        f'<span class="chip">{len(runs)} long weekends in {latest}</span>'
        "</div>"
        '<div class="cta-row" style="margin-top:22px">'
        '<button type="button" class="btn-share-hot" data-share-open>'
        '<span aria-hidden="true">✨</span> 生成分享卡片 · Share card</button>'
        f'<a class="btn" href="calendar-{latest}.ics">Add {latest} to my calendar</a>'
        f'<a class="btn ghost" href="{latest}/long-weekends/index.html">See long weekends</a>'
        "</div></div>"
        '<aside class="next-holiday">'
        f'<div class="flag">{flag_emoji(cc)}</div>'
        "<h3>Next holiday</h3>"
        f'<p class="muted">{esc(nxt_label)}</p>'
        f'<div class="countdown" data-date="{esc(next_iso)}"><span data-countdown></span></div>'
        '<p class="muted">Dates from open sources, verify before booking.</p>'
        "</aside></section>"
        f'<div class="years">{year_nav}</div>'
        f'<section class="sec"><h2>Long weekends in {latest}</h2>'
        "<p>Each row shows a holiday run and how many days of leave turn it into a longer break.</p>"
        + long_weekend_cards(top_runs, 3)
        + f'<p><a class="btn" href="{latest}/long-weekends/index.html">See all long weekends</a></p>'
        "</section>"
        '<section class="ad">[Ad slot]</section>'
        + tables
        + '<section class="sec" id="calendar"><h2>Add these holidays to your calendar</h2>'
        "<p>Subscribe once and the dates update in your calendar. Works with Google Calendar, "
        "Apple Calendar and Outlook.</p>"
        + "".join(
            f'<p><a class="btn" href="calendar-{y}.ics">{esc(name)} {y} (.ics)</a></p>' for y in ordered[:2]
        )
        + "</section>"
    )

    faq = [
        (f"How many public holidays are there in {name}?", f"{name} has {len(by_country[cc][latest])} public "
         f"holidays listed for {latest}, including regional observances."),
        ("What is a bridge day?", "A day of leave taken between a public holiday and a weekend to connect them "
                                  "into a longer break."),
        ("How do I add these holidays to Google Calendar?", "Open Google Calendar, choose 'Other calendars' → "
                                                            "'From URL', and paste the .ics link for the country and year."),
    ]
    if cc == "CN":
        body += cn_summary_html(latest)
    body += subscribe_block(cc, name, slug, latest, site_url)
    body += '<p style="margin:14px 0"><button type="button" class="btn ghost" data-share-open>'
    body += "分享卡片 / Share card</button></p>"
    body += official_source_html(cc)
    body += affiliate_block(name)
    body += embed_block(cc, latest)
    body += '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
    body += '<p><a href="../index.html">← All countries</a></p>'

    return render_page(
        title=f"{name} Public Holidays {latest} — Dates & Long Weekends | {SITE_NAME}",
        description=f"All {name} public holidays for {latest}: dates, weekdays, long weekends and bridge days. "
                    f"Add them to your calendar in one click.",
        canonical=f"{site_url}/{slug}/",
        base="../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
        cta_href=f"calendar-{latest}.ics",
        cta_label=f"Add {latest} to calendar",
        extra_js=share_extra,
        crumbs=[("Home", "../index.html"), ("Countries", "../index.html#countries"), (name, "")],
    )


def page_year(cc: str, name: str, slug: str, year: int, rows: list[dict], runs: list[dict],
              site_url: str, verified: str) -> str:
    cn = cn_year_data(year) if cc == "CN" else None
    share_extra = (
        "window.HK_SHARE="
        + json.dumps(share_payload(cc, name, slug, year, rows, site_url, cn), ensure_ascii=False)
        + ";"
        + SHARE_JS
    )
    monthly = [0] * 12
    weekend_ct = 0
    for r in rows:
        try:
            d = date.fromisoformat(r["date"])
        except (KeyError, ValueError, TypeError):
            continue
        monthly[d.month - 1] += 1
        if d.weekday() >= 5:
            weekend_ct += 1
    peak = max(monthly) or 1
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    bars_html = "".join(
        f'<div class="bz" data-h="{round(c / peak * 100)}" style="height:{max(2, round(c / peak * 100))}%"'
        f' title="{month_labels[i]}: {c}"><b>{c or ""}</b></div>'
        for i, c in enumerate(monthly)
    )
    wk_pct = (weekend_ct / len(rows)) if rows else 0.0
    donut = (
        '<div class="donut-wrap">'
        f'<svg class="vz-donut" data-donut="{wk_pct:.3f}" viewBox="0 0 120 120" aria-hidden="true">'
        '<circle class="bg" cx="60" cy="60" r="50"></circle>'
        '<circle class="fg" cx="60" cy="60" r="50" '
        'style="stroke-dasharray:314.159;stroke-dashoffset:314.159"></circle>'
        "</svg>"
        '<div class="donut-txt">'
        f'<span class="big">{round(wk_pct * 100)}%</span>'
        f'<span class="muted">of {year} holidays fall on a weekend</span></div></div>'
        '<div class="vz-legend"><span><i style="background:#34d399"></i>weekend holiday</span>'
        '<span><i style="background:#94a3b8"></i>weekday holiday</span></div>'
    )
    viz_html = (
        f'<section class="sec viz-sec"><h2><span class="sec-h-ico">📊</span>{year} at a glance</h2>'
        '<div class="kpi-row">'
        f'<div class="kpi"><span class="kpi-ico">🎉</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{len(rows)}">0</span>'
        '<span class="kpi-l">public holidays</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">🏖️</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{len(runs)}">0</span>'
        '<span class="kpi-l">long weekends</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">📅</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{weekend_ct}">0</span>'
        '<span class="kpi-l">fall on weekends</span></span></div>'
        "</div>"
        + donut
        + '<h3><span class="sec-h-ico">🗓️</span>Holidays by month</h3>'
        f'<div class="vz-wrap"><div class="vz-bars">{bars_html}</div>'
        '<div class="vz-x">' + "".join(f"<span>{m}</span>" for m in month_labels) + "</div></div>"
        f'<p class="viz-note">Official public holidays in {esc(name)} for {year} — dates, weekdays and the '
        "long weekends you can build around them with 1–3 days off. Bars show how many holidays fall in each "
        "month of the year.</p>"
        "</section>"
    )
    body = (
        '<section class="hero">'
        f'<p class="badge">{esc(name)} · {year}</p>'
        f"<h1>{esc(name)} public holidays {year}</h1>"
        '<div class="cta-row" style="margin-top:22px">'
        '<button type="button" class="btn-share-hot" data-share-open>'
        '<span aria-hidden="true">✨</span> 生成分享卡片 · Share card</button>'
        f'<a class="btn ghost" href="../calendar-{year}.ics">Add {year} to calendar</a>'
        "</div>"
        "</section>"
        + viz_html
        + holiday_table(rows)
        + month_calendar_html(year, rows, cn, prefer_local=(cc == "CN"))
        + '<section class="ad">[Ad slot]</section>'
        + f'<section class="sec"><h2>Long weekends and bridge days in {year}</h2>'
        + long_weekend_cards(runs, 8)
        + f'<p><a class="btn ghost" href="long-weekends/index.html">Full {year} long weekend guide</a></p>'
        "</section>"
        + (cn_summary_html(year) if cc == "CN" else "")
        + subscribe_block(cc, name, slug, year, site_url)
        + affiliate_block(name)
        + '<section class="sec"><h2>Keep planning</h2><div class="chips">'
        + f'<a class="chip" href="long-weekends/index.html">{year} long weekends</a>'
        + f'<a class="chip" href="../../compare/index.html?a={cc}&b=US">Compare {esc(name)} vs US</a>'
        + f'<a class="chip" href="../../days-until/index.html">Holiday countdowns</a>'
        + f'<a class="chip" href="../../api/index.html">Free JSON API</a>'
        + f'<a class="chip" href="../../calendar/index.html">Month by month</a>'
        + '</div>'
        f'<p><a href="../index.html">← {esc(name)} overview</a></p>'
    )
    faq = [
        (f"Does {name} have holidays on weekends in {year}?",
         "Some holidays fall on weekends; where a country has a substitute day, it is included as a separate entry."),
        (f"How do I use these dates to plan leave in {year}?",
         "Open the long weekend page, pick a run, and see how many days of leave connect it to the next weekend."),
    ]
    body += '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
    return render_page(
        title=f"{name} Public Holidays {year} (Full List) | {SITE_NAME}",
        description=f"Full list of {name} public holidays in {year}, including weekdays and long weekends. "
                    "Add the calendar with one click.",
        canonical=f"{site_url}/{slug}/{year}/",
        base="../../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
        cta_href=f"../calendar-{year}.ics",
        cta_label=f"Add {year} to calendar",
        extra_js=share_extra,
        crumbs=[("Home", "../../index.html"), (name, "../index.html"), (str(year), "")],
    )


def page_long_weekends(cc: str, name: str, slug: str, year: int, runs: list[dict],
                       site_url: str, verified: str) -> str:
    body = (
        '<section class="hero">'
        f'<p class="badge">{esc(name)} · {year}</p>'
        f"<h1>{esc(name)} long weekends and bridge days {year}</h1>"
        '<p class="lede">The best days to take off in '
        f"{esc(name)} {year}: every holiday run, and how much leave turns it into a longer break.</p>"
        "</section>"
        '<div class="callout"><strong>How to read this:</strong> “Base days” is the run of days off you get '
        "for free. Each pill tells you how many days of leave (<em>PTO</em>) connect that run to another "
        "weekend — more days off for the same leave.</div>"
        + long_weekend_cards(runs)
        + '<section class="ad">[Ad slot]</section>'
        '<section class="sec"><h2>Planning tip</h2>'
        "<p>Book long weekends early — flights and hotels around public holidays are the first to sell out. "
        "If your company allows it, link two holidays with one or two days of leave instead of taking them "
        "separately.</p>"
        "</section>"
        + affiliate_block("the long weekend")
        + f'<p><a href="../index.html">← {esc(name)} {year} holidays</a>'
        f' · <a href="../../index.html">All {esc(name)} years</a></p>'
    )
    faq = [
        (f"What is the best long weekend in {name} in {year}?",
         "The longest base run is usually around the biggest national holiday — check the table above and sort "
         "by total days."),
        ("How many days of leave do I need?", "Each pill shows the exact number: 1, 2 or 3 days of leave, and the "
                                             "total days off you get."),
    ]
    body += '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
    return render_page(
        title=f"{name} Long Weekends {year}: Best Days to Take Off | {SITE_NAME}",
        description=f"{name} {year} long weekends and bridge days. See how one or two days of leave turn each "
                    "public holiday into a 4–6 day break.",
        canonical=f"{site_url}/{slug}/{year}/long-weekends/",
        base="../../../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
        cta_href=f"../calendar-{year}.ics",
        cta_label=f"Add {year} to calendar",
        crumbs=[("Home", "../../../index.html"), (name, "../../index.html"),
                (str(year), "../../{year}/index.html".replace("{year}", str(year))),
                ("Long weekends", "")],
    )


def _lw_best(runs: list[dict]) -> dict | None:
    """Pick the cheapest strong break: fewest PTO for the longest total."""
    best = None
    for run in runs:
        for opt in run["options"]:
            if opt["pto"] > 1:
                continue
            score = opt["total"] - opt["pto"] * 2.5
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "total": opt["total"],
                    "pto": opt["pto"],
                    "start": opt["start"],
                    "end": opt["end"],
                    "holiday": run["name"],
                }
    return best


MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTH_SHORT = [m[:3] for m in MONTH_NAMES]


def _month_entries(by_country, countries, year: int, month: int) -> list[dict]:
    """Every public holiday across all countries on that month."""
    want = f"{month:02d}"
    items = []
    for cc, cname, slug in countries:
        for row in by_country[cc].get(year) or []:
            d = str(row.get("date") or "")
            if len(d) == 10 and d[5:7] == want:
                items.append({
                    "date": d,
                    "n": row.get("name") or "Public holiday",
                    "l": row.get("localName") or "",
                    "cc": cc,
                    "cname": cname,
                    "slug": slug,
                })
    items.sort(key=lambda e: (e["date"], e["cname"], e["n"]))
    return items


def _month_counts(by_country, countries, year: int) -> list[int]:
    counts = [0] * 12
    for cc, _cname, _slug in countries:
        for row in by_country[cc].get(year) or []:
            d = str(row.get("date") or "")
            if len(d) == 10:
                try:
                    counts[int(d[5:7]) - 1] += 1
                except ValueError:
                    continue
    return counts


def page_month_index(years: list[int], counts: dict[int, list[int]], site_url: str, verified: str) -> str:
    year_blocks = []
    for year in years:
        mon = counts.get(year) or [0] * 12
        total = sum(mon)
        cards = "".join(
            f'<a class="mcard" href="{year}/{i + 1}/index.html">'
            f'<span class="mcard-m">{MONTH_NAMES[i]}</span>'
            f'<span class="mcard-n">{mon[i]}</span>'
            f'<span class="mcard-l">holidays</span></a>'
            for i in range(12)
        )
        year_blocks.append(
            f'<section class="sec"><h2>{year} <span class="muted" style="font-weight:400;font-size:.9rem">'
            f'· {total} holidays</span></h2><div class="mgrid">{cards}</div></section>'
        )
    body = (
        '<section class="hero"><p class="eyebrow">Global calendar</p>'
        "<h1>Public holidays worldwide, month by month</h1>"
        '<p class="lede">Pick a month to see every public holiday happening around the world — which '
        "countries are off, on what day, and how it lines up with yours.</p>"
        '<div class="cta-row"><a class="btn ghost" href="../long-weekends/index.html">Long weekends</a>'
        '<a class="btn ghost" href="../api/index.html">Free JSON API</a></div></section>'
        + "".join(year_blocks)
    )
    body = "<style>" + MONTH_CSS + "</style>" + body
    return render_page(
        title=f"Public Holidays by Month, Worldwide | {SITE_NAME}",
        description="Browse public holidays worldwide month by month: which countries are off each month, "
                    "dates and holiday names, for 2025–2028.",
        canonical=f"{site_url}/calendar/",
        base="../",
        body=body,
        verified=verified,
        crumbs=[("Home", "../index.html"), ("Calendar", "")],
    )


def page_month_year(year: int, counts: list[int], site_url: str, verified: str) -> str:
    cards = "".join(
        f'<a class="mcard" href="{i + 1}/index.html">'
        f'<span class="mcard-m">{MONTH_NAMES[i]}</span>'
        f'<span class="mcard-n">{counts[i]}</span>'
        f'<span class="mcard-l">holidays</span></a>'
        for i in range(12)
    )
    peak = max(range(12), key=lambda i: counts[i]) if any(counts) else 0
    body = (
        f'<section class="hero"><p class="eyebrow">Global calendar · {year}</p>'
        f"<h1>Public holidays worldwide in {year}, month by month</h1>"
        f'<p class="lede">The busiest month is {MONTH_NAMES[peak]} with {counts[peak]} public holidays '
        "across the countries covered. Pick a month for the full list.</p>"
        '<div class="cta-row"><a class="btn ghost" href="../index.html">All years</a>'
        f'<a class="btn ghost" href="../../long-weekends/{year}/index.html">{year} long weekends</a></div>'
        "</section>"
        f'<section class="sec"><div class="mgrid">{cards}</div></section>'
    )
    body = "<style>" + MONTH_CSS + "</style>" + body
    return render_page(
        title=f"Public Holidays {year} by Month, Worldwide | {SITE_NAME}",
        description=f"Every public holiday in {year} around the world, organised by month — see which "
                    "countries are off each month.",
        canonical=f"{site_url}/calendar/{year}/",
        base="../../",
        body=body,
        verified=verified,
        crumbs=[("Home", "../../index.html"), ("Calendar", "../index.html"), (str(year), "")],
    )


def page_month(year: int, month: int, entries: list[dict], site_url: str, verified: str) -> str:
    mname = MONTH_NAMES[month - 1]
    by_date: dict[str, list[dict]] = {}
    for e in entries:
        by_date.setdefault(e["date"], []).append(e)

    rows_html = []
    for d in sorted(by_date):
        items = by_date[d]
        try:
            wd = date.fromisoformat(d).strftime("%a")
        except ValueError:
            wd = ""
        names: list[str] = []
        for e in items:
            label = e["n"]
            if e["l"] and e["l"] != e["n"]:
                label = f'{e["n"]} · {e["l"]}'
            if label not in names:
                names.append(label)
        nm = " / ".join(esc(n) for n in names[:3])
        if len(names) > 3:
            nm += f" +{len(names) - 3} more"
        seen, links = set(), []
        for e in sorted(items, key=lambda x: x["cname"]):
            if e["cc"] in seen:
                continue
            seen.add(e["cc"])
            links.append(f'<a href="/{e["slug"]}/{year}/">{esc(e["cname"])}</a>')
        rows_html.append(
            f'<tr><td>{d}</td><td>{wd}</td><td>{nm}</td><td>{" · ".join(links)}</td></tr>'
        )

    countries_n = len({e["cc"] for e in entries})
    busy_date = max(by_date, key=lambda d: len({e["cc"] for e in by_date[d]})) if by_date else ""
    busy_n = len({e["cc"] for e in by_date[busy_date]}) if busy_date else 0
    kpi = (
        '<div class="kpi-row">'
        f'<div class="kpi"><span class="kpi-ico">{_svg("calendar")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{countries_n}</span><span class="kpi-l">countries are off</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">{_svg("gift")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{len(entries)}</span><span class="kpi-l">public holidays</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">{_svg("sparkle")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{busy_n}</span><span class="kpi-l">countries on the busiest day</span></span></div>'
        "</div>"
    )
    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)
    nav_links = (
        '<div class="chips">'
        f'<a class="chip" href="../../{prev_y}/{prev_m}/index.html">← {MONTH_SHORT[prev_m - 1]} {prev_y}</a>'
        f'<a class="chip" href="../../{year}/index.html">All of {year}</a>'
        f'<a class="chip" href="../../{next_y}/{next_m}/index.html">{MONTH_SHORT[next_m - 1]} {next_y} →</a>'
        f'<a class="chip" href="../../../long-weekends/{year}/index.html">{year} long weekends</a>'
        "</div>"
    )
    body = (
        f'<section class="hero"><p class="eyebrow">Global calendar · {mname} {year}</p>'
        f"<h1>Public holidays around the world in {mname} {year}</h1>"
        f'<p class="lede">{len(entries)} public holidays across {countries_n} countries fall in {mname} '
        f"{year}. "
        + (f"The busiest day is {busy_date} with {busy_n} countries off." if busy_date else "")
        + "</p></section>"
        f'<section class="sec"><div class="kpi-row">{kpi}</div></section>'
        '<section class="sec"><h2>Holidays by date</h2><div class="tbl-wrap"><table><thead><tr>'
        "<th>Date</th><th>Day</th><th>Holiday</th><th>Countries</th></tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table></div></section>"
        + nav_links
    )
    body = "<style>" + MONTH_CSS + "</style>" + body
    return render_page(
        title=f"Public Holidays in {mname} {year} Around the World | {SITE_NAME}",
        description=f"Which countries are off in {mname} {year}: {len(entries)} public holidays across "
                    f"{countries_n} countries, with dates and holiday names.",
        canonical=f"{site_url}/calendar/{year}/{month}/",
        base="../../../",
        body=body,
        verified=verified,
        crumbs=[
            ("Home", "../../../index.html"),
            ("Calendar", "../../index.html"),
            (str(year), "../index.html"),
            (mname, ""),
        ],
    )


MONTH_CSS = """
.mgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.mcard{display:flex;flex-direction:column;gap:2px;padding:16px 16px 14px;border:1px solid var(--line);
  border-radius:14px;background:#fff;transition:transform .18s ease,box-shadow .18s ease;color:inherit}
.mcard:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(15,23,42,.08);text-decoration:none}
.mcard-m{font-weight:650;font-size:.95rem}
.mcard-n{font-size:1.55rem;font-weight:700;letter-spacing:-.02em;line-height:1.1}
.mcard-l{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
@media(max-width:760px){.mgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


def page_lw_index(years: list[int], focus: int, top_rows: list[dict],
                  year_best: dict, site_url: str, verified: str) -> str:
    cards = "".join(
        f'<a class="card" href="{y}/index.html"><h3>{y}</h3>'
        f'<p class="muted">Worldwide long weekends &amp; bridge days</p>'
        f'<span class="card-note">Longest break: {year_best.get(y, 0)} days</span></a>'
        for y in years
    )
    table = "".join(
        f'<tr><td>{i}</td><td><a href="/{r["slug"]}/{focus}/long-weekends/index.html">{esc(r["name"])}</a></td>'
        f'<td>{esc(r["holiday"])}</td><td>{esc(fmt_range(r["start"], r["end"]))}</td>'
        f'<td><strong>{r["total"]}</strong></td><td>{r["pto"] or "—"}</td></tr>'
        for i, r in enumerate(top_rows[:20], start=1)
    )
    body = (
        '<section class="hero"><p class="eyebrow">Long weekends · bridge days</p>'
        f"<h1>The best long weekends of {focus}</h1>"
        '<p class="lede">Every public-holiday run worldwide, ranked by how many days off you get for how '
        "little leave. Bridges are pre-computed — no calendar maths.</p>"
        '<div class="cta-row">'
        f'<a class="btn" href="{focus}/index.html">See the full {focus} ranking</a>'
        '<a class="btn ghost" href="../compare/index.html">Compare two countries</a>'
        "</div></section>"
        '<section class="sec"><h2>By year</h2><div class="grid">' + cards + "</div></section>"
        f'<section class="sec"><h2>Top 20 breaks in {focus}</h2>'
        '<div class="tbl-wrap"><table><thead><tr><th>#</th><th>Country</th><th>Holiday</th>'
        "<th>Dates</th><th>Days off</th><th>Leave needed</th></tr></thead><tbody>"
        + table + "</tbody></table></div>"
        '<p class="viz-note">“Days off” is the total break once you take the leave shown. '
        "Ranked by the longest break that needs at most a couple of days of leave.</p></section>"
    )
    return render_page(
        title=f"Best Long Weekends {focus} — Worldwide Ranking | {SITE_NAME}",
        description=f"Ranked long weekends and bridge days for {focus} across 95 countries: dates, days off "
                    "and how much leave each one needs.",
        canonical=f"{site_url}/long-weekends/",
        base="../",
        body=body,
        verified=verified,
        cta_href=f"{focus}/index.html",
        cta_label=f"Full {focus} ranking",
        crumbs=[("Home", "../index.html"), ("Long weekends", "")],
    )


def page_lw_year(year: int, rows: list[dict], site_url: str, verified: str) -> str:
    table = "".join(
        f'<tr><td>{i}</td><td><a href="/{r["slug"]}/{year}/long-weekends/index.html">{esc(r["name"])}</a></td>'
        f'<td>{esc(r["holiday"])}</td><td>{esc(fmt_range(r["start"], r["end"]))}</td>'
        f'<td><strong>{r["total"]}</strong></td><td>{r["pto"] or "—"}</td></tr>'
        for i, r in enumerate(rows, start=1)
    )
    longest = rows[0] if rows else None
    free = sum(1 for r in rows if r["pto"] == 0)
    avg = round(sum(r["total"] for r in rows) / len(rows), 1) if rows else 0
    kpi = (
        '<div class="kpi-row">'
        f'<div class="kpi"><span class="kpi-ico">{_svg("calendar")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{len(rows)}</span><span class="kpi-l">countries ranked</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">{_svg("sparkle")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{longest["total"] if longest else 0}</span>'
        '<span class="kpi-l">longest break (days)</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">{_svg("check")}</span><span class="kpi-b">'
        f'<span class="kpi-n">{free}</span><span class="kpi-l">need no leave at all</span></span></div>'
        "</div>"
    )
    body = (
        '<section class="hero"><p class="eyebrow">Long weekends · ' + str(year) + '</p>'
        f"<h1>Long weekends around the world in {year}</h1>"
        '<p class="lede">The best public-holiday breaks of the year, per country, with the exact leave '
        "each one needs.</p>"
        f'<div class="cta-row"><a class="btn ghost" href="../index.html">All years</a>'
        f'<a class="btn ghost" href="../../api/index.html">Free JSON API</a></div></section>'
        '<section class="sec"><h2>At a glance</h2>' + kpi
        + f'<p class="viz-note">Average best break across ranked countries: {avg} days.</p></section>'
        '<section class="sec"><h2>Ranking</h2><div class="tbl-wrap"><table><thead><tr><th>#</th>'
        "<th>Country</th><th>Holiday</th><th>Dates</th><th>Days off</th><th>Leave needed</th>"
        "</tr></thead><tbody>" + table + "</tbody></table></div></section>"
    )
    return render_page(
        title=f"Long Weekends {year} — Worldwide Ranking | {SITE_NAME}",
        description=f"Long weekends and bridge days in {year} for 95 countries: dates, days off and leave "
                    "required, ranked.",
        canonical=f"{site_url}/long-weekends/{year}/",
        base="../../",
        body=body,
        verified=verified,
        cta_href="../index.html",
        cta_label="All years",
        crumbs=[("Home", "../../index.html"), ("Long weekends", "../index.html"), (str(year), "")],
    )


def page_not_found(site_url: str, verified: str) -> str:
    body = (
        '<section class="hero"><p class="eyebrow">404</p>'
        "<h1>This page took a public holiday.</h1>"
        '<p class="lede">The link may be outdated, or the country/year you are looking for is not in the '
        "dataset yet. Try the search box (⌘K) or one of these.</p>"
        '<div class="cta-row"><a class="btn" href="/index.html#countries">Browse 95 countries</a>'
        '<a class="btn ghost" href="/long-weekends/index.html">Best long weekends</a>'
        '<a class="btn ghost" href="/api/index.html">Free JSON API</a></div></section>'
    )
    return render_page(
        title="Page not found — " + SITE_NAME,
        description="This page does not exist. Browse public holidays by country or use search.",
        canonical=f"{site_url}/404.html",
        base="/",
        body=body,
        verified=verified,
        robots="noindex,follow",
        crumbs=[("Home", "/index.html"), ("Not found", "")],
    )


def page_calendar(cc: str, name: str, slug: str, years: list[int], site_url: str, verified: str) -> str:
    links = "".join(
        f'<p><a class="btn" href="../calendar-{y}.ics">{esc(name)} {y} (.ics)</a>'
        f'<a class="btn ghost" href="../{y}/index.html">{y} dates</a></p>'
        for y in years
    )
    body = (
        '<section class="hero">'
        f"<h1>Add {esc(name)} public holidays to your calendar</h1>"
        '<p class="lede">One subscription keeps every public holiday in your calendar — no manual entry, '
        "no missed long weekends.</p></section>"
        '<section class="sec"><h2>Choose a year</h2>' + links + "</section>"
        '<section class="sec"><h2>How to subscribe</h2>'
        "<ul>"
        "<li><strong>Google Calendar</strong> (web): Other calendars → From URL → paste the .ics link → Add calendar.</li>"
        "<li><strong>Apple Calendar</strong>: File → New Calendar Subscription → paste the link.</li>"
        "<li><strong>Outlook</strong>: Add calendar → Subscribe from web → paste the link.</li>"
        "</ul></section>"
        f'<p><a href="../index.html">← {esc(name)} holidays</a></p>'
    )
    return render_page(
        title=f"Add {name} Public Holidays to Your Calendar (.ics) | {SITE_NAME}",
        description=f"Subscribe to {name} public holidays in Google Calendar, Apple Calendar or Outlook "
                    "with a single .ics link.",
        canonical=f"{site_url}/{slug}/calendar/",
        base="../../",
        body=body,
        verified=verified,
    )


def page_static(slug: str, title: str, body_html: str, site_url: str, verified: str) -> str:
    body = f'<section class="hero"><h1>{esc(title)}</h1></section><section class="sec">{body_html}</section>'
    body += '<p><a href="../index.html">← Back to all countries</a></p>'
    return render_page(
        title=f"{title} | {SITE_NAME}",
        description=f"{title} — {SITE_NAME}.",
        canonical=f"{site_url}/{slug}/",
        base="../",
        body=body,
        verified=verified,
    )


SUPPORT_ASSETS = ROOT / "assets" / "support"


def page_support(site_url: str, verified: str) -> str:
    def media(img: str, alt: str) -> str:
        if (SUPPORT_ASSETS / f"{img}.png").exists():
            return (f'<img class="sup-qr" src="../assets/support/{img}.png" '
                    f'alt="{esc(alt)}" loading="lazy">')
        return (f'<div class="sup-ph" aria-hidden="true">QR<br>'
                f'<code>assets/support/{img}.png</code></div>')

    cards = "".join([
        '<div class="sup-card">' + media("wechat", "WeChat tip QR code") +
        '<h3>微信赞赏</h3><p>扫码随意打赏，金额随意。</p></div>',
        '<div class="sup-card">' + media("alipay", "Alipay tip QR code") +
        '<h3>支付宝</h3><p>扫码打赏，支持项目持续更新。</p></div>',
        '<div class="sup-card"><div class="sup-ico">☕</div><h3>Buy me a coffee</h3>'
        '<p>International cards / PayPal.</p>'
        '<a class="btn" href="https://buymeacoffee.com/" target="_blank" rel="noopener">Open</a></div>',
        '<div class="sup-card"><div class="sup-ico">★</div><h3>GitHub Sponsors</h3>'
        '<p>Monthly or one-time sponsorship.</p>'
        '<a class="btn" href="https://github.com/sponsors/ChaoyuZhang1" target="_blank" '
        'rel="noopener">Sponsor</a></div>',
    ])
    body = (
        '<style>'
        '.sup-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0}'
        '@media(max-width:820px){.sup-grid{grid-template-columns:repeat(2,1fr)}}'
        '@media(max-width:460px){.sup-grid{grid-template-columns:1fr}}'
        '.sup-card{background:#fff;border:1px solid #e7e3da;border-radius:16px;padding:18px;text-align:center}'
        '.sup-qr{width:100%;max-width:180px;border-radius:12px;display:block;margin:0 auto 12px}'
        '.sup-ph{height:150px;border:2px dashed #d9d3c7;border-radius:12px;display:flex;flex-direction:column;'
        'align-items:center;justify-content:center;gap:6px;color:#8a8274;font-size:.78rem;margin-bottom:12px}'
        '.sup-ph code{font-size:.7rem;word-break:break-all}'
        '.sup-ico{font-size:2.2rem;line-height:1;margin:26px 0 14px}'
        '.sup-card h3{margin:0 0 6px;font-size:1.02rem}.sup-card p{color:#6b6558;font-size:.86rem;margin:0 0 12px}'
        '</style>'
        '<section class="hero"><p class="eyebrow">SUPPORT · 打赏支持</p>'
        '<h1>Keep HolidayKit free</h1>'
        '<p class="lede">If HolidayKit saved you time, you can buy me a coffee. Tips are optional — '
        'every country page, calendar subscription and the API stay free.</p></section>'
        '<section class="sec"><h2>打赏方式</h2><div class="sup-grid">' + cards + '</div>'
        '<p class="muted">打赏完全自愿，不换取任何功能、数据或优先级，也不影响你使用本站。</p></section>'
        '<section class="sec"><h2>打赏用在哪里</h2><ul>'
        '<li>持续更新 95 个国家的假期数据并补齐 2029 以后的年份</li>'
        '<li>域名、CDN 与构建所需的基础设施费用</li>'
        '<li>继续把长周末、学校假期、国家对比做深</li></ul></section>'
        '<section class="sec"><h2>Commercial API use</h2>'
        '<p>The JSON API is free for everyone under a generous fair-use policy. If you use it inside a '
        'commercial product or need a higher-volume guarantee, a sponsor licence is available — tip above '
        'and get in touch.</p></section>'
    )
    return render_page(
        title=f"Support {SITE_NAME} · 打赏支持",
        description="Support HolidayKit with a tip — WeChat, Alipay, Buy Me a Coffee or GitHub Sponsors.",
        canonical=f"{site_url}/support/",
        base="../",
        body=body,
        verified=verified,
    )


# ── school holidays & country comparison ───────────────────────────────────

def webcal_url(https_url: str) -> str:
    return https_url.replace("https://", "webcal://", 1)


def google_cal_url(ics_url: str) -> str:
    return "https://calendar.google.com/calendar/r?cid=" + quote(webcal_url(ics_url), safe="")


def outlook_cal_url(ics_url: str) -> str:
    return "https://outlook.live.com/calendar/0/addfromweb?url=" + quote(ics_url, safe="")


def go_page(cc: str, name: str, slug: str, year: int, site_url: str, verified: str) -> str:
    ics = f"{site_url}/{slug}/calendar-{year}.ics"
    wc = webcal_url(ics)
    body = (
        '<section class="hero"><p class="eyebrow">Android setup · '
        + esc(name) + " " + str(year) + "</p>"
        f"<h1>Subscribe to {esc(name)} holidays</h1>"
        '<p class="lede">We are copying the calendar link to your clipboard. Paste it into '
        "Google Calendar (Add by URL) or a subscription app — it updates automatically.</p></section>"
        '<div class="callout" data-go-status>Preparing your subscription link…</div>'
        '<div class="sub-actions">'
        '<a class="btn" href="https://calendar.google.com/calendar/r/settings/addbyurl" '
        'target="_blank" rel="noopener">Open Google Calendar → Add by URL</a>'
        f'<button type="button" class="btn ghost" data-copy="{ics}">Copy link</button>'
        f'<a class="btn ghost" href="{ics}">Download .ics</a>'
        f'<a class="btn ghost" href="/{slug}/{year}/index.html">Back to {esc(name)} {year}</a>'
        "</div>"
        '<section class="sec"><h2>2 steps</h2><div class="sub-help">'
        "<details open><summary>Google Calendar (Android browser or desktop)</summary><ol>"
        "<li>The .ics link is already copied (if not, tap <strong>Copy link</strong>).</li>"
        "<li>Open Google Calendar → Settings → <strong>Add calendar → From URL</strong> → "
        "paste the link → Add calendar.</li></ol></details>"
        "<details><summary>ICSx5 (Android app — syncs into the system calendar)</summary><ol>"
        "<li>Install ICSx5 → Add calendar → paste the copied link.</li></ol></details>"
        "<details><summary>iPhone / Mac</summary><ol>"
        f'<li><a href="{wc}">Subscribe with Apple Calendar</a> (webcal link, auto-updates).</li>'
        "</ol></details>"
        "</div></section>"
        f'<p class="muted">Calendar link: <code>{ics}</code></p>'
        "<script>(function(){var t=" + json.dumps(ics) + ";"
        "function ok(){var s=document.querySelector('[data-go-status]');"
        "if(s){s.textContent='✓ Link copied — now paste it into Google Calendar (Add calendar → From URL).';}}"
        "function copy(){if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,ok);}"
        "else{var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();"
        "try{document.execCommand('copy');}catch(e){}a.parentNode.removeChild(a);ok();}}"
        "copy();document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',copy);});"
        "})();</script>"
    )
    return render_page(
        title=f"Subscribe to {name} {year} holidays — Android one-tap setup",
        description=f"One-tap guided setup to subscribe to {name} {year} public holidays on Android, "
                    f"Google Calendar or Apple Calendar.",
        canonical=f"{site_url}/go/{slug}/",
        base="../../",
        body=body,
        verified=verified,
        robots="noindex,follow",
    )


def subscribe_block(cc: str, name: str, slug: str, year: int, site_url: str) -> str:
    ics = f"{site_url}/{slug}/calendar-{year}.ics"
    wc = webcal_url(ics)
    return (
        '<section class="sec" id="subscribe"><h2>Subscribe to '
        + esc(name) + " " + str(year) + "</h2>"
        '<p class="sub">One URL — auto-updating calendar. No file import needed (works with iOS, macOS, '
        "Google Calendar and Outlook).</p>"
        '<div class="sub-actions">'
        f'<a class="btn" href="{wc}">📱 iOS / macOS — one-tap subscribe</a>'
        f'<a class="btn ghost" href="{google_cal_url(ics)}" target="_blank" rel="noopener">'
        "Google Calendar (auto-sync)</a>"
        f'<a class="btn ghost" href="/go/{slug}/">Android — one-tap setup</a>'
        f'<a class="btn ghost" href="{outlook_cal_url(ics)}" target="_blank" rel="noopener">'
        "Add to Outlook</a>"
        f'<button type="button" class="btn ghost" data-copy="{ics}">Copy .ics link</button>'
        "</div>"
        '<div class="sub-help">'
        "<details open><summary>iPhone / iPad / Mac — subscribe (auto-updates)</summary><ol>"
        "<li>Tap the <strong>iOS / macOS — one-tap subscribe</strong> button above (this site uses a "
        "<code>webcal://</code> link).</li>"
        "<li>Calendar opens → tap <strong>Subscribe</strong>.</li>"
        "<li>If the button does nothing: Settings → Calendar → Accounts → Add Account → Other → "
        "<strong>Add Subscribed Calendar</strong>, paste the .ics URL below.</li>"
        "<li>Subscribed calendars update automatically — no need to re-import.</li></ol></details>"
        "<details><summary>Android — Google Calendar can't open webcal links; use one of these</summary><ol>"
        "<li>Easiest: open <a href=\"/go/\"><strong>Android one-tap setup</strong></a> — it copies the link "
        "and opens Google Calendar's “Add by URL”.</li>"
        "<li>Or browser → <a href=\"https://calendar.google.com/calendar/r/settings/addbyurl\" target=\"_blank\" "
        'rel="noopener">Google Calendar → Add calendar → From URL</a> → paste the .ics URL.</li>'
        "<li>Or install <strong>ICSx5</strong> (open-source) → Add calendar → paste the .ics URL; "
        "it syncs subscriptions into the Android system calendar automatically.</li>"
        "<li>Samsung Calendar: Settings → Add calendar → <strong>Subscribe</strong> → paste URL.</li>"
        "<li>Google Calendar mobile app has no “From URL” entry — use the browser step above.</li></ol></details>"
        "<details><summary>Outlook / Windows</summary><ol>"
        "<li>Outlook → Calendar → Add calendar → <strong>Subscribe from web</strong>.</li>"
        f"<li>Paste <code>{ics}</code> → Import.</li></ol></details>"
        "</div>"
        '<p class="muted">Direct .ics link (HTTPS): <code>' + ics + "</code></p>"
        "</section>"
    )


def load_school(path: Path) -> tuple[dict, dict]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(raw, dict):
        return {}, {}
    return raw.get("countries") or {}, raw.get("countryNames") or {}


def load_school_extra(root: Path) -> tuple[dict, dict]:
    """Merge manually curated national school calendars from data/school_extra.csv.

    CSV columns: cc,country,year,name,start,end,region,source
    Used only where no free nationwide API exists (source is recorded per row).
    """
    path = root / "data" / "school_extra.csv"
    countries: dict = {}
    names: dict = {}
    try:
        rows = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return countries, names
    for i, line in enumerate(rows):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [c.strip() for c in line.split(",")]
        if i == 0 and parts[0].lower() == "cc":
            continue
        if len(parts) < 7:
            continue
        cc, cname, year, hname, start, end, region = parts[:7]
        source = parts[7] if len(parts) > 7 else ""
        if not (len(cc) == 2 and cc.isalpha()):
            continue
        try:
            ds = date.fromisoformat(start)
            de = date.fromisoformat(end)
        except ValueError:
            continue
        if de < ds:
            continue
        names.setdefault(cc, cname)
        countries.setdefault(cc, {}).setdefault(str(year), []).append({
            "name": hname,
            "start": start,
            "end": end,
            "days": (de - ds).days + 1,
            "region": region or "Nationwide",
            "source": source,
        })
    for cc in countries:
        for y in countries[cc]:
            seen = set()
            uniq = []
            for item in countries[cc][y]:
                key = (item["start"], item["end"], item["name"])
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(item)
            countries[cc][y] = sorted(uniq, key=lambda r: (r["start"], r["name"]))
    return countries, names


def load_cn_calendar(path: Path) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw.get("years") or {}


def cn_year_data(year: int) -> dict:
    return CN_CAL.get(str(year)) or {}


def cn_summary_html(year: int) -> str:
    data = cn_year_data(year)
    if not data:
        return ""
    rest = data.get("rest") or []
    work = data.get("work") or []
    if not rest and not work:
        return ""
    return (
        '<section class="sec"><h2>中国的调休与补班 · ' + str(year) + "</h2>"
        '<p class="sub">中国节假日的调休安排与补班工作日（数据来自公开的中国节假日日历）。</p>'
        '<div class="chips">'
        f'<span class="chip">调休休息 {len(rest)} 天</span>'
        f'<span class="chip">补班 {len(work)} 天</span>'
        "</div>"
        + cn_tables_html(year, rest, work)
        + "</section>"
    )


def make_qr(url: str, path: Path) -> bool:
    if qrcode is None:
        return False
    try:
        img = qrcode.make(url, box_size=4, border=1)
        img.save(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def share_payload(cc: str, name: str, slug: str, year: int, rows: list[dict], site_url: str,
                  cn: dict | None = None) -> dict:
    months: list[list[dict]] = [[] for _ in range(12)]
    seen: set[str] = set()
    for row in rows:
        try:
            d = date.fromisoformat(str(row["date"]))
        except (KeyError, ValueError):
            continue
        if d.year != year:
            continue
        months[d.month - 1].append({
            "d": d.day,
            "n": str(row.get("localName") or row["name"]),
        })
        seen.add(d.isoformat())
    if cn:
        rest = cn.get("rest") or []
        work = cn.get("work") or []
        for item in rest:
            try:
                d = date.fromisoformat(item["date"])
            except (KeyError, ValueError):
                continue
            if d.year == year and d.isoformat() not in seen:
                months[d.month - 1].append({"d": d.day, "n": item.get("name") or "Holiday"})
                seen.add(d.isoformat())
        for item in work:
            try:
                d = date.fromisoformat(item["date"])
            except (KeyError, ValueError):
                continue
            if d.year == year and d.isoformat() not in seen:
                months[d.month - 1].append({"d": d.day, "n": (item.get("name") or "") + " 补班"})
                seen.add(d.isoformat())
    for month in months:
        month.sort(key=lambda x: x["d"])
    return {
        "country": name,
        "slug": slug,
        "year": year,
        "url": f"{site_url}/{slug}/{year}/",
        "qr": "/assets/qr/" + slug + ".png",
        "months": months,
    }


SHARE_CSS = """
.ic{display:inline-block;vertical-align:-0.14em;flex:none}
.kpi-ico .ic{width:20px;height:20px}
.sec-h-ico{display:inline-flex;align-items:center;justify-content:center;vertical-align:-2px}
.sec-h-ico .ic{width:18px;height:18px;stroke-width:1.9}
h3 .ic{width:.95em;height:.95em;vertical-align:-0.08em;opacity:.85}
.flag{font-size:.66rem;font-weight:800;letter-spacing:.09em;color:var(--muted);
  background:rgba(15,23,42,.05);border:1px solid var(--line);border-radius:7px;
  padding:3px 7px;display:inline-block;line-height:1.2;vertical-align:2px;text-align:center;min-width:2.1em}
h1 .flag{font-size:.30em;letter-spacing:.10em;vertical-align:.55em;padding:3px 7px;opacity:.85}
/* homepage next-holiday countdown */
.hero-side{display:flex;flex-direction:column;gap:14px;min-width:0}
.hero-next{border:0;border-radius:18px;padding:18px 20px;color:#e2e8f0;
  background:linear-gradient(150deg,#0f172a 0%,#111827 55%,#0b3b33 100%);
  box-shadow:0 18px 40px -24px rgba(2,6,23,.7)}
.hero-next .hn-top{display:flex;align-items:center;gap:8px;font-size:.7rem;letter-spacing:.09em;
  text-transform:uppercase;color:#94a3b8}
.hero-next h3{font-size:1.02rem;line-height:1.3;margin:8px 0 3px;color:#f8fafc}
.hero-next .hn-date{font-size:.78rem;color:#94a3b8}
.hero-next .hn-days{display:flex;align-items:baseline;gap:9px;margin-top:10px}
.hero-next .hn-num{font-size:2.35rem;line-height:1;font-weight:700;color:#34d399;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.hero-next .hn-lbl{font-size:.72rem;color:#94a3b8}
.hero-next .prog{background:rgba(148,163,184,.24);margin-top:12px}
.hero-next .hn-link{display:inline-block;margin-top:11px;font-size:.78rem;color:#67e8f9;text-decoration:none}
.hero-next .hn-link:hover{text-decoration:underline}
/* holiday guide cards: metrics */
.gmeta{display:flex;justify-content:space-between;gap:8px;font-size:.7rem;color:var(--muted);margin-top:6px}
.gspark{display:flex;align-items:flex-end;gap:2px;height:22px;margin:8px 0 0}
.gspark i{flex:1;min-height:2px;border-radius:2px 2px 0 0;
  background:linear-gradient(180deg,#38bdf8,#0ea5e9);transform-origin:bottom;
  animation:vzGrow .8s cubic-bezier(.2,.75,.25,1) both}
/* interactive comparison */
.cm-pick{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;margin:6px 0 20px}
.cm-pick label{display:flex;flex-direction:column;gap:6px;font-size:.76rem;font-weight:600}
.cm-pick select{padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff;
  font:inherit;min-width:230px}
.cm-card{border:1px solid var(--line);border-radius:16px;padding:18px;background:#fff;margin:0 0 16px}
.cm-card h2{font-size:1rem;margin:0 0 2px}
.cm-sub{font-size:.78rem;color:var(--muted);margin:0 0 12px}
.cm-bars{display:grid;grid-template-columns:repeat(12,1fr);gap:7px;align-items:end;height:150px}
.cm-m{display:flex;flex-direction:row;align-items:flex-end;gap:2px;height:100%}
.cm-m i{flex:1;display:block;border-radius:3px 3px 0 0;transform-origin:bottom;
  animation:vzGrow .8s cubic-bezier(.2,.75,.25,1) both}
.cm-table td.miss{color:#cbd5e1}
.cm-m i.a{background:linear-gradient(180deg,#34d399,#059669)}
.cm-m i.b{background:linear-gradient(180deg,#fbbf24,#f59e0b)}
.cm-x{display:grid;grid-template-columns:repeat(12,1fr);gap:7px;font-size:.62rem;color:var(--muted);
  text-align:center;margin-top:6px}
.cm-table{width:100%;border-collapse:collapse;font-size:.86rem;margin-top:4px}
.cm-table th,.cm-table td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.cm-table th{font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cm-table td.only-a{color:#047857;font-weight:600}
.cm-table td.only-b{color:#b45309;font-weight:600}
.cm-table td.miss{color:#cbd5e1}
.cm-note{font-size:.78rem;color:var(--muted);margin:10px 0 0}
.cm-pairs{margin-top:22px}
.cm-pairs .grid{gap:12px}
@media(max-width:900px){
  .cm-pick{flex-direction:column;align-items:stretch}
  .cm-pick select{min-width:0;width:100%}
  .cm-bars{height:110px;gap:4px}
  .cm-x{gap:4px;font-size:.56rem}
}

.share-modal{position:fixed;inset:0;z-index:80;background:rgba(12,16,22,.62);backdrop-filter:blur(6px);display:none;align-items:center;justify-content:center;padding:20px}
.share-modal.on{display:flex}
.share-panel{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:18px;max-width:min(780px,96vw);max-height:94vh;overflow:auto;box-shadow:0 30px 80px rgba(15,17,21,.35)}
.share-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-size:.95rem}
.share-close{border:1px solid var(--line);background:var(--surface);width:32px;height:32px;border-radius:10px;cursor:pointer;font-size:1rem;line-height:1}
.share-canvas{display:block;width:100%;max-height:52vh;height:auto;border-radius:12px;background:#111;margin:0 auto}
.share-controls{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
.share-controls label{font-size:.72rem;color:var(--muted);display:flex;flex-direction:column;gap:4px;text-transform:uppercase;letter-spacing:.06em}
.share-controls select{padding:7px 10px;border:1px solid var(--line);border-radius:9px;background:var(--surface);font-size:.85rem;text-transform:none;letter-spacing:0}
.share-btns{display:flex;gap:8px;flex-wrap:wrap}
.share-btns .btn{padding:9px 16px;font-size:.85rem}
.share-platforms{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.share-plat{border:1px solid var(--line);background:var(--surface);color:var(--ink-soft);border-radius:999px;padding:7px 14px;font-size:.8rem;cursor:pointer;transition:all .18s}
.share-plat:hover{border-color:var(--ink);transform:translateY(-1px)}
.share-hint{font-size:.72rem;color:var(--muted);margin:10px 0 0;line-height:1.5}
/* ── eye-catching share CTA + floating action button ── */
.btn-share-hot{position:relative;display:inline-flex;align-items:center;gap:9px;border:0;cursor:pointer;font-weight:700;font-size:.95rem;padding:14px 24px;border-radius:999px;color:#04231a;background:linear-gradient(100deg,#34d399,#22d3ee,#a78bfa,#34d399);background-size:280% 100%;animation:hotgrad 7s linear infinite;box-shadow:0 12px 32px rgba(34,211,238,.32),0 0 0 1px rgba(255,255,255,.28) inset;transition:transform .18s,box-shadow .18s}
.btn-share-hot:hover{transform:translateY(-2px) scale(1.02);box-shadow:0 18px 42px rgba(34,211,238,.42)}
.btn-share-hot:active{transform:translateY(0) scale(.99)}
@keyframes hotgrad{to{background-position:280% 50%}}
.share-fab{position:fixed;right:20px;bottom:100px;z-index:70;display:inline-flex;align-items:center;gap:9px;padding:12px 18px;border-radius:999px;border:1px solid rgba(255,255,255,.35);cursor:pointer;color:#04231a;font-weight:800;font-size:.86rem;letter-spacing:.01em;background:linear-gradient(120deg,#34d399,#22d3ee);box-shadow:0 12px 30px rgba(34,211,238,.38);animation:fabpulse 2.8s ease-in-out infinite;transition:transform .18s}
.share-fab:hover{transform:translateY(-3px) scale(1.04)}
.share-fab .sf-ic{width:22px;height:22px;display:grid;place-items:center;border-radius:7px;background:rgba(255,255,255,.4);font-size:.95rem;line-height:1}
.share-fab .sf-txt{display:inline-block}
@keyframes fabpulse{0%,100%{box-shadow:0 12px 30px rgba(34,211,238,.38),0 0 0 0 rgba(52,211,153,.5)}50%{box-shadow:0 12px 30px rgba(34,211,238,.38),0 0 0 15px rgba(52,211,153,0)}}
@media (max-width:720px){.share-fab{right:12px;bottom:78px;padding:10px 14px;font-size:.8rem}.btn-share-hot{padding:12px 18px;font-size:.88rem}}
/* ── data-visualisation components ── */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin:18px 0 6px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px 18px;position:relative;overflow:hidden}
.kpi::after{content:"";position:absolute;right:-30px;bottom:-50px;width:130px;height:130px;border-radius:50%;background:radial-gradient(circle,rgba(52,211,153,.2),transparent 70%);pointer-events:none}
.kpi-n{display:block;font-family:Georgia,"Times New Roman",serif;font-size:2.05rem;line-height:1.05;letter-spacing:-.02em}
.kpi-l{display:block;color:var(--muted);font-size:.74rem;margin-top:6px;text-transform:uppercase;letter-spacing:.08em}
.vz-wrap{margin:14px 0 4px}
.vz-bars{display:flex;align-items:flex-end;gap:6px;height:132px;padding:10px 6px 6px;border-radius:14px;background:linear-gradient(180deg,rgba(52,211,153,.07),rgba(52,211,153,0));border:1px solid var(--line)}
.vz-bars .bz{flex:1;position:relative;height:2px;min-height:2px;border-radius:5px 5px 2px 2px;background:linear-gradient(180deg,#34d399,#0ea5e9);transform-origin:bottom;animation:vzGrow .95s cubic-bezier(.2,.75,.25,1) both;opacity:.92}
.vz-bars .bz:hover{filter:brightness(1.15);opacity:1}
.vz-bars .bz b{position:absolute;top:-17px;left:0;right:0;text-align:center;font-size:.62rem;color:var(--muted);font-weight:600}
.vz-x{display:flex;gap:6px;margin-top:6px}
.vz-x span{flex:1;text-align:center;font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.vz-legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.72rem;color:var(--muted);margin-top:8px}
.vz-legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.vz-cmp{margin:6px 0 0}
.vz-cmp .row{margin:14px 0}
.vz-cmp .row-h{display:flex;justify-content:space-between;gap:12px;font-size:.84rem;margin-bottom:6px}
@keyframes vzGrow{from{transform:scaleY(.02)}to{transform:scaleY(1)}}
.vz-cmp .track{height:12px;border-radius:999px;background:rgba(15,23,42,.09);overflow:hidden}
.vz-cmp .fill{height:100%;width:0;border-radius:999px;background:linear-gradient(90deg,#34d399,#22d3ee);transform-origin:left;animation:vzGrowX 1.05s cubic-bezier(.2,.75,.25,1) both}
@keyframes vzGrowX{from{transform:scaleX(.01)}to{transform:scaleX(1)}}
.vz-cmp .fill.b{background:linear-gradient(90deg,#f59e0b,#f43f5e)}
@media (prefers-reduced-motion:reduce){.vz-bars .bz,.vz-cmp .fill{animation:none}}
.donut-wrap{display:flex;align-items:center;gap:26px;flex-wrap:wrap;margin:10px 0}
.vz-donut{width:156px;height:156px;transform:rotate(-90deg);flex:0 0 auto}
.vz-donut .bg{fill:none;stroke:rgba(148,163,184,.25);stroke-width:14}
.vz-donut .fg{fill:none;stroke:#34d399;stroke-width:14;stroke-linecap:round;transition:stroke-dashoffset 1.15s cubic-bezier(.2,.75,.25,1)}
.donut-txt{display:flex;flex-direction:column;gap:6px}
.donut-txt .big{font-family:Georgia,serif;font-size:1.9rem;line-height:1}
.donut-txt .muted{font-size:.78rem}
/* ── dashboard-style icon cards + bar lists ── */
.kpi{display:flex;align-items:flex-start;gap:13px}
.kpi-ico{flex:0 0 auto;width:40px;height:40px;border-radius:12px;display:grid;place-items:center;font-size:1.05rem;line-height:1;background:linear-gradient(135deg,rgba(52,211,153,.20),rgba(34,211,238,.16));border:1px solid rgba(52,211,153,.26)}
.kpi-b{display:flex;flex-direction:column;min-width:0}
.hbar{display:flex;align-items:center;gap:12px;margin:11px 0;font-size:.83rem}
.hbar-h{flex:0 0 34%;display:flex;align-items:center;gap:8px;min-width:0;color:var(--ink-soft)}
.hbar-h em{font-style:normal;flex:0 0 auto}
.hbar-h span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar-track{flex:1;height:9px;border-radius:999px;background:rgba(15,23,42,.08);overflow:hidden;min-width:60px}
.hbar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#34d399,#22d3ee);transform-origin:left;animation:vzGrowX 1s cubic-bezier(.2,.75,.25,1) both}
.hbar-v{flex:0 0 auto;min-width:30px;text-align:right;font-variant-numeric:tabular-nums;color:var(--ink-soft);font-size:.8rem}
.viz-note{color:var(--muted);font-size:.86rem;line-height:1.65;margin:16px 0 0;max-width:72ch}
.sec-h-ico{display:inline-grid;place-items:center;width:26px;height:26px;border-radius:8px;background:rgba(52,211,153,.15);font-size:.9rem;margin-right:10px;vertical-align:-4px}
@media (max-width:640px){.hbar-h{flex-basis:42%}.viz-note{font-size:.82rem}}
/* country card sparkline + countdown progress */
.spark{display:flex;align-items:flex-end;gap:2px;height:26px;margin:8px 0 2px}
.spark i{flex:1;min-height:2px;border-radius:2px 2px 1px 1px;background:linear-gradient(180deg,#34d399,#0ea5e9);transform-origin:bottom;animation:vzGrow .8s cubic-bezier(.2,.75,.25,1) both}
.card-note{font-size:.72rem;color:var(--muted);margin:2px 0 6px}
.prog{display:block;height:6px;border-radius:999px;background:rgba(15,23,42,.09);overflow:hidden;margin-top:10px}
.prog i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#34d399,#22d3ee);transform-origin:left;animation:vzGrowX .9s cubic-bezier(.2,.75,.25,1) both}
@media (prefers-reduced-motion:reduce){.spark i,.prog i{animation:none}}
"""




SHARE_JS = r"""
(function(){
  var D=window.HK_SHARE; if(!D) return;
  var TPL={
    aurora:{bg:['#0e211d','#0a1420'],ink:'#eef7f2',sub:'#9fb8ae',accent:'#34d399',cell:'rgba(255,255,255,.06)',line:'rgba(255,255,255,.14)',glow:['rgba(52,211,153,.30)','rgba(56,189,248,.16)']},
    paper:{bg:['#f8f3e8','#efe5d2'],ink:'#1d1a16',sub:'#6f6557',accent:'#b5731a',cell:'rgba(255,255,255,.55)',line:'rgba(29,26,22,.14)',glow:['rgba(181,115,26,.16)','rgba(29,26,22,.06)']},
    neon:{bg:['#050809','#0a1411'],ink:'#eafff3',sub:'#7fd6a5',accent:'#7cffb2',cell:'rgba(124,255,178,.08)',line:'rgba(124,255,178,.28)',glow:['rgba(124,255,178,.24)','rgba(0,255,170,.10)']},
    bloom:{bg:['#ffe9f0','#e8efff'],ink:'#2b2540',sub:'#6b6280',accent:'#7c5cff',cell:'rgba(255,255,255,.62)',line:'rgba(43,37,64,.14)',glow:['rgba(255,140,190,.28)','rgba(124,92,255,.18)']}
  };
  var SIZES={story:[1080,1350],square:[1080,1080],wide:[1600,900]};
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var st={tpl:'aurora',size:'story',month:-1,qr:null};
  var canvas=null, modal=null, qrImg=null;
  function px(n){ return Math.round(n); }
  function rr(ctx,x,y,w,h,r){ var q=Math.min(r,w/2,h/2); ctx.beginPath(); ctx.moveTo(x+q,y); ctx.arcTo(x+w,y,x+w,y+h,q); ctx.arcTo(x+w,y+h,x,y+h,q); ctx.arcTo(x,y+h,x,y,q); ctx.arcTo(x,y,x+w,y,q); ctx.closePath(); }
  function fit(ctx,text,max,size,font){ var s=size; do{ ctx.font='600 '+s+'px '+font; if(ctx.measureText(text).width<=max) break; s-=2; }while(s>10); return s; }
  function draw(){
    if(!canvas) return;
    var S=SIZES[st.size], W=S[0], H=S[1];
    canvas.width=W; canvas.height=H;
    var ctx=canvas.getContext('2d'), t=TPL[st.tpl];
    var g=ctx.createLinearGradient(0,0,W,H); g.addColorStop(0,t.bg[0]); g.addColorStop(1,t.bg[1]);
    ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    function blob(cx,cy,r,color){ var rg=ctx.createRadialGradient(cx,cy,0,cx,cy,r); rg.addColorStop(0,color); rg.addColorStop(1,'rgba(0,0,0,0)'); ctx.fillStyle=rg; ctx.beginPath(); ctx.arc(cx,cy,r,0,7); ctx.fill(); }
    blob(W*0.16,H*0.05,W*0.42,t.glow[0]); blob(W*0.92,H*0.9,W*0.5,t.glow[1]);
    var P=px(W*0.055);
    ctx.fillStyle=t.ink;
    ctx.font='700 '+px(W*0.034)+'px Georgia,"Times New Roman",serif';
    ctx.fillText('HolidayKit',P,px(H*0.085));
    ctx.fillStyle=t.sub; ctx.font='400 '+px(W*0.016)+'px system-ui,sans-serif';
    ctx.fillText('Public holidays · long weekends',P,px(H*0.115));
    ctx.textAlign='right'; ctx.fillStyle=t.accent;
    ctx.font='700 '+px(W*0.05)+'px Georgia,serif';
    ctx.fillText(String(D.year),W-P,px(H*0.095));
    ctx.textAlign='left';
    ctx.fillStyle=t.ink;
    var title=D.country+' holidays';
    var ts=fit(ctx,title,W-P*2,px(W*0.062),'Georgia,"Songti SC","Microsoft YaHei",serif');
    ctx.font='600 '+ts+'px Georgia,"Songti SC","Microsoft YaHei",serif';
    ctx.fillText(title,P,px(H*0.185));
    if(st.month>=0){ ctx.fillStyle=t.sub; ctx.font='400 '+px(W*0.022)+'px system-ui'; ctx.fillText(MONTHS[st.month]+' '+D.year,P,px(H*0.218)); }
    var areaTop=px(H*(st.month>=0?0.245:0.225));
    var footTop=px(H*0.855);
    if(st.month>=0){ drawMonth(ctx,W,H,P,t,areaTop,footTop); } else { drawYear(ctx,W,H,P,t,areaTop,footTop); }
    drawFooter(ctx,W,H,P,t,footTop);
  }
  function holidayOf(m){ return (D.months[m]||[]); }
  function drawYear(ctx,W,H,P,t,top,bottom){
    var cols = W>1400?4:3, rows=Math.ceil(12/cols);
    var gap=px(W*0.018);
    var availW=W-P*2, cellW=(availW-gap*(cols-1))/cols;
    var availH=bottom-top-px(H*0.03), cellH=availH/rows;
    var hol={}; for(var m=0;m<12;m++){ holidayOf(m).forEach(function(x){ hol[m+'-'+x.d]=x.n; }); }
    for(var i=0;i<12;i++){
      var c=i%cols, r=Math.floor(i/cols);
      var x=P+c*(cellW+gap), y=top+r*cellH;
      ctx.fillStyle=t.cell; rr(ctx,x,y+px(H*0.012),cellW,cellH-px(H*0.024),px(W*0.012)); ctx.fill();
      ctx.strokeStyle=t.line; ctx.lineWidth=1; ctx.stroke();
      ctx.fillStyle=t.accent; ctx.font='700 '+px(W*0.0125)+'px system-ui'; ctx.fillText(MONTHS[i],x+px(W*0.012),y+px(H*0.035));
      var dows=['M','T','W','T','F','S','S'];
      var gw=(cellW-px(W*0.024))/7;
      ctx.fillStyle=t.sub; ctx.font='500 '+px(W*0.0072)+'px system-ui';
      dows.forEach(function(dw,di){ ctx.textAlign='center'; ctx.fillText(dw,x+px(W*0.012)+gw*(di+0.5),y+px(H*0.055)); });
      var first=new Date(D.year,i,1); var offset=(first.getDay()+6)%7; var dim=new Date(D.year,i+1,0).getDate();
      for(var dnum=1;dnum<=dim;dnum++){
        var idx=offset+dnum-1, dx=idx%7, dy=Math.floor(idx/7);
        var cx=x+px(W*0.012)+gw*(dx+0.5), cy=y+px(H*0.055)+px(H*0.019)*(dy+1.15);
        var key=i+'-'+dnum;
        ctx.fillStyle=(hol[key]?t.accent:'rgba(0,0,0,0)');
        if(hol[key]){ rr(ctx,cx-gw*0.36,cy-px(W*0.008),gw*0.72,px(W*0.0145),px(W*0.004)); ctx.fill(); }
        ctx.fillStyle=(hol[key]? (st.tpl==='paper'?'#fff7ea':'#06120d') : t.ink);
        ctx.font='600 '+px(W*0.0078)+'px system-ui';
        ctx.textAlign='center'; ctx.fillText(String(dnum),cx,cy+px(W*0.0028));
      }
      ctx.textAlign='left';
    }
  }
  function drawMonth(ctx,W,H,P,t,top,bottom){
    var hol={}; holidayOf(st.month).forEach(function(x){ hol[x.d]=x.n; });
    var gw=(W-P*2)/7, gh=px(H*0.052);
    var dows=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    ctx.fillStyle=t.sub; ctx.font='600 '+px(W*0.0095)+'px system-ui';
    dows.forEach(function(d,i){ ctx.textAlign='center'; ctx.fillText(d,P+gw*(i+0.5),top+px(H*0.012)); });
    var first=new Date(D.year,st.month,1); var offset=(first.getDay()+6)%7; var dim=new Date(D.year,st.month+1,0).getDate();
    var rows=Math.ceil((offset+dim)/7);
    for(var r=0;r<rows;r++){
      for(var c=0;c<7;c++){
        var idx=r*7+c, dnum=idx-offset+1;
        var x=P+c*gw, y=top+px(H*0.03)+r*gh;
        if(dnum<1||dnum>dim) continue;
        var isHol=!!hol[dnum];
        ctx.fillStyle=isHol?t.cell:'rgba(0,0,0,0)';
        rr(ctx,x+px(W*0.003),y,px(gw)-px(W*0.006),gh-px(H*0.006),px(W*0.007)); ctx.fill();
        if(isHol){ ctx.strokeStyle=t.accent; ctx.lineWidth=1.5; ctx.stroke(); }
        ctx.fillStyle=isHol?t.accent:t.ink;
        ctx.font='700 '+px(W*0.016)+'px system-ui'; ctx.textAlign='left';
        ctx.fillText(String(dnum),x+px(W*0.012),y+px(H*0.033));
        if(isHol){
          ctx.fillStyle=t.sub; ctx.font='500 '+px(W*0.0072)+'px system-ui';
          var nm=hol[dnum]; var maxw=gw-px(W*0.02);
          if(ctx.measureText(nm).width>maxw){ while(nm.length>1 && ctx.measureText(nm+'...').width>maxw) nm=nm.slice(0,-1); nm+='...'; }
          ctx.fillText(nm,x+px(W*0.012),y+px(H*0.047));
        }
      }
    }
    var ly=top+px(H*0.03)+rows*gh+px(H*0.02);
    ctx.fillStyle=t.ink; ctx.font='700 '+px(W*0.013)+'px system-ui';
    var items=holidayOf(st.month);
    ctx.fillText(items.length? 'Holidays in '+MONTHS[st.month] : 'No public holidays this month',P,ly);
    var lineH=px(H*0.022);
    items.slice(0,10).forEach(function(it,i){
      var cy=ly+lineH*(i+1);
      ctx.fillStyle=t.accent; ctx.font='600 '+px(W*0.0095)+'px system-ui';
      ctx.fillText(MONTHS[st.month]+' '+it.d, P, cy);
      ctx.fillStyle=t.ink; ctx.font='400 '+px(W*0.0095)+'px system-ui';
      ctx.fillText(it.n, P+px(W*0.075), cy);
    });
  }
  function drawFooter(ctx,W,H,P,t,footTop){
    ctx.strokeStyle=t.line; ctx.beginPath(); ctx.moveTo(P,footTop); ctx.lineTo(W-P,footTop); ctx.stroke();
    var url=D.url.replace('https://','');
    ctx.fillStyle=t.ink; ctx.font='600 '+px(W*0.017)+'px system-ui';
    ctx.fillText('HolidayKit',P,footTop+px(H*0.035));
    ctx.fillStyle=t.sub; ctx.font='400 '+px(W*0.0105)+'px system-ui';
    ctx.fillText(url,P,footTop+px(H*0.058));
    ctx.fillText('Scan to open the calendar',P,footTop+px(H*0.078));
    if(st.qr){
      var qs=px(Math.min(W*0.105,H*0.105)), qx=W-P-qs, qy=footTop+px(H*0.012);
      ctx.fillStyle='#ffffff'; rr(ctx,qx-px(W*0.006),qy-px(W*0.006),qs+px(W*0.012),qs+px(W*0.012),px(W*0.008)); ctx.fill();
      ctx.drawImage(st.qr,qx,qy,qs,qs);
    }
  }
  function ensure(){
    if(modal) return modal;
    var wrap=document.createElement('div'); wrap.className='share-modal';
    wrap.innerHTML='<div class="share-panel"><div class="share-head"><strong>Share card</strong>'+
      '<button type="button" class="share-close" aria-label="Close">x</button></div>'+
      '<canvas class="share-canvas"></canvas>'+
      '<div class="share-controls">'+
      '<label>Range<select data-share-month><option value="-1">Full year</option>'+MONTHS.map(function(m,i){return '<option value="'+i+'">'+m+'</option>';}).join('')+'</select></label>'+
      '<label>Style<select data-share-tpl>'+Object.keys(TPL).map(function(k){return '<option value="'+k+'">'+k+'</option>';}).join('')+'</select></label>'+
      '<label>Size<select data-share-size><option value="story">Story 4:5</option><option value="square">Square</option><option value="wide">Wide</option></select></label>'+
      '</div>'+
      '<div class="share-btns"><button type="button" class="btn" data-share-dl>Download PNG</button>'+
      '<button type="button" class="btn ghost" data-share-native>Share</button>'+
      '<button type="button" class="btn ghost" data-share-copy>Copy image</button></div>'+
      '<div class="share-platforms" data-share-platforms></div>'+
      '<p class="share-hint">Shortcuts open the platform composer with text + link. For apps that only accept images (WeChat Moments, Xiaohongshu, Douyin, Instagram) tap "Download PNG" first, then post the image there.</p></div>';
    document.body.appendChild(wrap); modal=wrap;
    canvas=wrap.querySelector('.share-canvas');
    wrap.querySelector('.share-close').addEventListener('click',function(){ wrap.classList.remove('on'); });
    wrap.addEventListener('click',function(e){ if(e.target===wrap) wrap.classList.remove('on'); });
    wrap.querySelector('[data-share-month]').addEventListener('change',function(){ st.month=parseInt(this.value,10); draw(); });
    wrap.querySelector('[data-share-tpl]').addEventListener('change',function(){ st.tpl=this.value; draw(); });
    wrap.querySelector('[data-share-size]').addEventListener('change',function(){ st.size=this.value; draw(); });
    wrap.querySelector('[data-share-dl]').addEventListener('click',function(){ dl(); });
    wrap.querySelector('[data-share-native]').addEventListener('click',function(){ nativeShare(); });
    wrap.querySelector('[data-share-copy]').addEventListener('click',function(){ copy(); });
    return wrap;
  }
  var CP={CN:['wechat','weibo','xhs','douyin'],TW:['line','facebook','whatsapp'],HK:['whatsapp','wechat','facebook'],
    JP:['line','x','facebook'],KR:['kakao','facebook','x'],US:['x','facebook','reddit','linkedin'],
    GB:['x','facebook','whatsapp','linkedin'],CA:['x','facebook','whatsapp'],AU:['facebook','x','whatsapp'],
    IN:['whatsapp','x','telegram','linkedin'],SG:['whatsapp','telegram','facebook'],MY:['whatsapp','facebook','telegram'],
    TH:['line','facebook','x'],VN:['facebook','zalo'],ID:['whatsapp','facebook','instagram'],PH:['facebook','whatsapp'],
    DE:['whatsapp','facebook','x'],FR:['whatsapp','facebook','x'],ES:['whatsapp','facebook','x'],IT:['whatsapp','facebook','x'],
    NL:['whatsapp','facebook','x'],PL:['facebook','x','whatsapp'],RU:['vk','telegram','whatsapp'],
    BR:['whatsapp','instagram','facebook'],MX:['whatsapp','facebook','x'],AR:['whatsapp','facebook','x'],
    ZA:['whatsapp','facebook','x'],AE:['whatsapp','telegram','x'],SA:['whatsapp','x','telegram'],
    TR:['whatsapp','x','telegram'],IL:['whatsapp','facebook','telegram'],EG:['whatsapp','facebook','x'],
    NG:['whatsapp','facebook','x'],KE:['whatsapp','facebook','x'],NZ:['facebook','x','whatsapp'],
    SE:['facebook','whatsapp','x'],NO:['facebook','whatsapp'],DK:['facebook','whatsapp'],FI:['whatsapp','facebook','x'],
    CH:['whatsapp','facebook','x'],AT:['whatsapp','facebook','x'],PT:['whatsapp','facebook','x'],GR:['facebook','whatsapp','x']};
  var PN={x:'X',facebook:'Facebook',whatsapp:'WhatsApp',telegram:'Telegram',line:'LINE',weibo:'微博',
    wechat:'微信',xhs:'小红书',douyin:'抖音',kakao:'KakaoTalk',vk:'VK',reddit:'Reddit',linkedin:'LinkedIn',
    instagram:'Instagram',zalo:'Zalo'};
  function platformHref(id,cap,url){
    var u=encodeURIComponent(url), t=encodeURIComponent(cap);
    if(id==='x')return 'https://twitter.com/intent/tweet?text='+t+'&url='+u;
    if(id==='facebook')return 'https://www.facebook.com/sharer/sharer.php?u='+u;
    if(id==='linkedin')return 'https://www.linkedin.com/sharing/share-offsite/?url='+u;
    if(id==='reddit')return 'https://www.reddit.com/submit?url='+u+'&title='+t;
    if(id==='whatsapp')return 'https://wa.me/?text='+encodeURIComponent(cap+' '+url);
    if(id==='telegram')return 'https://t.me/share/url?url='+u+'&text='+t;
    if(id==='line')return 'https://social-plugins.line.me/lineit/share?url='+u;
    if(id==='weibo')return 'https://service.weibo.com/share/share.php?url='+u+'&title='+t;
    if(id==='kakao')return 'https://story.kakao.com/share?url='+u;
    if(id==='vk')return 'https://vk.com/share.php?url='+u;
    if(id==='zalo')return 'https://zalo.me/share?u='+u;
    return '';
  }
  function caption(){
    return 'HolidayKit · '+D.country+' '+D.year+' holidays — '+D.url;
  }
  function renderPlatforms(){
    if(!modal) return;
    var box=modal.querySelector('[data-share-platforms]'); if(!box) return;
    var cc=(window.HK_COUNTRY||'').toUpperCase();
    var ids=CP[cc]||['x','facebook','whatsapp','telegram','linkedin'];
    box.innerHTML='';
    ids.forEach(function(id){
      var b=document.createElement('button'); b.type='button'; b.className='share-plat';
      b.textContent=PN[id]||id;
      b.addEventListener('click',function(){
        var h=platformHref(id,caption(),D.url);
        if(h){ window.open(h,'_blank','noopener'); }
        else { try{navigator.clipboard.writeText(caption());}catch(e){} dl();
          alert(PN[id]+' 不支持网页直接带图发布：图片已下载、文案已复制，请打开 App 发布。'); }
      });
      box.appendChild(b);
    });
  }
  function detectCountry(){
    if(window.HK_COUNTRY) return;
    fetch('/geo').then(function(r){return r.ok?r.json():null;}).then(function(d){
      window.HK_COUNTRY=((d&&d.country)||'').toUpperCase(); renderPlatforms();
    }).catch(function(){
      try{ var n=(navigator.language||'').split('-')[1]; if(n) window.HK_COUNTRY=n.toUpperCase(); }catch(e){}
      renderPlatforms();
    });
  }
  function toBlob(cb){ canvas.toBlob(function(b){ cb(b); },'image/png'); }
  function dl(){ toBlob(function(b){ var a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='holidaykit-'+D.slug+'-'+D.year+'.png'; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); },800); }); }
  function nativeShare(){ toBlob(function(b){ var f=new File([b],'holidaykit.png',{type:'image/png'}); if(navigator.canShare&&navigator.canShare({files:[f]})){ navigator.share({files:[f],title:'HolidayKit',text:D.country+' '+D.year+' holidays'}).catch(function(){}); } else { dl(); } }); }
  function copy(){ toBlob(function(b){ if(navigator.clipboard&&window.ClipboardItem){ navigator.clipboard.write([new ClipboardItem({'image/png':b})]).then(function(){ alert('Copied image / 图片已复制'); },function(){ dl(); }); } else { dl(); } }); }
  function open(){ ensure().classList.add('on'); draw(); detectCountry(); renderPlatforms(); }
  qrImg=new Image();
  qrImg.onload=function(){ st.qr=qrImg; if(modal) draw(); };
  qrImg.src=D.qr;
  document.querySelectorAll('[data-share-open]').forEach(function(b){ b.addEventListener('click',function(e){ e.preventDefault(); open(); }); });
  if(new URLSearchParams(location.search).has('share')) { window.addEventListener('load', open); }
  // floating, always-visible share CTA
  (function(){
    if(document.querySelector('.share-fab')) return;
    var lang=(document.documentElement.lang||'en').slice(0,2);
    var TXT={zh:'分享卡片',ja:'共有カード',ko:'공유 카드',es:'Compartir',fr:'Partager',de:'Teilen'};
    var fab=document.createElement('button');
    fab.type='button'; fab.className='share-fab'; fab.setAttribute('aria-label','Share card');
    fab.innerHTML='<span class="sf-ic" aria-hidden="true">✨</span><span class="sf-txt">'+(TXT[lang]||'Share card')+'</span>';
    fab.addEventListener('click', function(){ open(); });
    document.body.appendChild(fab);
  })();
  window.HK_OPEN_SHARE=open;
})();
"""


def cn_tables_html(year: int, rest: list[dict], work: list[dict]) -> str:
    def rows(items: list[dict]) -> str:
        out = []
        for item in items:
            try:
                d = date.fromisoformat(item["date"])
            except (KeyError, ValueError):
                continue
            out.append(
                "<tr>"
                f"<td>{esc(fmt_date(d))}</td>"
                f"<td>{esc(fmt_weekday(d))}</td>"
                f"<td>{esc(item.get('name') or '—')}</td>"
                "</tr>"
            )
        return "".join(out)

    return (
        '<div class="two-col">'
        '<div><h3>调休休息日</h3><div class="tbl-wrap"><table><thead><tr>'
        "<th>日期</th><th>星期</th><th>节日</th>"
        "</tr></thead><tbody>" + rows(rest) + "</tbody></table></div></div>"
        '<div><h3>补班工作日</h3><div class="tbl-wrap"><table><thead><tr>'
        "<th>日期</th><th>星期</th><th>节日</th>"
        "</tr></thead><tbody>" + rows(work) + "</tbody></table></div></div>"
        "</div>"
    )


def school_ics(cc: str, name: str, year: int, ranges: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HolidayKit//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(name)} school holidays {year}",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for index, item in enumerate(ranges):
        try:
            start = date.fromisoformat(item["start"])
            end = date.fromisoformat(item["end"])
        except (KeyError, ValueError):
            continue
        summary = f"{item.get('name', 'School holiday')} ({item.get('region', '')})"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:school-{cc}-{year}-{index}@holidaykit",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(end + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{ics_escape(summary)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def page_school(cc: str, name: str, years_data: dict, site_url: str, verified: str) -> str:
    slug = slugify(name)
    years = sorted((int(y) for y in years_data), reverse=True)
    blocks: list[str] = []
    for year in years:
        ranges = years_data.get(str(year)) or years_data.get(year) or []
        if not ranges:
            continue
        rows = []
        for item in ranges:
            try:
                start = date.fromisoformat(item["start"])
                end = date.fromisoformat(item["end"])
            except (KeyError, ValueError):
                continue
            days = int(item.get("days") or ((end - start).days + 1))
            rows.append(
                "<tr>"
                f"<td>{esc(item.get('region', ''))}</td>"
                f"<td>{esc(item.get('name', ''))}</td>"
                f"<td>{esc(fmt_range(start, end))}</td>"
                f"<td>{days}</td>"
                "</tr>"
            )
        blocks.append(
            f'<section class="sec"><h2>{year} school holidays</h2>'
            '<div class="tbl-wrap"><table><thead><tr>'
            "<th>Region</th><th>Break</th><th>Dates</th><th>Days</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
            f'<p><a class="btn ghost" href="calendar-{year}.ics">Add {year} school calendar</a></p>'
            "</section>"
        )
    faq = [
        ("Are school holidays the same across the country?",
         "No — most countries set them region by region, so each region is listed separately."),
        ("Why are some years missing?",
         "School calendars are published progressively; future years are added as official sources release them."),
    ]
    body = (
        '<section class="hero-country"><div>'
        f'<p class="eyebrow">{esc(cc)} · school calendar</p>'
        f'<h1><span class="flag">{flag_emoji(cc)}</span> {esc(name)} school holidays</h1>'
        f'<p class="lede">Official school break dates for {esc(name)} by region, with one-click '
        "calendar subscriptions.</p></div>"
        '<aside class="next-holiday"><div class="flag">🎒</div><h3>What this is</h3>'
        '<p class="muted">School breaks by region from OpenHolidays. Region codes are the official '
        "subdivisions.</p></aside></section>"
        + "".join(blocks)
        + '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
        f'<p><a href="../index.html">← All school calendars</a> · '
        f'<a href="../../{slug}/index.html">Public holidays</a></p>'
    )
    first_year = years[0] if years else 2026
    return render_page(
        title=f"{name} School Holidays by Region | {SITE_NAME}",
        description=f"{name} school holiday dates by region (2025–2028), with calendar subscriptions.",
        canonical=f"{site_url}/school-holidays/{slug}/",
        base="../../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
        cta_href=f"calendar-{first_year}.ics",
        cta_label="Add school calendar",
    )


def page_school_index(items: list[tuple[str, str]], site_url: str, verified: str) -> str:
    cards = "".join(
        f'<a class="card" href="{slug}/index.html"><div class="flag">🎒</div>'
        f"<h3>{esc(name)}</h3><p>School breaks by region</p></a>"
        for slug, name in items
    )
    body = (
        '<section class="hero"><p class="eyebrow">School calendars</p>'
        "<h1>School holidays by country</h1>"
        '<p class="lede">Official school break dates by region, with calendar subscriptions.</p>'
        '</section>'
        '<section class="sec"><h2>Coverage</h2>'
        f'<p class="sub">Nationwide school calendars are published as open data for {len(items)} countries '
        '(Europe plus a growing set of national calendars). In most other countries school terms are set '
        "by province, state or individual school board, so no single national calendar exists to publish.</p>"
        f'<p class="sub">Know the official calendar for another country? '
        f'<a href="mailto:{CONTACT_EMAIL}?subject=School%20calendar%20for%20a%20country">Send the source link</a> '
        "and it will be added to this list.</p></section>"
        '<div class="grid">' + cards + "</div>"
        '<p><a href="../index.html">← All countries</a></p>'
    )
    return render_page(
        title=f"School Holidays by Country | {SITE_NAME}",
        description="School holiday dates by country and region, with calendar subscriptions.",
        canonical=f"{site_url}/school-holidays/",
        base="../",
        body=body,
        verified=verified,
    )


def page_compare(a: tuple, b: tuple, year: int, rows_a: list[dict], rows_b: list[dict],
                 site_url: str, verified: str) -> str:
    a_cc, a_name, a_slug = a
    b_cc, b_name, b_slug = b
    common = {r["date"] for r in rows_a} & {r["date"] for r in rows_b}
    pair_slug = f"{a_slug}-vs-{b_slug}-holidays"

    def holiday_table(rows: list[dict], label: str, link: str) -> str:
        body_rows = []
        for row in sorted(rows, key=lambda r: r["date"]):
            d = date.fromisoformat(row["date"])
            body_rows.append(
                "<tr>"
                f"<td>{esc(fmt_date(d))}</td>"
                f"<td>{esc(fmt_weekday(d))}</td>"
                f"<td>{esc(row['name'])}</td>"
                "</tr>"
            )
        return (
            f'<section class="sec"><h2><a href="{link}">{esc(label)}</a> — {year}</h2>'
            '<div class="tbl-wrap"><table><thead><tr><th>Date</th><th>Day</th><th>Holiday</th>'
            "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table></div></section>"
        )

    faq = [
        (f"Does {a_name} have more public holidays than {b_name}?",
         f"In {year}: {len(rows_a)} vs {len(rows_b)}. Regional holidays are included in the counts."),
        ("Which holidays fall on the same date?",
         f"{len(common)} dates overlap in {year} — see both tables above."),
    ]

    def _stats(rows: list[dict]) -> tuple[int, int]:
        weekend = 0
        months = [0] * 12
        for row in rows:
            try:
                d = date.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            months[d.month - 1] += 1
            if d.weekday() >= 5:
                weekend += 1
        return weekend, max(months) if months else 0

    a_wk, a_peak = _stats(rows_a)
    b_wk, b_peak = _stats(rows_b)
    peak = max(len(rows_a), len(rows_b)) or 1

    def _cmp_row(label: str, av: int, bv: int) -> str:
        aw, bw = round(av / peak * 100), round(bv / peak * 100)
        return (
            '<div class="row">'
            f'<div class="row-h"><span>{esc(label)}</span><span><b>{av}</b> · <b>{bv}</b></span></div>'
            f'<div class="track"><div class="fill" data-w="{aw}" style="width:{aw}%"></div></div>'
            f'<div class="track" style="margin-top:5px"><div class="fill b" data-w="{bw}" style="width:{bw}%"></div></div>'
            "</div>"
        )

    viz = (
        '<section class="sec"><h2><span class="sec-h-ico">⚖️</span>Head-to-head numbers</h2>'
        '<div class="kpi-row">'
        f'<div class="kpi"><span class="kpi-ico">🎉</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{len(rows_a)}">0</span>'
        f'<span class="kpi-l">{esc(a_name)} holidays</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">🎊</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{len(rows_b)}">0</span>'
        f'<span class="kpi-l">{esc(b_name)} holidays</span></span></div>'
        f'<div class="kpi"><span class="kpi-ico">🎯</span><span class="kpi-b">'
        f'<span class="kpi-n" data-countup="{len(common)}">0</span>'
        '<span class="kpi-l">same-date overlaps</span></span></div>'
        "</div>"
        '<div class="vz-cmp">'
        + _cmp_row("Public holidays", len(rows_a), len(rows_b))
        + _cmp_row("Falling on weekends", a_wk, b_wk)
        + _cmp_row("Busiest month", a_peak, b_peak)
        + "</div>"
        '<div class="vz-legend">'
        f'<span><i style="background:#34d399"></i>{esc(a_name)}</span>'
        f'<span><i style="background:#f59e0b"></i>{esc(b_name)}</span>'
        "</div>"
        f'<p class="viz-note">Side-by-side public holidays: {len(rows_a)} in {esc(a_name)}, '
        f"{len(rows_b)} in {esc(b_name)}, {len(common)} on the same date. Longer bars mean more of that "
        "number in the given year.</p></section>"
    )
    body = (
        '<section class="hero"><p class="eyebrow">Country comparison</p>'
        f"<h1>{esc(a_name)} vs {esc(b_name)} holidays {year}</h1>"
        '<div class="chips">'
        f'<span class="chip">{esc(a_name)}: {len(rows_a)} holidays</span>'
        f'<span class="chip">{esc(b_name)}: {len(rows_b)} holidays</span>'
        f'<span class="chip">Same date: {len(common)}</span>'
        "</div></section>"
        + viz
        + holiday_table(rows_a, a_name, f"../../{a_slug}/index.html")
        + holiday_table(rows_b, b_name, f"../../{b_slug}/index.html")
        + '<section class="ad">[Ad slot]</section>'
        + '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
        '<p><a href="../index.html">← All comparisons</a></p>'
    )
    return render_page(
        title=f"{a_name} vs {b_name} Holidays {year}: Side-by-Side | {SITE_NAME}",
        description=f"Compare {a_name} and {b_name} public holidays in {year}: {len(rows_a)} vs "
                    f"{len(rows_b)}, {len(common)} on the same date.",
        canonical=f"{site_url}/compare/{pair_slug}/",
        base="../../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
    )


def page_compare_index(items: list[tuple[str, str, str, int]], site_url: str, verified: str,
                       compare_data: list[dict] | None = None) -> str:
    cards = "".join(
        f'<a class="card" href="{pair_slug}/index.html"><div class="flag">⚖️</div>'
        f"<h3>{esc(a_name)} vs {esc(b_name)}</h3><p>Holidays side by side · {year}</p></a>"
        for pair_slug, a_name, b_name, year in items
    )
    pairs_block = (
        '<h2 class="cm-pairs">Popular comparisons</h2><div class="grid">' + cards + "</div>"
        if cards else ""
    )
    picker = (
        '<div class="cm-pick">'
        '<label>国家 A · Country A<select data-cm-a></select></label>'
        '<label>国家 B · Country B<select data-cm-b></select></label>'
        "</div>"
        '<div data-cm-out><p class="cm-note">Loading comparison…</p></div>'
    )
    body = (
        '<section class="hero"><p class="eyebrow">Compare</p>'
        "<h1>Compare public holidays between countries</h1>"
        '<p class="lede">Pick any two countries: holiday counts, key holidays side by side, and '
        "how holidays spread across the year — rendered live.</p></section>"
        '<section class="sec" id="hk-compare">' + picker + "</section>"
        + pairs_block
        + '<p><a href="../index.html">← All countries</a></p>'
    )
    extra = ""
    if compare_data:
        extra = (
            "window.HK_COMPARE="
            + json.dumps({"countries": compare_data}, ensure_ascii=False, separators=(",", ":"))
            + ";"
            + HOME_COMPARE_JS
        )
    return render_page(
        title=f"Compare Public Holidays Between Countries | {SITE_NAME}",
        description="Compare public holidays side by side for any two countries: holiday counts, "
                    "key holiday names and monthly distribution.",
        canonical=f"{site_url}/compare/",
        base="../",
        body=body,
        verified=verified,
        extra_js=extra,
    )


# ── holiday guides / countdowns / growth & monetisation ────────────────────

def holiday_slug(name: str) -> str:
    return slugify(name)


def next_occurrence(rows: list[dict], today: date) -> date | None:
    days = []
    for row in rows:
        try:
            days.append(date.fromisoformat(str(row["date"])))
        except (KeyError, ValueError):
            continue
    if not days:
        return None
    future = sorted(d for d in days if d >= today)
    return future[0] if future else sorted(days)[-1]


def load_official_sources(path: Path) -> dict[str, dict]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def official_source_html(cc: str) -> str:
    info = OFFICIAL_SOURCES.get(cc) or {}
    url = str(info.get("source") or "")
    if not url:
        return ""
    meta = ""
    if info.get("checked"):
        meta += f" · checked {esc(info['checked'])}"
    if info.get("notes"):
        meta += f" · {esc(info['notes'])}"
    return (
        '<section class="callout"><strong>Official source:</strong> '
        f'<a href="{esc(url)}" rel="nofollow noopener" target="_blank">{esc(url)}</a>{meta}'
        "</section>"
    )


def affiliate_block(place: str) -> str:
    url = AFFILIATE_URL or "#"
    return (
        '<section class="sec"><h2>Make it a trip</h2>'
        "<p>Long weekends are the best-value days to travel — and the first dates to sell out. "
        f"Compare flights and hotels around {esc(place)} before prices move.</p>"
        f'<p><a class="btn" href="{esc(url)}" rel="sponsored nofollow noopener" target="_blank">'
        'Compare flights &amp; hotels</a> <span class="muted">affiliate link</span></p>'
        "</section>"
    )


def embed_block(cc: str, year: int) -> str:
    snippet = (
        '<div id="holidaykit-widget"></div>\n'
        f'<script src="{SITE_URL}/widget.js" data-country="{cc}" '
        f'data-year="{year}" data-target="holidaykit-widget"></script>'
    )
    return (
        '<section class="sec"><h2>Embed this calendar</h2>'
        "<p>Drop this snippet into any page — it renders a live holiday list with no API key.</p>"
        f'<pre class="code">{esc(snippet)}</pre>'
        f'<p><a class="btn ghost" href="{SITE_URL}/embed/index.html">See the live demo</a></p>'
        "</section>"
    )


def popular_sections(catalog: dict, today: date) -> str:
    items = sorted(catalog.items(), key=lambda kv: (-len({r["country"] for r in kv[1]}), kv[0]))
    guide_cards: list[str] = []
    countdown_cards: list[str] = []
    for name, rows in items[:12]:
        nxt = next_occurrence(rows, today)
        if not nxt:
            continue
        slug = holiday_slug(name)
        meta = f"next {fmt_date(nxt)}"
        n_countries = len({r["country"] for r in rows})
        guide_cards.append(
            f'<a class="card" href="holidays/{slug}/index.html">'
            f"<h3>{esc(name)}</h3><p>{esc(meta)} · {n_countries} countries</p></a>"
        )
        countdown_cards.append(
            f'<a class="card" href="days-until/{slug}/index.html">'
            f"<h3>{esc(name)}</h3><p>{esc(meta)}</p></a>"
        )
    return (
        '<section class="sec"><h2>Popular holiday guides</h2><div class="grid">'
        + "".join(guide_cards)
        + '</div><p><a class="btn ghost" href="holidays/index.html">All holiday guides</a></p></section>'
        '<section class="sec"><h2>Live countdowns</h2><div class="grid">'
        + "".join(countdown_cards)
        + '</div><p><a class="btn ghost" href="days-until/index.html">All countdowns</a></p></section>'
        '<section class="sec"><h2>Build on HolidayKit</h2><div class="grid">'
        '<a class="card" href="api/index.html"><h3>Free API</h3>'
        "<p>JSON for every country and year. CORS enabled, no key required.</p></a>"
        '<a class="card" href="embed/index.html"><h3>Embed widget</h3>'
        "<p>A live holiday calendar in one script tag.</p></a>"
        '<a class="card" href="compare/index.html"><h3>Compare countries</h3>'
        "<p>Side-by-side holidays for expats and remote workers.</p></a>"
        '<a class="card" href="school-holidays/index.html"><h3>School holidays</h3>'
        "<p>Official school breaks by region, with calendar links.</p></a>"
        '<a class="card" href="premium/index.html"><h3>Premium</h3>'
        "<p>Multi-country planner, alerts and PTO export — coming soon.</p></a>"
        "</div></section>"
    )


def page_holiday(kind: str, slug: str, name: str, rows: list[dict], site_url: str,
                 verified: str, today: date) -> str:
    countries = sorted({r["country"] for r in rows})
    nxt = next_occurrence(rows, today)
    by_date: dict[date, list[dict]] = defaultdict(list)
    for row in rows:
        try:
            by_date[date.fromisoformat(str(row["date"]))].append(row)
        except (KeyError, ValueError):
            continue
    all_dates = sorted(by_date)
    future = [d for d in all_dates if d >= today][:8] or all_dates[-8:]
    date_rows: list[str] = []
    for day in future:
        names = sorted({country_name(r["country"]) for r in by_date[day]})
        date_rows.append(
            "<tr>"
            f"<td>{esc(fmt_date(day))}</td>"
            f"<td>{esc(fmt_weekday(day))}</td>"
            f'<td data-date="{esc(day.isoformat())}" data-countdown></td>'
            f"<td>{esc(', '.join(names))}</td>"
            "</tr>"
        )
    table = (
        '<div class="tbl-wrap"><table><thead><tr>'
        "<th>Date</th><th>Day</th><th>Countdown</th><th>Countries</th>"
        "</tr></thead><tbody>" + "".join(date_rows) + "</tbody></table></div>"
    )
    country_links = " · ".join(
        f'<a href="../../{slugify(country_name(cc))}/index.html">{esc(country_name(cc))}</a>'
        for cc in countries
    )
    next_label = fmt_date(nxt) if nxt else "unknown"

    if kind == "countdown":
        h1 = f"Days until {name}"
        lede = f"Live countdown to the next {name} ({next_label}), with dates by country."
        box = ""
        if nxt:
            year_start = date(nxt.year, 1, 1)
            span = max(1, (nxt - year_start).days)
            pct = max(0.0, min(1.0, (today - year_start).days / span))
            days_left = max(0, (nxt - today).days)
            circ = 314.159
            box = (
                '<div class="donut-wrap">'
                f'<svg class="vz-donut" data-donut="{pct:.3f}" viewBox="0 0 120 120" aria-hidden="true">'
                '<circle class="bg" cx="60" cy="60" r="50"></circle>'
                f'<circle class="fg" cx="60" cy="60" r="50" style="stroke-dasharray:{circ};'
                f'stroke-dashoffset:{circ * (1 - pct):.1f}"></circle></svg>'
                '<div class="donut-txt">'
                f'<span class="big" data-countup="{days_left}">0</span>'
                f'<span class="muted">days until {esc(name)} · {esc(next_label)}</span>'
                f"<span class=\"muted\">{int(pct * 100)}% of this year's wait is behind you</span>"
                "</div>"
                f'<div class="countdown" data-date="{esc(nxt.isoformat())}"><span data-countdown></span></div>'
                "</div>"
                '<div class="vz-legend"><span>🌍 ' + str(len(countries)) + " countries</span>"
                "<span>📅 next " + esc(next_label) + "</span></div>"
            )
        title = f"Days Until {name} — Live Countdown | {SITE_NAME}"
        description = f"Countdown to the next {name} ({next_label}). Dates by country and calendar links."
        canonical = f"{site_url}/days-until/{slug}/"
    else:
        h1 = f"{name}: dates, countries and long weekends"
        lede = f"When is {name}? Next date: {next_label}. Full list of countries and upcoming dates."
        box = ""
        title = f"{name} — Dates, Countries & Long Weekends | {SITE_NAME}"
        description = f"{name} dates by country ({next_label}). Upcoming occurrences and calendar links."
        canonical = f"{site_url}/holidays/{slug}/"

    faq = [
        (f"When is {name} next?", f"The next occurrence is {next_label}."),
        ("Is it a public holiday everywhere?",
         "Not always — check each country page for regional and state-level differences."),
    ]
    body = (
        '<section class="hero">'
        f"<h1>{esc(h1)}</h1>" + box
        + (f'<p class="viz-note">{esc(lede)}</p>' if kind == "countdown"
           else f'<p class="lede">{esc(lede)}</p>')
        + "</section>"
        '<section class="sec"><h2>Upcoming dates</h2>' + table + "</section>"
        '<section class="ad">[Ad slot]</section>'
        '<section class="sec"><h2>Observed in</h2><p>' + country_links + "</p></section>"
        + affiliate_block(name)
        + '<section class="sec"><h2>FAQ</h2>' + faq_block(faq) + "</section>"
        '<p><a href="../../index.html">← All countries</a> · '
        '<a href="../../holidays/index.html">Holiday guides</a> · '
        '<a href="../../days-until/index.html">Countdowns</a></p>'
    )
    return render_page(
        title=title,
        description=description,
        canonical=canonical,
        base="../../",
        body=body,
        verified=verified,
        json_ld=faq_json_ld(faq),
    )


def holiday_index_page(kind: str, items: list[tuple[str, str]], site_url: str, verified: str,
                       meta: dict | None = None) -> str:
    path = "holidays" if kind == "holiday" else "days-until"
    heading = "Holiday guides" if kind == "holiday" else "Holiday countdowns"
    meta = meta or {}

    def _card(slug: str, name: str) -> str:
        m = meta.get(name) or {}
        countries = m.get("countries") or 0
        days = m.get("days")
        months = m.get("months") or []
        mx = (max(months) if months else 1) or 1
        spark = "".join(
            f'<i style="height:{max(6, round(v / mx * 100))}%"></i>' for v in months
        ) if months else ""
        next_lbl = ""
        if days is not None:
            next_lbl = f"in {days} day{'s' if days != 1 else ''}" if days >= 0 else "today"
        if kind == "countdown" and days is not None:
            pct = max(3, min(100, round(100 - days / 365 * 100)))
            return (
                f'<a class="card" href="{slug}/index.html"><h3>{esc(name)}</h3>'
                f'<p>{countries} countries · next {next_lbl}</p>'
                f'<span class="prog" aria-hidden="true"><i style="width:{pct}%"></i></span></a>'
            )
        return (
            f'<a class="card" href="{slug}/index.html"><h3>{esc(name)}</h3>'
            f'<p>{countries} countries · {next_lbl or "dates by year"}</p>'
            f'<span class="gspark" aria-hidden="true">{spark}</span>'
            '<div class="gmeta">'
            f'<span>by month</span><span>{countries} countries</span>'
            "</div></a>"
        )

    cards = "".join(_card(slug, name) for slug, name in items)
    body = (
        f'<section class="hero"><h1>{esc(heading)}</h1>'
        '<p class="lede">Pick a holiday to see its dates across countries, a live countdown '
        "and calendar links.</p></section>"
        '<div class="grid">' + cards + "</div>"
        '<p><a href="../index.html">← All countries</a></p>'
    )
    return render_page(
        title=f"{heading} | {SITE_NAME}",
        description=f"{heading}: dates, countdowns and calendar links for every major public holiday.",
        canonical=f"{site_url}/{path}/",
        base="../",
        body=body,
        verified=verified,
    )


def page_premium(site_url: str, verified: str) -> str:
    plans = [
        ("Free", "$0", [
            "Every public holiday page",
            "ICS calendar subscriptions",
            "Free API (fair use)",
            "Long weekend lists",
        ]),
        ("Pro", "$2.99 / month", [
            "Everything in Free",
            "Multi-country comparison",
            "Long weekend email alerts",
            "PTO planner + PDF / ICS export",
            "Ad-free, higher API limits",
        ]),
        ("Team", "$9 / month", [
            "Everything in Pro",
            "5 seats",
            "Team holiday calendar (multi-country)",
            "CSV / API bulk export",
            "Priority data corrections",
        ]),
    ]
    cards: list[str] = []
    for plan_name, amount, features in plans:
        featured = " featured" if plan_name == "Pro" else ""
        items = "".join(f"<li>{esc(feature)}</li>" for feature in features)
        cards.append(
            f'<div class="price{featured}"><h3>{esc(plan_name)}</h3>'
            f'<div class="amount">{esc(amount)}</div><ul>{items}</ul></div>'
        )
    body = (
        '<section class="hero"><h1>HolidayKit Premium</h1>'
        '<p class="lede">Free is enough to look up dates. Premium is for people who plan around them: '
        "multi-country views, alerts before the long weekend sells out, and a leave planner.</p></section>"
        '<div class="price-grid">' + "".join(cards) + "</div>"
        '<p class="muted">Billing is not live yet — join the waitlist and we will email you at launch.</p>'
        f'<p><a class="btn" href="mailto:{esc(CONTACT_EMAIL)}?subject=HolidayKit%20Premium%20waitlist">'
        "Join the waitlist</a></p>"
        '<p><a href="../index.html">← Back to all countries</a></p>'
    )
    return render_page(
        title=f"Premium — multi-country holiday planner | {SITE_NAME}",
        description="HolidayKit Premium: multi-country comparison, long weekend alerts, "
                    "PTO planner and ad-free API.",
        canonical=f"{site_url}/premium/",
        base="../",
        body=body,
        verified=verified,
    )


def page_api_docs(site_url: str, verified: str, countries: list[tuple[str, str, str]]) -> str:
    sample_cc = countries[0][0] if countries else "US"
    sample_name = countries[0][1] if countries else "United States"
    example = (
        "{\n"
        '  "country": "' + sample_cc + '",\n'
        '  "name": "' + sample_name + '",\n'
        '  "year": 2026,\n'
        '  "holidays": [\n'
        '    {"date": "2026-01-01", "name": "New Year\'s Day", "types": ["Public", "Bank"], '
        '"global": true, "counties": []}\n'
        "  ]\n"
        "}"
    )
    codes = ", ".join(cc for cc, _, _ in countries[:24])
    body = (
        '<section class="hero"><h1>Free holiday API</h1>'
        '<p class="lede">Every country and year as static JSON. CORS enabled, no API key, and a generous '
        'fair-use policy — please cache responses and attribute HolidayKit. If you need commercial or '
        'high-volume use, see <a href="../support/index.html">Support</a> for a sponsor licence.</p></section>'
        '<section class="sec"><h2>Endpoints</h2>'
        '<pre class="code">'
        + "GET " + site_url + "/api/v1/countries.json\n"
        + "GET " + site_url + "/api/v1/holidays/{country}/{year}.json\n"
        + "GET " + site_url + "/api/v1/holidays/" + sample_cc + "/2026.json   (example)\n"
        + "</pre></section>"
        '<section class="sec"><h2>Example response</h2>'
        f'<pre class="code">{esc(example)}</pre></section>'
        '<section class="sec"><h2>Notes</h2><ul>'
        "<li>Country codes are ISO 3166-1 alpha-2: " + esc(codes) + ", …</li>"
        "<li>Rows include <code>types</code> (Public / Bank / School), <code>global</code> and "
        "<code>counties</code> (regional scope).</li>"
        "<li>Data is rebuilt when sources change; see <code>generatedAt</code> in countries.json.</li>"
        "<li>Rate limit: 240 requests/minute per IP. Over the limit returns HTTP 429 with "
        "<code>Retry-After</code>; responses are cacheable for a day, so cache them.</li>"
        "<li>Commercial use under the free tier requires a link back to HolidayKit. For high-volume "
        'or paid usage, see <a href="../support/index.html">Support</a>.</li>'
        "</ul></section>"
        '<section class="sec"><h2>Embed instead</h2>'
        f'<p><a href="{site_url}/embed/index.html">Use the one-line widget</a> if you just want a calendar '
        "on a page.</p></section>"
        '<p><a href="../index.html">← Back to all countries</a></p>'
    )
    return render_page(
        title=f"Free Public Holiday API — JSON by country and year | {SITE_NAME}",
        description="Free static JSON API for public holidays by country and year. CORS enabled, no key required.",
        canonical=f"{site_url}/api/",
        base="../",
        body=body,
        verified=verified,
    )


def page_embed_demo(site_url: str, verified: str, cc: str, name: str, year: int) -> str:
    snippet = (
        '<div id="holidaykit-widget"></div>\n'
        f'<script src="{site_url}/widget.js" data-country="{cc}" '
        f'data-year="{year}" data-target="holidaykit-widget"></script>'
    )
    body = (
        '<section class="hero"><h1>Embed the holiday calendar</h1>'
        '<p class="lede">Paste one script tag and get a live holiday list for any country. '
        "No API key, no build step, works on any HTML page.</p></section>"
        '<section class="sec"><h2>Live example — ' + esc(name) + " " + str(year) + "</h2>"
        '<div id="holidaykit-widget"></div>'
        f'<script src="{site_url}/widget.js" data-country="{cc}" '
        f'data-year="{year}" data-target="holidaykit-widget"></script>'
        "</section>"
        '<section class="sec"><h2>Copy this</h2>'
        f'<pre class="code">{esc(snippet)}</pre></section>'
        '<p><a href="../index.html">← Back to all countries</a></p>'
    )
    return render_page(
        title=f"Embed a Holiday Calendar — free widget | {SITE_NAME}",
        description="Free embeddable holiday calendar widget for any website. One script tag, no API key.",
        canonical=f"{site_url}/embed/",
        base="../",
        body=body,
        verified=verified,
    )


WIDGET_JS = r"""
(function () {
  var script = document.currentScript;
  if (!script) return;
  var base = script.src.replace(/widget\.js(\?.*)?$/, '');
  var cc = (script.getAttribute('data-country') || 'US').toUpperCase();
  var year = script.getAttribute('data-year') || String(new Date().getFullYear());
  var target = document.getElementById(script.getAttribute('data-target') || 'holidaykit-widget');
  if (!target) return;
  target.innerHTML = '<p style="font:14px system-ui;color:#6b7280">Loading holidays…</p>';
  fetch(base + 'api/v1/holidays/' + cc + '/' + year + '.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      var rows = (data.holidays || []).slice(0, 40).map(function (h) {
        var d = new Date(h.date + 'T00:00:00');
        var label = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
        return '<li style="display:flex;justify-content:space-between;gap:12px;padding:6px 0;' +
          'border-bottom:1px solid #e5e7eb"><span>' + label + '</span><span>' + h.name + '</span></li>';
      }).join('');
      target.innerHTML = '<div style="font:14px/1.5 system-ui;color:#111827">' +
        '<p style="margin:0 0 6px;font-weight:600">' + data.name + ' public holidays ' + data.year + '</p>' +
        '<ul style="list-style:none;margin:0;padding:0">' + rows + '</ul>' +
        '<p style="margin:8px 0 0;font-size:12px;color:#6b7280">Powered by HolidayKit</p></div>';
    })
    .catch(function () {
      target.innerHTML = '<p style="font:14px system-ui;color:#b91c1c">Holiday data unavailable.</p>';
    });
})();
"""


# ── main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Build the HolidayKit static site")
    parser.add_argument("--data", default=str(ROOT / "data" / "holidays.json"))
    parser.add_argument("--out", default=str(ROOT / "dist"))
    parser.add_argument("--site-url", default="https://holidaykit.example")
    parser.add_argument("--verified", default=date.today().isoformat())
    parser.add_argument("--official-sources", default=str(ROOT / "data" / "official_sources.json"))
    parser.add_argument("--affiliate-url", nargs="?", const="", default="", help="travel affiliate CTA URL")
    parser.add_argument("--contact-email", default="hello@example.com")
    parser.add_argument("--adsense-client", nargs="?", const="", default="", help="AdSense publisher id, e.g. pub-0000000000000000")
    parser.add_argument("--google-site-verification", nargs="?", const="", default="", help="Google Search Console verification token")
    parser.add_argument("--indexnow-key", nargs="?", const="", default="", help="IndexNow key (written as /{key}.txt for Bing/Yandex)")
    args = parser.parse_args()

    global SITE_URL, AFFILIATE_URL, CONTACT_EMAIL, ADSENSE_CLIENT, OFFICIAL_SOURCES, OG_IMAGE, GOOGLE_VERIFY, SCHOOL_DATA, SCHOOL_NAMES, CN_CAL
    SITE_URL = args.site_url.rstrip("/")
    AFFILIATE_URL = args.affiliate_url
    CONTACT_EMAIL = args.contact_email
    ADSENSE_CLIENT = args.adsense_client
    GOOGLE_VERIFY = args.google_site_verification.strip()
    OFFICIAL_SOURCES = load_official_sources(Path(args.official_sources))
    SCHOOL_DATA, SCHOOL_NAMES = load_school(ROOT / "data" / "school.json")
    _extra_data, _extra_names = load_school_extra(ROOT)
    for _cc, _years in _extra_data.items():
        _target = SCHOOL_DATA.setdefault(_cc, {})
        for _y, _items in _years.items():
            _target.setdefault(_y, []).extend(_items)
        SCHOOL_NAMES.setdefault(_cc, _extra_names.get(_cc, _cc))
        for _y in _target:
            _target[_y] = sorted(_target[_y], key=lambda r: (r["start"], r["name"]))
    CN_CAL = load_cn_calendar(ROOT / "data" / "cn_calendar.json")
    OG_IMAGE = (ROOT / "assets" / "og-cover.png").exists()

    data_path = Path(args.data)
    sample_path = ROOT / "data" / "sample-holidays.json"
    if not data_path.exists() and sample_path.exists():
        print(f"Data file not found ({data_path}); falling back to {sample_path.name} (sample data).")
        data_path = sample_path
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Run: python scripts/collect.py   (or try --data data/sample-holidays.json)")
        return 1

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    rows = payload.get("holidays", []) if isinstance(payload, dict) else payload
    public_rows = [r for r in rows if is_public(r) and "School" not in (r.get("types") or [])]

    by_country = defaultdict(lambda: defaultdict(list))
    for row in public_rows:
        try:
            year = int(row.get("year") or str(row["date"])[:4])
        except (KeyError, ValueError):
            continue
        by_country[row["country"]][year].append(row)

    if not by_country:
        print("No public holidays found in the data file.")
        return 1

    # Enrich China rows with Chinese local names from 调休/补班 data
    cn_names: dict[str, str] = {}
    for _year_key, _data in (CN_CAL or {}).items():
        for _item in (_data.get("rest") or []) + (_data.get("work") or []):
            if _item.get("date") and _item.get("name"):
                cn_names[_item["date"]] = _item["name"]
    if cn_names and "CN" in by_country:
        for _rows in by_country["CN"].values():
            for _row in _rows:
                _zh = cn_names.get(str(_row.get("date")))
                if _zh and _zh != _row.get("name"):
                    _row["localName"] = _zh

    countries = []
    used_slugs = set()
    for cc in sorted(by_country):
        name = country_name(cc)
        slug = slugify(name)
        if slug in used_slugs:
            slug = f"{slug}-{slugify(cc)}"
        used_slugs.add(slug)
        countries.append((cc, name, slug))
    countries.sort(key=lambda c: c[1])

    site_url = args.site_url.rstrip("/")
    verified = args.verified
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    urls: list[tuple[str, str]] = []

    today = date.today()
    catalog: dict[str, list[dict]] = defaultdict(list)
    for row in public_rows:
        catalog[row["name"]].append(row)

    # share-card QR codes: one per country pointing at its focus-year page
    qr_dir = out / "assets" / "qr"
    qr_dir.mkdir(parents=True, exist_ok=True)
    make_qr(f"{site_url}/", qr_dir / "root.png")
    for cc, name, slug in countries:
        focus = pick_focus_year(by_country[cc].keys(), today)
        make_qr(f"{site_url}/{slug}/{focus}/", qr_dir / f"{slug}.png")

    # index
    (out / "index.html").write_text(
        page_index(countries, by_country, site_url, verified, catalog, today), encoding="utf-8"
    )
    urls.append(("", "1.0"))

    # localized home pages + hreflang
    for lang in HOME_I18N:
        lang_dir = out / lang
        lang_dir.mkdir(exist_ok=True)
        (lang_dir / "index.html").write_text(
            page_lang_home(lang, countries, by_country, site_url, verified, today),
            encoding="utf-8",
        )
        urls.append((f"{lang}/", "0.8"))

    # subscribe hub: one URL per country, iOS/macOS/Google/Outlook
    sub_rows = []
    for cc, name, slug in countries:
        y = today.year if today.year in by_country[cc] else max(by_country[cc])
        ics = f"{site_url}/{slug}/calendar-{y}.ics"
        sub_rows.append(
            f'<tr><td><a href="{slug}/index.html">{esc(name)}</a></td><td>{y}</td>'
            f'<td><a href="{webcal_url(ics)}">📱 Subscribe</a> · '
            f'<a href="{ics}">.ics</a> · '
            f'<a href="{google_cal_url(ics)}" target="_blank" rel="noopener">Google</a> · '
            f'<a href="{outlook_cal_url(ics)}" target="_blank" rel="noopener">Outlook</a></td></tr>'
        )
    sub_body = (
        '<section class="hero"><p class="eyebrow">Calendar subscriptions</p>'
        "<h1>Subscribe to any country's holidays</h1>"
        '<p class="lede">One URL, auto-updating — no .ics file import. iPhone, iPad, Mac, Android, '
        "Google Calendar and Outlook all support URL subscriptions.</p></section>"
        '<section class="sec"><h2>How it works</h2><div class="sub-help">'
        "<details open><summary>iPhone / iPad / Mac — subscribe (auto-updates)</summary><ol>"
        "<li>Tap a <strong>Subscribe</strong> link below → Calendar opens → tap <strong>Subscribe</strong>.</li>"
        "<li>Or: Settings → Calendar → Accounts → Add Account → Other → "
        "<strong>Add Subscribed Calendar</strong>, then paste the .ics URL.</li>"
        "<li>Subscribed calendars refresh automatically; you never re-import.</li></ol></details>"
        "<details><summary>Android (Google Calendar)</summary><ol>"
        "<li>Google Calendar → Other calendars → “+” → <strong>From URL</strong>.</li>"
        "<li>Paste the .ics URL → Add calendar.</li></ol></details>"
        "<details><summary>Outlook / Windows</summary><ol>"
        "<li>Outlook → Calendar → Add calendar → <strong>Subscribe from web</strong>.</li>"
        "<li>Paste the .ics URL → Import.</li></ol></details>"
        "</div></section>"
        '<section class="sec"><h2>All countries</h2><div class="tbl-wrap"><table><thead><tr>'
        "<th>Country</th><th>Year</th><th>Subscribe</th></tr></thead><tbody>"
        + "".join(sub_rows) + "</tbody></table></div></section>"
    )
    (out / "subscribe").mkdir(exist_ok=True)
    (out / "subscribe" / "index.html").write_text(
        render_page(
            title="Subscribe to holiday calendars — one URL, auto-updating",
            description="Subscribe to any country's public holiday calendar by URL. Works with iPhone, "
                        "iPad, Mac, Android, Google Calendar and Outlook — no .ics import needed.",
            canonical=f"{site_url}/subscribe/",
            base="../",
            body=sub_body,
            verified=verified,
        ),
        encoding="utf-8",
    )
    urls.append(("subscribe/", "0.7"))

    # Android one-tap setup pages (/go/{country}/) + hub
    (out / "go").mkdir(exist_ok=True)
    go_rows = []
    for cc, name, slug in countries:
        gyears = sorted(int(y) for y in by_country[cc].keys())
        gyear = pick_focus_year(gyears, today)
        gdir = out / "go" / slug
        gdir.mkdir(exist_ok=True)
        (gdir / "index.html").write_text(
            go_page(cc, name, slug, gyear, site_url, verified), encoding="utf-8"
        )
        ics = f"{site_url}/{slug}/calendar-{gyear}.ics"
        go_rows.append(
            f'<tr><td><a href="{slug}/index.html">{esc(name)}</a></td><td>{gyear}</td>'
            f'<td><a href="{slug}/index.html">📱 One-tap setup</a></td>'
            f'<td><a href="{ics}">.ics</a></td></tr>'
        )
    go_body = (
        '<section class="hero"><p class="eyebrow">Android subscriptions</p>'
        "<h1>One-tap setup for Android</h1>"
        '<p class="lede">Pick a country: we copy the calendar link and open Google Calendar’s '
        "“Add by URL”, where you paste it once. After that the calendar updates automatically.</p></section>"
        '<section class="sec"><h2>All countries</h2><div class="tbl-wrap"><table><thead><tr>'
        "<th>Country</th><th>Year</th><th>Setup</th><th>Direct .ics</th></tr></thead><tbody>"
        + "".join(go_rows) + "</tbody></table></div></section>"
        '<div class="callout">Why not one tap like iOS? Android has no system handler for '
        "<code>webcal://</code> links — so we copy the link and open Google Calendar for you.</div>"
    )
    (out / "go" / "index.html").write_text(
        render_page(
            title="Android one-tap calendar subscription setup",
            description="Guided Android setup to subscribe to holiday calendars via Google Calendar From URL or ICSx5.",
            canonical=f"{site_url}/go/",
            base="../",
            body=go_body,
            verified=verified,
            robots="noindex,follow",
        ),
        encoding="utf-8",
    )

    for cc, name, slug in countries:
        years = sorted(by_country[cc].keys(), reverse=True)
        all_rows = [r for y in years for r in by_country[cc][y]]

        country_dir = out / slug
        country_dir.mkdir(parents=True, exist_ok=True)
        (country_dir / "index.html").write_text(
            page_country(cc, name, slug, by_country, site_url, verified), encoding="utf-8"
        )
        urls.append((f"{slug}/", "0.9"))

        # calendar subscription page
        cal_dir = country_dir / "calendar"
        cal_dir.mkdir(parents=True, exist_ok=True)
        (cal_dir / "index.html").write_text(
            page_calendar(cc, name, slug, years, site_url, verified), encoding="utf-8"
        )
        urls.append((f"{slug}/calendar/", "0.6"))

        for year in years:
            year_rows = by_country[cc][year]
            runs = compute_long_weekends(all_rows, year)

            year_dir = country_dir / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            (year_dir / "index.html").write_text(
                page_year(cc, name, slug, year, year_rows, runs, site_url, verified), encoding="utf-8"
            )
            urls.append((f"{slug}/{year}/", "0.8"))

            lw_dir = year_dir / "long-weekends"
            lw_dir.mkdir(parents=True, exist_ok=True)
            (lw_dir / "index.html").write_text(
                page_long_weekends(cc, name, slug, year, runs, site_url, verified), encoding="utf-8"
            )
            urls.append((f"{slug}/{year}/long-weekends/", "0.7"))

            (country_dir / f"calendar-{year}.ics").write_text(
                build_ics(cc, name, year, year_rows, cn_year_data(year) if cc == "CN" else None),
                encoding="utf-8",
            )

    # ── long weekends hub ──
    all_years = sorted({y for cc, _, _ in countries for y in by_country[cc]})
    lw_focus = pick_focus_year(all_years, today)
    lw_by_year: dict[int, list[dict]] = {}
    for year in all_years:
        rows_for_year = []
        for cc, name, slug in countries:
            year_rows = by_country[cc].get(year)
            if not year_rows:
                continue
            best = _lw_best(compute_long_weekends(year_rows, year))
            if not best:
                continue
            rows_for_year.append({**best, "cc": cc, "name": name, "slug": slug})
        rows_for_year.sort(key=lambda r: (-r["total"], r["pto"], r["name"]))
        lw_by_year[year] = rows_for_year

    lw_dir = out / "long-weekends"
    lw_dir.mkdir(parents=True, exist_ok=True)
    focus_top = lw_by_year.get(lw_focus) or []
    (lw_dir / "index.html").write_text(
        page_lw_index(all_years, lw_focus, focus_top, {y: (rows[0]["total"] if rows else 0) for y, rows in lw_by_year.items()}, site_url, verified), encoding="utf-8"
    )
    urls.append(("long-weekends/", "0.8"))
    for year in all_years:
        ydir = lw_dir / str(year)
        ydir.mkdir(parents=True, exist_ok=True)
        (ydir / "index.html").write_text(
            page_lw_year(year, lw_by_year[year], site_url, verified), encoding="utf-8"
        )
        urls.append((f"long-weekends/{year}/", "0.8"))

    # 404
    (out / "404.html").write_text(page_not_found(site_url, verified), encoding="utf-8")

    # ── worldwide calendar by month ──
    cal_dir = out / "calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_counts: dict[int, list[int]] = {}
    for year in all_years:
        cal_counts[year] = _month_counts(by_country, countries, year)
    (cal_dir / "index.html").write_text(
        page_month_index(all_years, cal_counts, site_url, verified), encoding="utf-8")
    urls.append(("calendar/", "0.8"))
    for year in all_years:
        ydir = cal_dir / str(year)
        ydir.mkdir(parents=True, exist_ok=True)
        (ydir / "index.html").write_text(
            page_month_year(year, cal_counts[year], site_url, verified), encoding="utf-8")
        urls.append((f"calendar/{year}/", "0.7"))
        for month in range(1, 13):
            entries = _month_entries(by_country, countries, year, month)
            mdir = ydir / str(month)
            mdir.mkdir(parents=True, exist_ok=True)
            (mdir / "index.html").write_text(
                page_month(year, month, entries, site_url, verified), encoding="utf-8")
            urls.append((f"calendar/{year}/{month}/", "0.6"))
    CAL_YEARS = list(all_years)

    # ── holiday guides & countdowns ──
    ranked = sorted(catalog.items(), key=lambda kv: (-len({r["country"] for r in kv[1]}), kv[0]))
    top_items = [(holiday_slug(name), name) for name, _ in ranked[:150]]
    for hslug, hname in top_items:
        hdir = out / "holidays" / hslug
        hdir.mkdir(parents=True, exist_ok=True)
        (hdir / "index.html").write_text(
            page_holiday("holiday", hslug, hname, catalog[hname], site_url, verified, today),
            encoding="utf-8",
        )
        urls.append((f"holidays/{hslug}/", "0.6"))
        cdir = out / "days-until" / hslug
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "index.html").write_text(
            page_holiday("countdown", hslug, hname, catalog[hname], site_url, verified, today),
            encoding="utf-8",
        )
        urls.append((f"days-until/{hslug}/", "0.6"))

    meta_count = {}
    _catalog_years = set()
    for _rows in catalog.values():
        for _row in _rows:
            try:
                _catalog_years.add(date.fromisoformat(_row["date"]).year)
            except (KeyError, ValueError):
                continue
    _catalog_focus = pick_focus_year(_catalog_years, today)
    for _hslug, _hname in top_items:
        _rows = catalog[_hname]
        _ccs = {r["country"] for r in _rows}
        _fut = sorted(r["date"] for r in _rows if r["date"] >= today.isoformat())
        _d = (date.fromisoformat(_fut[0]) - today).days if _fut else None
        _mon = [0] * 12
        for _row in _rows:
            try:
                _rd = date.fromisoformat(_row["date"])
            except (KeyError, ValueError):
                continue
            if _rd.year == _catalog_focus:
                _mon[_rd.month - 1] += 1
        meta_count[_hname] = {"countries": len(_ccs), "days": _d, "months": _mon}

    (out / "holidays").mkdir(exist_ok=True)
    (out / "holidays" / "index.html").write_text(
        holiday_index_page("holiday", top_items, site_url, verified, meta_count), encoding="utf-8")
    urls.append(("holidays/", "0.7"))
    (out / "days-until").mkdir(exist_ok=True)
    (out / "days-until" / "index.html").write_text(
        holiday_index_page("countdown", top_items, site_url, verified, meta_count), encoding="utf-8")
    urls.append(("days-until/", "0.7"))

    # ── school holidays ──
    if SCHOOL_DATA:
        school_items = []
        for cc in sorted(SCHOOL_DATA):
            name = COUNTRY_NAMES.get(cc) or SCHOOL_NAMES.get(cc) or cc
            sdir = out / "school-holidays" / slugify(name)
            sdir.mkdir(parents=True, exist_ok=True)
            (sdir / "index.html").write_text(
                page_school(cc, name, SCHOOL_DATA[cc], site_url, verified), encoding="utf-8")
            school_items.append((slugify(name), name))
            urls.append((f"school-holidays/{slugify(name)}/", "0.7"))
            for year in sorted(int(y) for y in SCHOOL_DATA[cc]):
                ranges = SCHOOL_DATA[cc].get(str(year)) or []
                if ranges:
                    (sdir / f"calendar-{year}.ics").write_text(
                        school_ics(cc, name, year, ranges), encoding="utf-8")
        (out / "school-holidays").mkdir(exist_ok=True)
        (out / "school-holidays" / "index.html").write_text(
            page_school_index(school_items, site_url, verified), encoding="utf-8")
        urls.append(("school-holidays/", "0.7"))

    # ── country comparisons ──
    country_by_code = {c[0]: c for c in countries}
    compare_pairs = [
        ("US", "GB"), ("US", "CA"), ("US", "AU"), ("US", "DE"), ("US", "JP"),
        ("GB", "DE"), ("GB", "FR"), ("GB", "IE"), ("DE", "FR"), ("DE", "AT"),
        ("FR", "ES"), ("ES", "IT"), ("NL", "BE"), ("CH", "AT"), ("SE", "NO"),
        ("PL", "CZ"), ("AU", "NZ"), ("JP", "KR"), ("CN", "HK"), ("SG", "MY"),
        ("BR", "MX"), ("CA", "AU"), ("GB", "JP"), ("IN", "PK"),
    ]
    compare_items = []
    for a_cc, b_cc in compare_pairs:
        if a_cc not in country_by_code or b_cc not in country_by_code:
            continue
        common_years = set(by_country[a_cc]) & set(by_country[b_cc])
        if not common_years:
            continue
        year = 2026 if 2026 in common_years else max(common_years)
        a = country_by_code[a_cc]
        b = country_by_code[b_cc]
        pair_slug = f"{a[2]}-vs-{b[2]}-holidays"
        pdir = out / "compare" / pair_slug
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "index.html").write_text(
            page_compare(a, b, year, by_country[a_cc][year], by_country[b_cc][year],
                         site_url, verified),
            encoding="utf-8",
        )
        compare_items.append((pair_slug, a[1], b[1], year))
        urls.append((f"compare/{pair_slug}/", "0.6"))
    compare_data = []
    for cc, name, slug in countries:
        fy = pick_focus_year(by_country[cc].keys(), today)
        crows = sorted(by_country[cc][fy], key=lambda r: r["date"])
        compare_data.append({
            "c": cc,
            "n": name,
            "s": slug,
            "y": fy,
            "h": [[r["date"], r["name"], r.get("localName") or r["name"]] for r in crows],
        })
    (out / "compare").mkdir(exist_ok=True)
    (out / "compare" / "index.html").write_text(
        page_compare_index(compare_items, site_url, verified, compare_data), encoding="utf-8")
    urls.append(("compare/", "0.7"))

    # ── static API (JSON) ──
    api_v1 = out / "api" / "v1"
    api_v1.mkdir(parents=True, exist_ok=True)
    api_countries = []
    for cc, name, cslug in countries:
        year_list = sorted(by_country[cc].keys())
        api_countries.append({
            "code": cc,
            "name": name,
            "slug": cslug,
            "years": year_list,
            "holidayCount": sum(len(by_country[cc][y]) for y in year_list),
        })
    (api_v1 / "countries.json").write_text(
        json.dumps({"generatedAt": verified, "countries": api_countries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for cc, name, cslug in countries:
        cc_dir = api_v1 / "holidays" / cc
        cc_dir.mkdir(parents=True, exist_ok=True)
        for year in sorted(by_country[cc]):
            payload_rows = []
            for row in sorted(by_country[cc][year], key=lambda r: r["date"]):
                payload_rows.append({
                    "date": row["date"],
                    "name": row["name"],
                    "localName": row.get("localName") or row["name"],
                    "types": row.get("types") or [],
                    "global": bool(row.get("global")),
                    "counties": row.get("counties") or [],
                })
            api_payload = {
                "country": cc,
                "name": name,
                "year": year,
                "holidays": payload_rows,
            }
            if cc == "CN":
                cn_data = cn_year_data(year)
                if cn_data:
                    api_payload["supplementary"] = {
                        "rest": cn_data.get("rest") or [],
                        "work": cn_data.get("work") or [],
                    }
            (cc_dir / f"{year}.json").write_text(
                json.dumps(api_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # ── widget / CDN headers / ads.txt ──
    (out / "widget.js").write_text(WIDGET_JS, encoding="utf-8")
    (out / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    if args.indexnow_key:
        (out / f"{args.indexnow_key}.txt").write_text(args.indexnow_key, encoding="utf-8")

    (out / '9c1f7a2b4d6e8f0a1b3c5d7e9f2a4b6c.txt').write_text('9c1f7a2b4d6e8f0a1b3c5d7e9f2a4b6c', encoding='utf-8')
    if OG_IMAGE:
        shutil.copyfile(ROOT / "assets" / "og-cover.png", out / "og-cover.png")
    (out / "_headers").write_text(
        "/api/v1/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=86400\n"
        "/assets/support/*\n  Cache-Control: public, max-age=604800\n"
        "/widget.js\n  Cache-Control: public, max-age=86400\n"
        "/search-index.json\n  Cache-Control: public, max-age=3600\n",
        encoding="utf-8",
    )
    support_dir = ROOT / "assets" / "support"
    if support_dir.exists():
        shutil.copytree(support_dir, out / "assets" / "support", dirs_exist_ok=True)
    if ADSENSE_CLIENT:
        (out / "ads.txt").write_text(
            f"google.com, {ADSENSE_CLIENT}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    else:
        (out / "ads.txt").write_text(
            "# Replace with your AdSense publisher id after approval, e.g.\n"
            "# google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0\n",
            encoding="utf-8",
        )

    # ── growth & monetisation pages ──
    (out / "premium").mkdir(exist_ok=True)
    (out / "premium" / "index.html").write_text(page_premium(site_url, verified), encoding="utf-8")
    urls.append(("premium/", "0.7"))
    (out / "api").mkdir(exist_ok=True)
    (out / "api" / "index.html").write_text(
        page_api_docs(site_url, verified, countries), encoding="utf-8")
    urls.append(("api/", "0.5"))
    (out / "embed").mkdir(exist_ok=True)
    demo_cc, demo_name = countries[0][0], countries[0][1]
    demo_year = sorted(by_country[demo_cc].keys())[-1]
    (out / "embed" / "index.html").write_text(
        page_embed_demo(site_url, verified, demo_cc, demo_name, demo_year), encoding="utf-8")
    urls.append(("embed/", "0.5"))
    (out / "support").mkdir(exist_ok=True)
    (out / "support" / "index.html").write_text(page_support(site_url, verified), encoding="utf-8")
    urls.append(("support/", "0.4"))

    # compliance pages
    privacy = (
        "<p>This site does not require registration and does not collect personal information. "
        "We use standard web server logs (IP address, user agent) for security and aggregate traffic "
        "analytics. Third-party advertising and affiliate partners may set cookies; you can control "
        "cookies in your browser settings.</p>"
        "<p>If you believe a holiday date is wrong, please contact us with the country, year and date.</p>"
    )
    about = (
        f"<p>{SITE_NAME} collects public holiday data from open sources and cross-checks it against "
        "official government announcements. The goal is simple: show not just which days are holidays, "
        "but how to turn them into the longest possible breaks.</p>"
        "<p>Data sources: Nager.Date (MIT), OpenHolidays API, and official government pages. "
        "Dates are provided for planning; always confirm before booking non-refundable travel.</p>"
    )
    (out / "privacy").mkdir(exist_ok=True)
    (out / "privacy" / "index.html").write_text(
        page_static("privacy", "Privacy Policy", privacy, site_url, verified), encoding="utf-8"
    )
    (out / "about").mkdir(exist_ok=True)
    (out / "about" / "index.html").write_text(
        page_static("about", f"About {SITE_NAME}", about, site_url, verified), encoding="utf-8"
    )
    urls.extend([("privacy/", "0.2"), ("about/", "0.2")])

    # ── site search index ──
    search_entries: list[dict] = []
    for cc, name, slug in countries:
        search_entries.append({"t": name, "s": "Public holidays 2025–2028",
                               "u": f"/{slug}/", "k": "country"})
        for y in sorted(by_country[cc].keys()):
            search_entries.append({"t": f"{name} {y}", "s": f"{y} public holidays",
                                   "u": f"/{slug}/{y}/", "k": "year"})
    for hslug, hname in top_items:
        search_entries.append({"t": hname, "s": "Holiday guide — dates by country",
                               "u": f"/holidays/{hslug}/", "k": "holiday"})
        search_entries.append({"t": f"When is {hname}", "s": "Live countdown",
                               "u": f"/days-until/{hslug}/", "k": "countdown"})
    for _slug, _name in (school_items if SCHOOL_DATA else []):
        search_entries.append({"t": f"{_name} school holidays", "s": "School break dates",
                               "u": f"/school-holidays/{_slug}/", "k": "school"})
    for _path, _title, _sub in [
        ("compare/", "Compare two countries", "Side-by-side holiday comparison"),
        ("holidays/", "Holiday guides", "Every major public holiday"),
        ("days-until/", "Countdowns", "Days until each holiday"),
        ("school-holidays/", "School holidays", "Global school break calendar"),
        ("api/", "Free JSON API", "Static holiday data, CORS, no key"),
        ("embed/", "Embed widget", "Put the calendar on your site"),
        ("premium/", "Premium", "Multi-country planner"),
        ("about/", "About", "Data sources and method"),
        ("support/", "Support", "Keep the project free"),
    ]:
        search_entries.append({"t": _title, "s": _sub, "u": f"/{_path}", "k": "page"})
    for _lang in HOME_I18N:
        search_entries.append({"t": f"HolidayKit {_lang.upper()}", "s": "Localized home page",
                               "u": f"/{_lang}/", "k": "page"})
    search_entries.append({"t": "Long weekends", "s": "Best breaks worldwide, ranked",
                           "u": "/long-weekends/", "k": "page"})
    for _y in sorted(lw_by_year):
        search_entries.append({"t": f"Long weekends {_y}", "s": "Worldwide long-weekend ranking",
                               "u": f"/long-weekends/{_y}/", "k": "year"})
    search_entries.append({"t": "Holidays by month", "s": "Worldwide calendar, month by month",
                           "u": "/calendar/", "k": "page"})
    for _y in CAL_YEARS:
        search_entries.append({"t": f"Public holidays {_y} by month", "s": "Worldwide calendar",
                               "u": f"/calendar/{_y}/", "k": "year"})
        for _m in range(1, 13):
            search_entries.append({"t": f"{MONTH_NAMES[_m - 1]} {_y} holidays",
                                   "s": "Which countries are off this month",
                                   "u": f"/calendar/{_y}/{_m}/", "k": "month"})
    (out / "search-index.json").write_text(
        json.dumps(search_entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # sitemap + robots
    # full URL list (manual submission / debugging)
    all_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority in urls:
        all_lines.append(
            f"<url><loc>{site_url}/{path}</loc><lastmod>{verified}</lastmod>"
            f"<priority>{priority}</priority></url>"
        )
    all_lines.append("</urlset>")
    (out / "sitemap-all.xml").write_text("\n".join(all_lines), encoding="utf-8")

    # chunked sitemap index: /sitemap.xml IS the index (better for Search Console)
    chunk_size = 500
    chunk_names = []
    for start in range(0, len(urls), chunk_size):
        chunk = urls[start:start + chunk_size]
        chunk_name = f"sitemap-{start // chunk_size + 1}.xml"
        chunk_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path, priority in chunk:
            chunk_lines.append(
                f"<url><loc>{site_url}/{path}</loc><lastmod>{verified}</lastmod>"
                f"<priority>{priority}</priority></url>"
            )
        chunk_lines.append("</urlset>")
        (out / chunk_name).write_text("\n".join(chunk_lines), encoding="utf-8")
        chunk_names.append(chunk_name)
    index_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for chunk_name in chunk_names:
        index_lines.append(
            f"<sitemap><loc>{site_url}/{chunk_name}</loc><lastmod>{verified}</lastmod></sitemap>"
        )
    index_lines.append("</sitemapindex>")
    index_text = "\n".join(index_lines)
    (out / "sitemap.xml").write_text(index_text, encoding="utf-8")
    (out / "sitemap_index.xml").write_text(index_text, encoding="utf-8")

    # minimal sitemap (diagnostics: isolate content issues from fetch/property issues)
    min_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, _priority in urls[:5]:
        min_lines.append(f"<url><loc>{site_url}/{path}</loc></url>")
    min_lines.append("</urlset>")
    (out / "sitemap-min.xml").write_text("\n".join(min_lines), encoding="utf-8")

    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: " + site_url + "/sitemap.xml\n",
        encoding="utf-8",
    )

    print(f"Built {len(urls)} pages for {len(countries)} countries -> {out}")
    print("Open dist/index.html to preview. Deploy the dist/ folder as-is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
