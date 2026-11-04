# HolidayKit · B2C 流量方案

> 目标：用「全球假期 + 长周末规划 + 日历订阅」做一个月内上线、可被搜索抓取的 B2C 静态站，
> 第一阶段靠展示广告 + 旅行联盟验证需求，第二阶段上订阅和 API。

## 1. 定位

**一句话**：Plan your year around long weekends.

**目标人群**（按付费/传播意愿排序）：
1. **跨境工作者 / 外派**：需要"本国 + 所在国"两份假期，最愿意为提醒和对比付费；
2. **远程工作者 / 自由职业**：跨时区客户的假期、自己的 PTO 规划；
3. **旅行者**：目的地长周末 + 机票酒店（联盟价值最高）；
4. **家长 / 学生**：学校假期（第二阶段数据）；
5. **HR / 行政**（偏 B 端）：多国假期表，后续转 API/订阅。

## 2. 差异化（决定了能不能活）

| 竞品普遍缺的 | HolidayKit 的做法 |
|---|---|
| 只列日期，不告诉你"请几天能连休几天" | **长周末/桥假规划器**：给定国家+年假天数，列出每个假期可延伸的连休方案 |
| 多国对比弱 | 国家页 + 后续"国家对比页"（US vs UK vs DE） |
| 亚洲调休数据空白 | 第二阶段接入中国调休、日本振替休日、韩国替代公休 |
| 只给网页，不进日历 | **一键 ICS 订阅**进 Google/Apple/Outlook |
| 无学校假期 | 第二阶段接 OpenHolidays 学校假期（家长人群，联盟强） |

## 3. 页面矩阵（程序化 SEO）

| 页面 | URL 规范 | Title 模板 | 搜索意图 |
|---|---|---|---|
| 国家页 | `/{country}-holidays/` | `{Country} Public Holidays 2026 & 2027 — Dates & Long Weekends` | 主词 |
| 年份页 | `/{country}-holidays/{year}/` | `{Country} Public Holidays {year} (Official Dates)` | 年份词 |
| 长周末页 | `/{country}-holidays/{year}/long-weekends/` | `{Country} Long Weekends {year}: Best Days to Take Off` | 决策词（差异化） |
| 节日页 | `/holidays/{holiday}/` | `{Holiday} {year}: Date, History, Long Weekend` | 节日词（量大） |
| 倒计时页 | `/days-until/{holiday}/` | `Days Until {Holiday} {year}` | 长尾/复访 |
| 对比页 | `/compare/{a}-vs-{b}-holidays/` | `{A} vs {B} Holidays {year}` | 跨境人群 |
| 学校假期页 | `/school-holidays/{country}/` | `{Country} School Holidays {year}` | 家长词 |
| 订阅页 | `/{country}-holidays/calendar/` | `Add {Country} Holidays to Your Calendar` | 转化页 |

**URL/内容规则**
- 每页唯一 `<title>` + meta description，canonical 带站点域名；
- 内链：年份页 ↔ 国家页 ↔ 长周末页 ↔ ICS 页 ↔ 相邻国家；
- 每页底部固定数据来源与 `Last verified` 日期；
- 结构化数据：国家页 FAQPage + 节日页 Event（后续）。

## 4. 首批关键词（示例 40 个，按意图分组）

**国家词**
`us public holidays 2026`、`uk bank holidays 2026`、`germany public holidays 2026`、`france jours fériés 2026`、`japan public holidays 2026`、`korea holidays 2026`、`canada statutory holidays 2026`、`australia public holidays 2026`

**年份/时间词**
`public holidays 2027`、`next public holiday`、`holidays this month`、`long weekend 2026`

**决策词（核心）**
`us long weekends 2026`、`best days to take off 2026`、`bridge days 2026`、`how to maximize annual leave 2026`、`2026 holidays calendar printable`

**节日/倒计时词**
`when is easter 2026`、`days until christmas 2026`、`thanksgiving 2026 date`、`when is thanksgiving 2026`、`chinese new year 2026 date`

**跨境词**
`us vs uk holidays`、`working in germany holidays`、`expat holiday calendar`、`holidays in japan for foreigners`

选词原则：先做 KD < 15 的长尾（长周末、桥假、倒计时、某国某节日），别碰 `public holidays` 这类头部词。
工具：Ahrefs / Semrush / Google Keyword Planner / Google Trends；上线后用 Search Console 的真实曝光反推。

## 5. 内容与数据质量

- **双源核对**：Nager.Date 打底 + 各国政府站核对；OpenHolidays 补学校假期；
- **纠错入口**：页面底部"数据有误？告诉我们"（表单可先用 mailto）；
- **更新机制**：每年 10-12 月各国公布次年安排后 24h 内重建；GitHub Actions 每周跑一次 `collect.py` + `build_site.py` 并比对 diff，有变化就发布；
- **准确性是生命线**：一个错误日期就能毁掉口碑，宁可少覆盖国家，不可错日期；
- **AI 摘要友好**：首屏用结构化列表（日期/名称/是否长周末），FAQ 用问答对。

## 6. 变现（按上线顺序）

| 方式 | 上线时机 | 预期 |
|---|---|---|
| **AdSense → Ezoic** | 有 30+ 页即可申请 | 美/英/德流量 RPM 约 $3–8；假期页停留长，属于高 RPM 品类 |
| **旅行联盟**（Booking / Skyscanner / Agoda / GetYourGuide） | 长周末页、节日页 | AOV 高、CPS 3–5%；"book the long weekend" CTA |
| **Premium 订阅** | 第 2 个月 | $2.99/月 或 $19/年：多国对比、长周末提醒、PTO 规划导出 PDF、ICS 高级订阅 |
| **Email 列表** | 与上线同步 | "Long weekend alerts"，邮件 → 联盟转化 |
| **免费 API** | 第 2 个月 | 开发者外链 + 后续付费档 |
| **B2B / lead-gen** | 第 3 个月 | 多国假期表卖给 HR/PEO/跨境 SaaS |

初期**不做付费投放**（工具站 ROI 极低）。

## 7. 增长路径（按 ROI）

1. **ICS 订阅**：每页主 CTA；用户订阅后每月至少回访一次日历；
2. **免费 embed widget**：博客/HR 站嵌入"某国假期日历"，换自然外链（WordCounter 的增长飞轮）；
3. **免费 API + GitHub 开源采集器**：开发者社区（HN / Reddit / X）传播；
4. **社区**：r/expats、r/digitalnomad、r/travel、各国 Facebook 群组；发"工具"贴要克制，先做内容再带链接；
5. **Pinterest**：长周末海报（视觉化，旅行人群活跃）；
6. **季节性节点**：圣诞/新年倒计时、暑假、各国"下一年假期官宣"；
7. **少量人工外链**：维基百科相关词条引用、大学/HR 博客资源页。

## 8. 技术方案

- **静态站**：本仓库 `build_site.py` 生成纯 HTML，无 JS 框架；
- **托管**：Cloudflare Pages 免费额度（全球 CDN + 自动 SSL）；Vercel 备选；
- **数据**：`data/holidays.json`（采集器输出，可入库版本化）；
- **自动化**：GitHub Actions 定时采集 → diff → 构建 → 部署；
- **后续扩展**：倒计时/对比页仍可静态生成；付费/API 再上 Workers + KV/D1。

## 9. 4 周排期

| 周 | 产出 | 验收 |
|---|---|---|
| W1 | 20–30 国数据（2026/2027）+ 国家页 + 年份页 | 本地 `dist/` 可点通，数据抽查 3 国 |
| W2 | 长周末页 + ICS 订阅 + sitemap/robots + 隐私/关于页 | Google Calendar 能成功订阅 |
| W3 | 上线 + Search Console + sitemap 提交 + 首批 2–3 个长尾页 | GSC 有收录、有曝光 |
| W4 | 数据复盘 + 节日页/倒计时页 + 联盟申请 | 自然点击 > 0，订阅数 > 10 |

## 10. KPI（第一月）

- 收录页数（GSC）
- 自然曝光 / 点击 / CTR / 平均排名
- ICS 订阅数（Cloudflare 日志统计 `calendar-*.ics` 下载）
- Email 订阅数
- 联盟点击 / 广告 RPM
- 数据错误报告数（应为 0）

## 11. 风险与对策

| 风险 | 对策 |
|---|---|
| AI Overviews 截流查询类流量 | 主打"决策/工具"页（长周末规划、ICS），少依赖纯日期页 |
| 数据错误 | 双源 + 人工抽查 + 纠错入口 + 变更 diff 审核 |
| 季节性波动（12 月高、2 月低） | 用倒计时页、学校假期页、多国页撑平 |
| AdSense 审核不过 | 先上线 30+ 页 + 隐私/关于页 + 原创说明，再申请 |
| 数据许可 | 保留来源署名，不抓版权站 |
| 一个人精力有限 | 先做 10 国精耕，验证后再扩；别一上来 200 国 |

## 12. 与 time_cursor 的关系

- `time_cursor` **只读复用**：采集器思路、`workday_eval` 的法定/调休口径、ICS 生成逻辑、i18n 词表；
- HolidayKit 独立仓库独立部署，不反向依赖主站；
- 中国调休/日本振替/韩国替代公休作为第二批数据接入，是主站最有价值的差异化资产。
