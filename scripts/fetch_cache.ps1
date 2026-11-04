param(
  [string]$CacheDir = "",
  [string]$Years = "2025,2026,2027,2028"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($CacheDir)) { $CacheDir = Join-Path $Root "data\cache" }
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

$countries = @(
  "US","CA","MX","GB","IE","AU","NZ",
  "DE","FR","ES","IT","NL","BE","AT","CH","PT","LU",
  "SE","NO","DK","FI","IS",
  "PL","CZ","SK","HU","RO","BG","GR","HR","SI","EE","LV","LT",
  "UA","RS","MT","CY",
  "JP","KR","CN","HK","TW","SG","MY","TH","VN","ID","PH","IN",
  "PK","BD","LK","MN",
  "BR","AR","CL","CO","PE","UY","CR","PA","EC","VE",
  "ZA","EG","NG","KE","MA","TN","MU",
  "AE","SA","IL","TR","QA","KW","BH","OM","JO","LB",
  "RU","KZ","GE","AM","AZ","UZ"
)
$yearList = $Years.Split(",") | ForEach-Object { $_.Trim() }

Write-Host "Fetching $($countries.Count) countries x $($yearList.Count) years -> $CacheDir"

$countries | ForEach-Object -Parallel {
  $cc = $_
  $years = $using:yearList
  $cacheRoot = $using:CacheDir
  $dir = Join-Path $cacheRoot $cc
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  foreach ($y in $years) {
    $out = Join-Path $dir "$y.json"
    if ((Test-Path $out) -and ((Get-Item $out).Length -gt 2)) { continue }
    for ($attempt = 1; $attempt -le 4; $attempt++) {
      curl.exe -s --max-time 30 -o $out "https://date.nager.at/api/v3/PublicHolidays/$y/$cc" | Out-Null
      $size = 0
      if (Test-Path $out) { $size = (Get-Item $out).Length }
      if ($size -gt 2) { break }
      Start-Sleep -Milliseconds (300 * $attempt)
    }
  }
} -ThrottleLimit 8

$files = Get-ChildItem -Path $CacheDir -Recurse -Filter *.json -ErrorAction SilentlyContinue
$good = @($files | Where-Object { $_.Length -gt 2 }).Count
Write-Host "FETCH_DONE files=$($files.Count) nonEmpty=$good"
