# launch-visualise-moc.ps1
# End-to-end wrapper for visualise-moc. FULLY DETERMINISTIC — no `claude`
# invocation; the agent is not in this loop.
#
# Steps:
#   1. mmdc doctor check (global preferred, npx fallback, install hint if missing);
#      writes 00_Inbox\MMDC_MODE.txt, which build_diagrams.ps1 reads
#   2. Regenerate VAULT_INDEX.json
#   3. Validate the MOC stem against the index
#   4. Run extract_diagram_candidates.ps1 to build the per-MOC manifest
#   5. Create the DIAGRAM_BUILD/{moc_stem}/ working folder
#   6. Run build_diagrams.ps1 (renders the SVGs and patches the MOC)
#
# Post-flight:
#   - Summarise build_diagrams.ps1's DIAGRAM_RENDER_PLAN.json (tiers, wide/failed)

param(
    [Parameter(Mandatory=$true)]
    [string]$MocStem
)

# ── Portable vault root ─────────────────────────────────────────────
# Set VAULT_ROOT in your environment, or this falls back to the
# directory the script lives in.
$VaultRoot = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
# ────────────────────────────────────────────────────────────────────
Set-Location $VaultRoot

$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$vaultRoot = $VaultRoot
$indexPath = Join-Path $vaultRoot "00_Inbox\VAULT_INDEX.json"

# --- Pre-flight 1: mmdc doctor check ------------------------------------

Write-Host "Checking for Mermaid CLI (mmdc)..." -ForegroundColor Cyan

$mmdcMode = $null
$globalMmdc = Get-Command mmdc -ErrorAction SilentlyContinue
if ($globalMmdc) {
    try {
        $ver = (& mmdc --version) 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  mmdc (global) found: $ver" -ForegroundColor Green
            $mmdcMode = "global"
        }
    } catch {}
}

if (-not $mmdcMode) {
    $npxAvailable = Get-Command npx -ErrorAction SilentlyContinue
    if ($npxAvailable) {
        Write-Host "  mmdc not installed globally - falling back to: npx -y @mermaid-js/mermaid-cli" -ForegroundColor Yellow
        Write-Host "  (For faster runs, install globally: npm i -g @mermaid-js/mermaid-cli)" -ForegroundColor DarkGray
        $mmdcMode = "npx"
    } else {
        Write-Host "  ⚠ Neither mmdc nor npx is available." -ForegroundColor Red
        Write-Host "  Install Node.js (https://nodejs.org) then run:" -ForegroundColor Red
        Write-Host "    npm i -g @mermaid-js/mermaid-cli" -ForegroundColor Red
        Write-Host "  Aborting." -ForegroundColor Red
        exit 1
    }
}

# Write mode sentinel so build_diagrams.ps1 knows which command form to use
$modePath = Join-Path $vaultRoot "00_Inbox\MMDC_MODE.txt"
[System.IO.File]::WriteAllText($modePath, $mmdcMode, (New-Object System.Text.UTF8Encoding($false)))

# --- Pre-flight 2: regenerate index -------------------------------------

Write-Host ""
Write-Host "Regenerating vault index..." -ForegroundColor Cyan
python generate_index.py

if (-not (Test-Path $indexPath)) {
    Write-Host "⚠ Index regeneration failed - $indexPath not found." -ForegroundColor Red
    exit 1
}

# --- Pre-flight 3: validate MOC stem ------------------------------------

$index = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
$validMocs = @($index.mocs | ForEach-Object { $_.stem })

if ($validMocs -notcontains $MocStem) {
    Write-Host ""
    Write-Host "⚠ Unknown MOC stem '$MocStem'." -ForegroundColor Red
    Write-Host "Valid MOC stems:" -ForegroundColor Yellow
    foreach ($m in ($validMocs | Sort-Object)) {
        Write-Host "  - $m" -ForegroundColor DarkGray
    }
    exit 1
}

Write-Host ""
Write-Host "Target MOC: $MocStem" -ForegroundColor Green

# --- Pre-flight 4: build per-MOC manifest -------------------------------

Write-Host ""
Write-Host "Extracting diagram manifest..." -ForegroundColor Cyan
& (Join-Path $vaultRoot "extract_diagram_candidates.ps1") -MocStem $MocStem

$manifestPath = Join-Path $vaultRoot ("00_Inbox\DIAGRAM_CANDIDATES_" + $MocStem + ".json")
if (-not (Test-Path $manifestPath)) {
    Write-Host "⚠ Manifest not written at $manifestPath - aborting." -ForegroundColor Red
    exit 1
}

# --- Pre-flight 5: prepare DIAGRAM_BUILD working folder -----------------

$buildFolder = Join-Path $vaultRoot ("00_Inbox\DIAGRAM_BUILD\" + $MocStem)
if (-not (Test-Path $buildFolder)) {
    New-Item -ItemType Directory -Path $buildFolder -Force | Out-Null
}

# Clear stale .mmd/.svg from any prior run for this MOC so the generator
# starts with an empty work area.
Get-ChildItem $buildFolder -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# --- Build diagrams (deterministic generator; no agent in the loop) -----

Write-Host ""
Write-Host "Building diagrams (deterministic generator)..." -ForegroundColor Green
& (Join-Path $vaultRoot "build_diagrams.ps1") -MocStem $MocStem

# --- Post-flight: summarise the render plan -----------------------------

$planPath = Join-Path $vaultRoot "00_Inbox\DIAGRAM_RENDER_PLAN.json"
if (Test-Path $planPath) {
    try {
        $plan = Get-Content $planPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $wide = @($plan.tiers | Where-Object { $_.status -eq "wide" })
        $fail = @($plan.tiers | Where-Object { $_.status -eq "failed" })
        Write-Host ""
        Write-Host ("Render complete: {0} tiers, embed width {1}px, cap {2}." -f @($plan.tiers).Count, $plan.display_width, $plan.cap) -ForegroundColor Cyan
        if ($fail.Count -gt 0) { Write-Host ("  FAILED: "        + (($fail | ForEach-Object { $_.cluster }) -join ", ")) -ForegroundColor Red }
        if ($wide.Count -gt 0) { Write-Host ("  wide (review): " + (($wide | ForEach-Object { $_.cluster }) -join ", ")) -ForegroundColor Yellow }
    } catch {
        Write-Host "(could not parse render plan: $($_.Exception.Message))" -ForegroundColor DarkYellow
    }
}
