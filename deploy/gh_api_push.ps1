param(
  [string]$Repo = "ChaoyuZhang1/holidaykit",
  [string]$Message = "feat: school holidays, country comparisons, countdown expansion, cross-platform curl, CF build script"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$remoteCommit = (gh api "repos/$Repo/git/ref/heads/master" --jq ".object.sha").Trim()
$remoteTree = (gh api "repos/$Repo/git/commits/$remoteCommit" --jq ".tree.sha").Trim()
Write-Host "remote head=$remoteCommit tree=$remoteTree"

$files = @(git diff --name-only origin/master..HEAD)
if (-not $files -or $files.Count -eq 0) { Write-Host "nothing to push"; return }

$entries = @()
foreach ($f in $files) {
  $full = Join-Path $Root $f
  if (-not (Test-Path $full)) { Write-Host "skip missing $f"; continue }
  $bytes = [System.IO.File]::ReadAllBytes($full)
  $b64 = [Convert]::ToBase64String($bytes)
  $payload = @{ content = $b64; encoding = "base64" } | ConvertTo-Json -Compress
  $tmp = Join-Path $env:TEMP "hk_blob.json"
  [System.IO.File]::WriteAllText($tmp, $payload, [System.Text.UTF8Encoding]::new($false))
  $sha = (gh api "repos/$Repo/git/blobs" --method POST --input $tmp --jq ".sha").Trim()
  Remove-Item $tmp -Force
  $entries += @{ path = $f; mode = "100644"; type = "blob"; sha = $sha }
  Write-Host "blob $f -> $sha"
}

$treePayload = @{ base_tree = $remoteTree; tree = $entries } | ConvertTo-Json -Depth 8 -Compress
$tmpTree = Join-Path $env:TEMP "hk_tree.json"
[System.IO.File]::WriteAllText($tmpTree, $treePayload, [System.Text.UTF8Encoding]::new($false))
$treeSha = (gh api "repos/$Repo/git/trees" --method POST --input $tmpTree --jq ".sha").Trim()
Remove-Item $tmpTree -Force
Write-Host "new tree=$treeSha"

$commitPayload = @{ message = $Message; tree = $treeSha; parents = @($remoteCommit) } | ConvertTo-Json -Compress
$tmpCommit = Join-Path $env:TEMP "hk_commit.json"
[System.IO.File]::WriteAllText($tmpCommit, $commitPayload, [System.Text.UTF8Encoding]::new($false))
$commitSha = (gh api "repos/$Repo/git/commits" --method POST --input $tmpCommit --jq ".sha").Trim()
Remove-Item $tmpCommit -Force
Write-Host "new commit=$commitSha"

$refPayload = @{ sha = $commitSha; force = $false } | ConvertTo-Json -Compress
$tmpRef = Join-Path $env:TEMP "hk_ref.json"
[System.IO.File]::WriteAllText($tmpRef, $refPayload, [System.Text.UTF8Encoding]::new($false))
$updated = (gh api "repos/$Repo/git/refs/heads/master" --method PATCH --input $tmpRef --jq ".object.sha").Trim()
Remove-Item $tmpRef -Force
Write-Host "remote master updated -> $updated"
