# launch-weave-links.ps1
# Pre-flight wrapper for weave-links.
#
# Before this script existed, weave-links had no launcher at all: it was
# invoked directly (`claude ... weave-links {scope}`), and PHASE IC-2 had the
# agent propose cross-MOC candidates by eyeballing index descriptions with NO
# numeric floor — despite interconnect-pipeline.md's own header claiming
# weave-links shared the calibrated 0.70 dense-cosine search with
# process-inbox. It didn't; only process-inbox actually called
# overlap_candidates.py (via this script's sibling, launch-process-inbox.ps1).
#
# This closes that gap the same way the other four launchers already do it:
# pre-compute the candidate manifest deterministically, BEFORE the agent
# starts, so the check cannot be skipped or done differently run to run.
#
# Steps:
#   1. Regenerate VAULT_INDEX.json (staleness gate)
#   2. Validate every MOC stem against the index; require at least 2
#   3. Build 00_Inbox\WEAVE_CANDIDATES.json (overlap_candidates.py weave ...)
#   4. Invoke claude weave-links {scope}

param(
    [Parameter(Mandatory=$true)]
    [string[]]$MocStems
)

# ── Portable vault root ─────────────────────────────────────────────
# Set VAULT_ROOT in your environment, or this falls back to the
# directory the script lives in.
$VaultRoot = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
# ────────────────────────────────────────────────────────────────────
Set-Location $VaultRoot

if ($MocStems.Count -lt 2) {
    Write-Host "weave-links needs at least 2 MOCs; got: $($MocStems -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "Regenerating vault index..." -ForegroundColor Cyan
python generate_index.py

$indexPath = Join-Path $VaultRoot "00_Inbox\VAULT_INDEX.json"
if (-not (Test-Path $indexPath)) {
    Write-Host "Index regeneration failed - $indexPath not found." -ForegroundColor Red
    exit 1
}
$index = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
$validMocs = @($index.mocs | ForEach-Object { $_.stem })

$unknown = @($MocStems | Where-Object { $validMocs -notcontains $_ })
if ($unknown.Count -gt 0) {
    Write-Host "Unknown MOC stem(s): $($unknown -join ', ')" -ForegroundColor Red
    Write-Host "Valid MOC stems:" -ForegroundColor Yellow
    foreach ($m in ($validMocs | Sort-Object)) { Write-Host "  - $m" -ForegroundColor DarkGray }
    exit 1
}

Write-Host ""
Write-Host "Building cross-MOC candidate manifest (dense-cosine >= 0.70)..." -ForegroundColor Cyan
python overlap_candidates.py weave $MocStems
if ($LASTEXITCODE -ne 0) {
    Write-Host "  overlap_candidates.py failed - aborting before the agent starts." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting weave-links agent..." -ForegroundColor Green
claude --model sonnet --remote-control "PKM Weave Links" "weave-links $($MocStems -join ' ')"
