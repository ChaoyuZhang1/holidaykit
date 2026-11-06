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
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

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
}
@media(max-width:600px){
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

# UI i18n (chrome strings only; holiday names stay in their original/local form)
I18N_JS = r"""
(function(){
  var D = {
    en: {
      'nav.countries':'Countries','nav.guides':'Holiday guides','nav.countdowns':'Countdowns',
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
      'nav.countries':'国家','nav.guides':'节日指南','nav.countdowns':'倒计时',
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
      'nav.countries':'国一覧','nav.guides':'祝日ガイド','nav.countdowns':'カウントダウン',
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
      'nav.countries':'국가','nav.guides':'공휴일 가이드','nav.countdowns':'카운트다운',
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
      'nav.countries':'Países','nav.guides':'Guías de festivos','nav.countdowns':'Cuentas atrás',
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
      'nav.countries':'Pays','nav.guides':'Guides des fêtes','nav.countdowns':'Comptes à rebours',
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
      'nav.countries':'Länder','nav.guides':'Feiertags-Guides','nav.countdowns':'Countdowns',
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
        var txt = el.textContent.trim().replace(/,/g, '');
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


def flag_emoji(cc: str) -> str:
    code = str(cc or "").upper()
    if len(code) != 2 or not code.isalpha():
        return "🌍"
    return chr(0x1F1E6 + ord(code[0]) - 65) + chr(0x1F1E6 + ord(code[1]) - 65)


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
    """广告位：未配置 AdSense 时显示占位；配置后输出自适应广告单元。"""
    if not ADSENSE_CLIENT:
        return '<section class="ad">Ad slot — configure --adsense-client</section>'
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
        "<nav>"
        f'<a href="{base}index.html#countries" data-i18n="nav.countries">Countries</a>'
        f'<a href="{base}holidays/index.html" data-i18n="nav.guides">Holiday guides</a>'
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
        '<a href="https://date.nager.at" rel="nofollow noopener" target="_blank">Nager.Date</a></div>'
        "</div>"
        f'<div class="foot-note" data-i18n="foot.note">Data from open sources, cross-checked against official government '
        "announcements. Dates are for planning — always confirm before booking non-refundable travel.</div>"
        "</div></footer>"
    )


def render_page(*, title: str, description: str, canonical: str, base: str,
                body: str, verified: str, json_ld: str = "",
                cta_href: str = "", cta_label: str = "Browse countries",
                extra_js: str = "", lang_code: str = "en", alternates: str = "") -> str:
    head = (
        f'<!doctype html><html lang="{esc(lang_code)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title>"
        f'<meta name="description" content="{esc(description)}">'
        f'<link rel="canonical" href="{esc(canonical)}">'
        '<meta name="robots" content="index,follow">'
        f'<meta property="og:site_name" content="{SITE_NAME}">'
        f'<meta property="og:title" content="{esc(title)}">'
        f'<meta property="og:description" content="{esc(description)}">'
        '<meta property="og:type" content="website">'
        '<meta name="theme-color" content="#fbfaf7">'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        f'<link rel="sitemap" type="application/xml" href="{base}sitemap.xml">'
        + alternates
        + f"<style>{CSS}{CSS2}</style>"
    )
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
    return (
        head + "</head><body>"
        + nav_html(base)
        + '<main class="wrap">' + body + "</main>"
        + footer_html(base, verified)
        + mobile_cta
        + f"<script>{JS}</script>"
        + (f'<script>window.HK_FORCE_LANG="{esc(lang_code)}";</script>' if lang_code != "en" else "")
        + f"<script>{I18N_JS}</script>"
        + f"<script>{CAL_JS}</script>"
        + f"<script>{MOTION_JS}</script>"
        + (f"<script>{extra_js}</script>" if extra_js else "")
        + "</body></html>"
    )


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
        cards.append(
            f'<a class="card" href="{slug}/index.html">'
            f'<div class="flag">{flag_emoji(cc)}</div>'
            f"<h3>{esc(name)}</h3>"
            f'<p>{count} public holidays · {", ".join(str(y) for y in years[:3])}</p>'
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
        "</div></div>" + feature_card + "</div></section>"
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
        extra_js=HOME_CAL_JS,
        alternates=hreflang_links(site_url),
    )


def page_country(cc: str, name: str, slug: str, by_country, site_url: str, verified: str) -> str:
    today = date.today()
    years = sorted(int(y) for y in by_country[cc].keys())
    latest = pick_focus_year(years, today)
    ordered = year_order(years, today)
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
    )


def page_year(cc: str, name: str, slug: str, year: int, rows: list[dict], runs: list[dict],
              site_url: str, verified: str) -> str:
    cn = cn_year_data(year) if cc == "CN" else None
    body = (
        '<section class="hero">'
        f'<p class="badge">{esc(name)} · {year}</p>'
        f"<h1>{esc(name)} public holidays {year}</h1>"
        f'<p class="lede">Official public holidays in {esc(name)} for {year}, with weekdays, '
        "countdowns and the long weekends you can build around them.</p>"
        "</section>"
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
        + f'<p><a href="../index.html">← {esc(name)} overview</a></p>'
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


# ── school holidays & country comparison ───────────────────────────────────

def webcal_url(https_url: str) -> str:
    return https_url.replace("https://", "webcal://", 1)


def google_cal_url(ics_url: str) -> str:
    return "https://calendar.google.com/calendar/r?cid=" + quote(webcal_url(ics_url), safe="")


def outlook_cal_url(ics_url: str) -> str:
    return "https://outlook.live.com/calendar/0/addfromweb?url=" + quote(ics_url, safe="")


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
        '<a class="btn ghost" href="https://calendar.google.com/calendar/r/settings/addbyurl" '
        'target="_blank" rel="noopener">Android — Add by URL</a>'
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
        "<li>Browser → <a href=\"https://calendar.google.com/calendar/r/settings/addbyurl\" target=\"_blank\" "
        'rel="noopener">Google Calendar → Settings → Add calendar → From URL</a> → paste the .ics URL.</li>'
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
        '<p class="lede">Official school break dates by region, with calendar subscriptions. '
        "Coverage is expanding as sources publish future calendars.</p></section>"
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
    body = (
        '<section class="hero"><p class="eyebrow">Country comparison</p>'
        f"<h1>{esc(a_name)} vs {esc(b_name)} holidays {year}</h1>"
        f'<p class="lede">Side-by-side public holidays: {len(rows_a)} in {esc(a_name)}, '
        f"{len(rows_b)} in {esc(b_name)}, {len(common)} on the same date.</p>"
        '<div class="chips">'
        f'<span class="chip">{esc(a_name)}: {len(rows_a)} holidays</span>'
        f'<span class="chip">{esc(b_name)}: {len(rows_b)} holidays</span>'
        f'<span class="chip">Same date: {len(common)}</span>'
        "</div></section>"
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


def page_compare_index(items: list[tuple[str, str, str, int]], site_url: str, verified: str) -> str:
    cards = "".join(
        f'<a class="card" href="{pair_slug}/index.html"><div class="flag">⚖️</div>'
        f"<h3>{esc(a_name)} vs {esc(b_name)}</h3><p>Holidays side by side · {year}</p></a>"
        for pair_slug, a_name, b_name, year in items
    )
    body = (
        '<section class="hero"><p class="eyebrow">Compare</p>'
        "<h1>Compare public holidays between countries</h1>"
        '<p class="lede">Side-by-side holiday calendars for expats, remote workers and travel planning.</p>'
        "</section>"
        '<div class="grid">' + cards + "</div>"
        '<p><a href="../index.html">← All countries</a></p>'
    )
    return render_page(
        title=f"Compare Public Holidays Between Countries | {SITE_NAME}",
        description="Compare public holidays side by side for major country pairs.",
        canonical=f"{site_url}/compare/",
        base="../",
        body=body,
        verified=verified,
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
        box = (
            f'<div class="countdown" data-date="{esc(nxt.isoformat())}">'
            '<span data-countdown></span></div>'
            if nxt else ""
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
        f"<h1>{esc(h1)}</h1>"
        f'<p class="lede">{esc(lede)}</p>' + box + "</section>"
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


def holiday_index_page(kind: str, items: list[tuple[str, str]], site_url: str, verified: str) -> str:
    path = "holidays" if kind == "holiday" else "days-until"
    heading = "Holiday guides" if kind == "holiday" else "Holiday countdowns"
    cards = "".join(
        f'<a class="card" href="{slug}/index.html"><h3>{esc(name)}</h3>'
        "<p>Dates by country · calendar links</p></a>"
        for slug, name in items
    )
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
        '<p class="lede">Every country and year as static JSON. CORS enabled, no API key, no rate limit — '
        "please cache responses and attribute HolidayKit.</p></section>"
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
        "<li>Commercial use under the free tier requires a link back to HolidayKit.</li>"
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

    (out / "holidays").mkdir(exist_ok=True)
    (out / "holidays" / "index.html").write_text(
        holiday_index_page("holiday", top_items, site_url, verified), encoding="utf-8")
    urls.append(("holidays/", "0.7"))
    (out / "days-until").mkdir(exist_ok=True)
    (out / "days-until" / "index.html").write_text(
        holiday_index_page("countdown", top_items, site_url, verified), encoding="utf-8")
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
    (out / "compare").mkdir(exist_ok=True)
    (out / "compare" / "index.html").write_text(
        page_compare_index(compare_items, site_url, verified), encoding="utf-8")
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
    if OG_IMAGE:
        shutil.copyfile(ROOT / "assets" / "og-cover.png", out / "og-cover.png")
    (out / "_headers").write_text(
        "/api/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=3600\n"
        "/widget.js\n  Cache-Control: public, max-age=86400\n",
        encoding="utf-8",
    )
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
