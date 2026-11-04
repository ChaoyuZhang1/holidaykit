# HolidayKit — 全球节假日 & 长周末（B2C 静态站）

从 `D:\zcy\zcy\time_cursor`（只读）抽出的 B2C 产品：**全球公共假期 → 长周末/桥假规划 → 日历订阅 → API/embed**。
纯静态、纯 Python 标准库、无后端数据库，一条命令构建，直接部署 Cloudflare Pages。

## 功能清单

| 模块 | 内容 |
|---|---|
| 数据 | 90 国/地区 × 2025–2028 公共假期（Nager.Date），官方源核对清单，快照 + diff 审计 |
| 页面 | 国家页、年份页、长周末/桥假页、假期指南页、倒计时页、ICS 订阅页、API 文档、embed 演示、Premium、隐私/关于 |
| 增长 | ICS 日历订阅、免费 JSON API（CORS）、一行 script 的 embed widget、sitemap、FAQ/Event 结构化数据 |
| 变现 | 页内广告位、旅行联盟 CTA、Premium 定价页、`ads.txt` 占位 |
| 质量 | `audit.py` 数据审计（schema/重复/覆盖率/diff，出错退出码 1）+ `selftest.py` 一键自检 |

## 目录

```
holiday-kit/
├─ scripts/collect.py       采集 → data/holidays.json + data/snapshots/
├─ scripts/audit.py         数据审计 + 与上一份快照 diff → data/audit-report.json
├─ scripts/build_site.py    生成静态站 → dist/
├─ scripts/selftest.py      一键自检（构建到临时目录并检查关键产物）
├─ scripts/deploy.ps1       采集 → 审计 → 构建 → 部署 Cloudflare Pages
├─ data/official_sources.json  官方日历核对清单（国家 → 政府站点）
├─ data/sample-holidays.json   样例数据（US/GB 2026，可离线预览）
├─ functions/ics-count.js   ICS 订阅点击统计（可选，需 Pages Functions）
├─ wrangler.toml            Cloudflare Pages 配置
├─ .github/workflows/deploy.yml  定时采集 + 自检 + 自动部署
└─ docs/B2C-PLAN.md         流量与变现方案
```

## 快速开始

```bash
# 0) 离线预览（用样例数据）
python scripts/build_site.py --data data/sample-holidays.json
#    打开 dist/index.html

# 1) 采集真实数据（约 2-3 分钟）
python scripts/collect.py

# 2) 审计数据（schema/重复/覆盖率/与上版 diff）
python scripts/audit.py

# 3) 构建
python scripts/build_site.py --site-url https://your-domain.com

# 4) 自检（可选但建议在部署前跑）
python scripts/selftest.py
```

## 数据与审计

- **主数据源**：Nager.Date（MIT，200+ 国家）。`collect.py` 默认采 90 国 × 2025–2028，失败会写入 `meta.failed`。
- **学校假期（可选）**：`python scripts/collect.py --with-school` 走 OpenHolidays，接口在某些网络下可能返回空。
- **官方核对清单**：`data/official_sources.json` 记录每个国家的政府日历页、最后核对日期、口径备注；国家页会展示「Official source」。`audit.py` 会对缺少条目的国家告警——**上线前至少人工核对主推的 10 个国家**。
- **快照与 diff**：每次采集写 `data/snapshots/holidays-YYYY-MM-DD.json`；`audit.py` 自动和上一份不同快照比较，报告新增/删除的假期，用于发现上游数据变动。
- **准确性是生命线**：节假日是活数据（临时改期、调休、补班），建议每周跑一次采集（仓库已带 GitHub Actions 定时任务），并保留人工抽查。

## 免费 API（静态 JSON）

构建时生成，无需后端：

```
GET /api/v1/countries.json                       # 国家列表 + 年份 + 假期数量
GET /api/v1/holidays/{CC}/{YYYY}.json            # 某国某年全部公共假期
```

`dist/_headers` 已给 `/api/*` 加上 `Access-Control-Allow-Origin: *` 和缓存头。文档页：`/api/`。

## Embed widget

任意网站粘一段：

```html
<div id="holidaykit-widget"></div>
<script src="https://your-domain.com/widget.js" data-country="US" data-year="2026" data-target="holidaykit-widget"></script>
```

`widget.js` 会拉 `/api/v1/holidays/US/2026.json` 并渲染列表；演示页 `/embed/`。

## 变现位（构建参数）

```bash
python scripts/build_site.py \
  --site-url https://your-domain.com \
  --affiliate-url "https://你的联盟链接" \
  --adsense-client pub-0000000000000000 \
  --contact-email hi@your-domain.com
```

- `--adsense-client`：生成 `ads.txt` 的正式行（批准后填）
- `--affiliate-url`：长周末页/国家页/假期页的「Compare flights & hotels」CTA 目标
- `--contact-email`：Premium 页 waitlist 的 mailto

## 部署到 Cloudflare Pages

### 方式 A：本地一条命令（最快，静态直传）

```powershell
# 首次：浏览器授权一次
npx wrangler login

# 创建项目（只需一次）
npx wrangler pages project create holidaykit --production-branch main

# 采集 + 审计 + 构建 + 部署
powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1 `
  -SiteUrl https://holidaykit.pages.dev `
  -ContactEmail hi@your-domain.com `
  -AffiliateUrl "https://你的联盟链接"
```

产物是纯静态，直传不包含 `functions/`（ICS 统计会静默跳过，不影响站点）。

### 方式 B：Git 集成 / GitHub Actions（推荐长期用）

1. 仓库推到 GitHub；
2. Cloudflare Dashboard → Workers & Pages → 创建 Pages → 连接 Git 仓库；
   构建命令：`python scripts/collect.py && python scripts/build_site.py --site-url $SITE_URL`
   输出目录：`dist`（或直接用仓库里的 `.github/workflows/deploy.yml`，在 GitHub 配置：
   - Secrets：`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`
   - Variables：`SITE_URL`、`CF_PAGES_PROJECT`、`CONTACT_EMAIL`、`AFFILIATE_URL`、`ADSENSE_CLIENT`）
3. 自定义域名：Pages → Custom domains。

### 上线后 checklist

- [ ] Search Console 提交 `sitemap.xml`
- [ ] Cloudflare Web Analytics 打开（免费）
- [ ] 30+ 页后再申请 AdSense/Ezoic
- [ ] 申请旅行联盟（Booking/Skyscanner/Agoda），把链接填进 `--affiliate-url`
- [ ] 人工核对主推国家的假期（对照 `data/official_sources.json`）

## 数据来源与许可

| 来源 | 用途 | 许可 |
|---|---|---|
| [Nager.Date](https://date.nager.at) | 公共假期 | MIT，保留署名 |
| [OpenHolidays API](https://openholidaysapi.org) | 学校假期（可选） | 以官网条款为准 |
| 各国政府站点 | 人工核对 | 引用事实，不复制正文 |

**不要抓取 timeanddate / officeholidays 等版权站点**；仅参考页面结构。
