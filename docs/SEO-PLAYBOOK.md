# SEO playbook — HolidayKit / WorkdayKit / ExchangeKit

> 站点：https://holidaykit.pages.dev · https://workdaykit.pages.dev · https://exchangekit.pages.dev
> 结构：纯静态（Python 构建 → Cloudflare Pages Direct Upload），GitHub 仓库 `ChaoyuZhang1/holidaykit`、`workdaykit`、`exchangekit`。

## 0. 当前状态（2026-11-08）

| 项目 | HolidayKit | WorkdayKit | ExchangeKit |
|---|---|---|---|
| 页面数 | 1,850 | 486 | 171 |
| sitemap 分片 | 4 | 1 | 1 |
| lastmod | ✅ | ✅ | ✅ |
| JSON-LD | WebSite + SearchAction + FAQPage（国家页）+ BreadcrumbList + FAQPage（月度/长周末/学校） | WebSite + SearchAction + FAQPage（国家页）+ BreadcrumbList | WebSite + SearchAction + FAQPage（年份页）+ BreadcrumbList |
| hreflang | 8 语言 × 首页 | 8 语言 × 首页 | 8 语言 × 首页 |
| OG 图 | /og-cover.png（1200×630） | 同 | 同 |
| 站内搜索 | ✅ ⌘K，`/search-index.json` | ✅ | ✅ |
| 静态对比页 | 496 对（`/compare/{a}-vs-{b}-holidays/`） | — | — |
| 共享 CSS | `/assets/site.css?v=hash`（immutable 1y） | 同 | 同 |
| 内链 | 全部目录 URL（无 `/index.html`） | 同 | 同 |
| 验证标签 | google + bing（exchange） | google | google + bing |

## 1. 一次性提交清单（需要账号操作，逐站做）

### Google Search Console
1. 每站各建一个 **URL-prefix** 资源：`https://<site>.pages.dev/`。
2. 验证方式选「HTML 标记」——三站 head 已内置同一 token（`googlesitev…`），提交后点验证即可。
3. 「站点地图」提交 `https://<site>.pages.dev/sitemap.xml`（HolidayKit 是 sitemapindex，会自动展开分片）。
4. 一周后看「页面索引」报告：**已编入索引 / 已发现但未编入索引** 的分布，再决定是否需要加内容。

### Bing Webmaster Tools
1. 用 Google Search Console 导入（最快），或手动加站点并验证。
2. ExchangeKit 已有 `<meta name="msvalidate.01">`；另两站如果也要提交，需要各自生成 Bing 验证码。
3. 提交 sitemap。
4. **IndexNow**：三站 key 文件 `https://<site>.pages.dev/9c1f7a2b4d6e8f0a1b3c5d7e9f2a4b6c.txt`。
   - HolidayKit / WorkdayKit 已验证可提交（2026-11-08 全量 3,705 + 486 URL 返回 200）；
   - ExchangeKit 仍返回 `403 UserForbiddedToAccessSite`，需先在 Bing WMT 完成该域名验证，再重跑提交。

### 其他引擎（按语言）
- 中文：百度站长（需备案域名，pages.dev 无法提交 → 用自定义域名后再做）
- 日文：Google 已覆盖，可加 Yahoo Japan（YST）
- 俄语：Yandex Webmaster
- 韩语：Naver Search Advisor

## 2. 技术项（已完成，作为回归检查）

- ✅ 内链统一目录 URL（`clean_links()`），canonical 与内链一致，没有 `/x/index.html` 形式的重复 URL。
- ✅ 结构化数据：WebSite + SearchAction（站内搜索）、BreadcrumbList（所有有面包屑的页）、FAQPage（国家/年份/月度/长周末/学校）。
- ✅ OG/Twitter 卡片 + 1200×630 封面图。
- ✅ 共享 CSS 抽到 `/assets/site.css?v=<md5>`，`Cache-Control: immutable, max-age=31536000`。
- ✅ 站内搜索索引 `search-index.json`（1h 缓存）。
- ✅ 自定义 404（`/404`）与 sitemap/robots。
- 🔲 剩余：内联 JS（CAL_JS / SEARCH_JS / MAP_JS 等）也可抽成 `/assets/app.js`，预计再省 20–40KB/页。
- 🔲 剩余：图片只有 OG 封面，无 LCP 图片，无需 lazy-load 改造。

## 3. 外链渠道（按投入产出排序）

| 渠道 | 做法 | 预期 |
|---|---|---|
| **免费数据/API 目录** | 提交到 public-apis、awesome-public-datasets、RapidAPI、APIList 等（先恢复 `SHOW_API`，或提交 embed 页） | 高质量编辑外链，DR 高 |
| **Reddit** | r/travel、r/digitalnomad、r/Finland 等真实回答「2027 年怎么请假最划算」，贴长周末页面；不要纯广告 | 流量 + 自然引用 |
| **Hacker News** | Show HN: "I built a free public-holiday calendar API with long-weekend planner" | 一次性爆发，需当天值守 |
| **Product Hunt** | 三站合并为一个 maker 页 | 中等 |
| **Dev.to / Hashnode / Medium** | 写「How I built a 95-country holiday dataset」，正文链回站点与 API | 编辑外链 |
| **GitHub awesome lists** | PR 到 awesome-travel、awesome-datasets、awesome-calendar | 稳定 dofollow |
| **问答** | Quora/知乎「2027 年放假安排」类问题下给长周末排行 | 长尾流量 |
| **中文站** | 知乎专栏 + 小红书图文（分享卡片直接可用） | 中文长尾 |
| **Embed 组件** | 给 HR/学校/旅行博客提供 `<iframe>` 小挂件，挂件带链接 | 持续自然外链 |
| **邮件 outreach** | 找「public holidays 2027」类列表页的站长，提供更新更准的数据 | 中等，转化低 |

注意：pages.dev 是共享域，外链 PR 值会被部分稀释；**自定义域名**（如 holidaykit.com）对 SEO 与信任度提升明显，是下一步最高杠杆的动作。

## 4. 内容节奏（保持抓取频次）

- **每年 9–10 月**：更新下一年假期（脚本已自动从 Nager.Date / OpenHolidays 拉取），提交 IndexNow。
- **每月**：`/calendar/{year}/{month}/` 自动更新最忙日期；可配一条社交帖。
- **每季度**：新增 1 个专题（如「全球春节放假国家」「斋月对工作日的影响」「欧洲桥假 TOP 20」）。
- **持续**：长周末排行每年重算，天然产生「2028 最新」类新 URL。

## 5. 监测指标

- GSC：已编入索引页数、平均排名、CTR、Core Web Vitals
- Bing WMT：索引数、抓取错误
- Cloudflare Analytics：页面浏览、来源
- 每月记录一次三站索引数与自然流量，判断是否需要加内容或修技术项

## 6. 关于「多语言内容页（E）」的建议

原计划生成 `/{lang}/{country}/{year}/` 全量多语言页（6 语言 × 95 国 × 4 年 ≈ 2,280 页/站）。**暂不建议直接做**：

- 正文（假期名、说明）目前只有英文 + 部分 `localName`，批量生成会产出大量「英文正文 + 本地语言外壳」的近似重复页，Google 容易判定为 thin/duplicate，反而拖累整站质量分。
- 更稳的做法（建议分两步）：
  1. 先做**语言匹配的本地化国家页**：`/zh/cn/2027/`、`/ja/jp/2027/`、`/ko/kr/2027/`、`/es/es/2027/`、`/fr/fr/2027/`、`/de/de/2027/`（6 语言 × 4 年 + 6 个索引页 ≈ 30 页），标题/标签/说明用该语言，假期名优先用 `localName`；同时给这批页加 hreflang 簇。
  2. 观察 4–6 周索引与排名，再决定是否扩到更多国家。

需要执行时告诉我，我可以按上面的范围先生成 30 页试点并接入 sitemap / 搜索索引 / hreflang。
