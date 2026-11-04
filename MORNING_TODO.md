# 早间待办（2026-11-05）

站点已上线：https://holidaykit.pages.dev（1,313 页 / 95 国 / 学校假期 33 国 / 对比 24 组）

## 1. Search Console 提交 sitemap（2 分钟）

GSC → 索引 → Sitemaps：

1. 删除之前那条「无法读取」的记录
2. 新建并提交：`https://holidaykit.pages.dev/sitemap.xml`（现在是 sitemapindex，含 3 个分片）
3. 若仍报错，依次尝试：
   - `https://holidaykit.pages.dev/sitemap-all.xml`（完整 1,313 条）
   - `https://holidaykit.pages.dev/sitemap-1.xml` / `-2` / `-3`
4. 仍失败就把 GSC 里那条记录的错误详情（文字/截图）发给 AI

**服务端已确认正常**：200、`application/xml`、XML 合法、1,313 条、robots 允许、无 Cloudflare 拦截。

## 2. GitHub Actions 权限（可选，2 分钟）

`gh auth status` 里必须有 `workflow`：

```powershell
gh auth refresh -s workflow
```

然后完成浏览器授权（输入终端给出的 8 位 code → Authorize），再运行 `gh auth status` 确认出现 `'workflow'`。
告诉 AI「好了」，它会：推送 workflow → 触发首次运行 → 验证自动部署。

> 注意：GitHub 的 443 端口本机间歇性被阻断；若 `git push` 失败，AI 会用 GitHub API 推送（已验证可行）。

## 3. 本机自动部署（已生效，无需操作）

- Windows 计划任务：**HolidayKit Auto Deploy**，每天 **09:00** 和 **21:00** 运行
- 内容：三源采集 → 组装 → 审计 → 构建 → Cloudflare Pages 部署 → IndexNow
- 错过时间会补跑（StartWhenAvailable），失败重试 3 次
- 手动运行：`powershell -File scripts/deploy.ps1`
- Cloudflare 凭据已写入用户环境变量 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`

## 4. 安全提醒

之前贴到聊天里的 Cloudflare token 建议在方便时 revoke，并换成新的：
- 先建新 token（Account · Cloudflare Pages · Edit）→ 更新用户环境变量 → 更新 GitHub Secret
- 再 revoke 旧的

## 5. 下一步内容计划（等指令）

- 节日倒计时扩到全部节日
- 学校假期覆盖更多国家（当前 33 国）
- 国家对比页扩到 60 组
- AdSense：等 GSC 有自然流量后申请，拿到 `pub-XXX` 后一条命令接入
