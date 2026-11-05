# time_cursor 可拆分功能分析（独立站点机会）

> 基于对 `D:\zcy\zcy\time_cursor`（只读）代码的梳理：Next.js 前端 + Flask 后端 + 微信小程序。
> 目标：找出能**单独抽出来做成一个站、靠 SEO/广告/订阅赚钱**的功能，并评估优先级。

## 现有能力盘点

| 模块 | 代码位置（参考） | 说明 |
|---|---|---|
| 中国法定节假日/调休 | `collector/sources_chinese_days.py`、`application/workday_eval.py` | 调休、补班、法定/个人口径 |
| 全球公共假期 | `collector/sources_openholidays.py`、`sources_nager.py` | 35+ 国家 |
| 交易所日历 | `collector/sources_*`、`pandas_market_calendars` | A 股/美股等交易日 |
| 财经日历 | AKShare / 东方财富 / 宏观 | 财报、宏观数据发布 |
| 体育/娱乐赛事 | F1、MotoGP、NHL、FIVB、AniList 等 | 赛程聚合 |
| 农历黄历 | `collector/almanac_service.py`、`lunar-python` | 宜忌/节气 |
| 城市限行 | `application/city_life_service.py` | 尾号限行 |
| 课程表 | `application/course_schedule_service.py` | Excel/ICS 导入、单双周 |
| 个人日程/倒数日 | `event_countdowns`、`countdown_reminders` | 倒数日 + 提醒 |
| 推送 | `pywebpush`、`wxpusher_products.py` | Web Push / 微信 |
| AI 智能添加 | `application/ai_service.py` | 自然语言建日程 |
| ICS 导出/订阅 | `application/ics_export.py` | 用户级订阅源 |

## 高潜力独立站点（按「需求 × 变现 × 开发成本」排序）

### 1. 商务工作日计算器（Business Days Calculator）★★★★★
- **需求**：全球搜索量巨大（"business days calculator"、"working days in 2026"、"add business days"），跨境/外贸/HR/财务/物流高频；中国侧还有「工作日计算/交期测算 + 调休」刚需。
- **可复用**：节假日/调休数据、workday_eval 口径。
- **变现**：展示广告（工具页 RPM 高）+ 后续 API 订阅（跨境 SaaS/物流）。
- **成本**：低（纯前端计算 + 数据 JSON）。
- **结论**：**本次已实现**（WorkdayKit，见 `workday-kit/`）。

### 2. 交易日历 / 交易所休市表（Trading Calendar）★★★★☆
- **需求**：「NYSE holidays 2026」「A股休市安排」搜索稳定；量化/回测/跨境支付/券商需要 API。
- **可复用**：`pandas_market_calendars`、交易所日历采集。
- **变现**：API 付费（B2B，客单高）、广告（B2C）。
- **成本**：低-中（数据 + 静态页 + API）。
- **注意**：需要保证准确性和更新（交易所临时休市）。

### 3. 中国调休 / 放假安排查询 ★★★★☆
- **需求**：每年 11 月国务院公布次年安排时流量爆发；「调休」「补班」是强搜索。
- **可复用**：chinese-days + chinese_calendar。
- **变现**：广告（季节性强）、企业日历订阅。
- **成本**：低。
- **注意**：季节性强、竞争激烈（万年历类）。

### 4. 农历/黄历吉日（Almanac）★★★☆☆
- **需求**：「黄历」「吉日」「宜忌」搜索量大，C 端用户广。
- **可复用**：`lunar-python`、almanac_service。
- **变现**：广告 + 会员（每日运势/择日）。
- **成本**：中（内容/文案量大、需本地化审美）。
- **注意**：国内竞争极强，且内容合规要谨慎。

### 5. 课程表 / 课表工具 ★★★☆☆
- **需求**：「课程表」「大学课表」学生人群，开学季爆发。
- **可复用**：course_schedule_service（Excel/ICS 导入）。
- **变现**：广告 + 小程序流量。
- **成本**：中（交互复杂，需移动端体验）。
- **注意**：微信小程序生态里竞品多。

### 6. 城市限行查询 ★★☆☆☆
- **需求**：有车一族刚需，但地域碎片化。
- **成本**：中（需要各城市数据源/维护）。
- **变现**：广告弱。
- **结论**：不建议单独做站，适合作为大站的子功能。

### 7. 倒数日/纪念日 ★★☆☆☆
- **需求**：C 端红海，App 竞争激烈。
- **变现**：弱。
- **结论**：不适合独立站点，适合做留存组件。

## 建议路线

1. **先做 #1 WorkdayKit**（已开发）：SEO 长尾大、开发快、可复用现有数据，先跑量；
2. 跑通后加 **#2 Trading Calendar API**：同一个技术栈，面向 B 端，客单价更高；
3. **#3 调休查询** 作为季节性流量入口，与 WorkdayKit 共用数据；
4. #4/#5 等有团队/流量后再考虑。

## 本次已交付

- `workday-kit/`：独立 Business Days Calculator 站点
  - 首页计算器（日期差 / 加工作日两种模式，支持 95 国与调休）
  - 国家页 × 年份页（每月工作日数、假期清单）
  - `/api/v1/business/{CC}/{year}.json` 静态 API
- 部署：Cloudflare Pages 新项目 `workdaykit`
