param(
  [string]$SiteUrl = "https://holidaykit.pages.dev",
  [string]$ProjectName = "holidaykit",
  [string]$AffiliateUrl = "",
  [string]$ContactEmail = "hello@example.com",
  [string]$AdsenseClient = "",
  [string]$GoogleVerification = "QfC8EpnSFGu7aWk17GyocmVaOBbTxTxy9lgJy3oYzfE",
  [string]$IndexNowKey = "9c1f7a2b4d6e8f0a1b3c5d7e9f2a4b6c",
  [switch]$SkipCollect
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SkipCollect) {
  Write-Host "==> 1/6 collect (Nager.Date)" -ForegroundColor Cyan
  python scripts/fetch_cache.py
  Write-Host "==> 2/6 collect (OpenHolidays)" -ForegroundColor Cyan
  python scripts/fetch_openholidays.py
  Write-Host "==> 3/6 collect (school holidays)" -ForegroundColor Cyan
  python scripts/fetch_school.py
  Write-Host "==> 4/6 collect (python-holidays fallback)" -ForegroundColor Cyan
  python scripts/fetch_lib.py
  Write-Host "==> 5/6 assemble + audit" -ForegroundColor Cyan
  python scripts/assemble.py
  python scripts/audit.py
} else {
  Write-Host "==> collect skipped" -ForegroundColor DarkGray
}

Write-Host "==> 6/6 build + deploy" -ForegroundColor Cyan
$buildArgs = @(
  "scripts/build_site.py",
  "--site-url", $SiteUrl,
  "--contact-email", $ContactEmail
)
if ($AffiliateUrl) { $buildArgs += @("--affiliate-url", $AffiliateUrl) }
if ($AdsenseClient) { $buildArgs += @("--adsense-client", $AdsenseClient) }
if ($GoogleVerification) { $buildArgs += @("--google-site-verification", $GoogleVerification) }
if ($IndexNowKey) { $buildArgs += @("--indexnow-key", $IndexNowKey) }
python @buildArgs

if (-not $env:CLOUDFLARE_API_TOKEN) {
  Write-Host "CLOUDFLARE_API_TOKEN is not set; cannot deploy." -ForegroundColor Yellow
  exit 1
}
if (-not $env:CLOUDFLARE_ACCOUNT_ID) {
  $env:CLOUDFLARE_ACCOUNT_ID = "b77a6d006715898e2720d24a332bd1f3"
}

$deployed = $false
for ($attempt = 1; $attempt -le 3; $attempt++) {
  Write-Host "==> deploy attempt $attempt" -ForegroundColor Cyan
  npx wrangler pages deploy dist --project-name $ProjectName --branch main
  if ($LASTEXITCODE -eq 0) { $deployed = $true; break }
  Start-Sleep -Seconds 5
}
if (-not $deployed) {
  Write-Host "deploy failed after 3 attempts" -ForegroundColor Red
  exit 1
}

if ($IndexNowKey) {
  python scripts/indexnow.py --key $IndexNowKey --site-url $SiteUrl
}

Write-Host "Done. Site: $SiteUrl" -ForegroundColor Green
