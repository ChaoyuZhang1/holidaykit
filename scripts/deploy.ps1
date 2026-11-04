<#
.SYNOPSIS
  HolidayKit 一键构建并部署到 Cloudflare Pages。
.DESCRIPTION
  依次执行：采集 → 审计 → 构建静态站 → wrangler 上传。
  首次使用需要先在本机执行一次 `npx wrangler login`（浏览器授权）。
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/deploy.ps1 `
    -SiteUrl https://holidaykit.pages.dev `
    -ContactEmail hi@your-domain.com
#>
param(
  [string]$SiteUrl = "https://holidaykit.pages.dev",
  [string]$ProjectName = "holidaykit",
  [string]$AffiliateUrl = "",
  [string]$ContactEmail = "hello@example.com",
  [string]$AdsenseClient = "",
  [switch]$SkipCollect
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SkipCollect) {
  Write-Host "==> 1/4 collect holidays" -ForegroundColor Cyan
  python scripts/collect.py
} else {
  Write-Host "==> 1/4 collect skipped" -ForegroundColor DarkGray
}

Write-Host "==> 2/4 audit data" -ForegroundColor Cyan
python scripts/audit.py

Write-Host "==> 3/4 build static site" -ForegroundColor Cyan
python scripts/build_site.py `
  --site-url $SiteUrl `
  --affiliate-url $AffiliateUrl `
  --contact-email $ContactEmail `
  --adsense-client $AdsenseClient

Write-Host "==> 4/4 deploy to Cloudflare Pages" -ForegroundColor Cyan
npx wrangler pages deploy dist --project-name $ProjectName --branch main

Write-Host "Done. Site: $SiteUrl" -ForegroundColor Green
