# launch-visualise-moc.ps1
# Pre-flight + post-flight wrapper for the visualise-moc agent.
#
# Pre-flight:
#   1. mmdc doctor check (global preferred, npx fallback, install hint if missing)
#   2. Regenerate VAULT_INDEX.json
#   3. Validate the MOC stem against the index
#   4. Run extract_diagram_candidates.ps1 to build the per-MOC manifest
#   5. Create the DIAGRAM_BUILD/{moc_stem}/ working folder
#   6. Invoke claude with visualise-moc {moc_stem}
#
# Post-flight:
#   - Render DIAGRAM_RUN_RESULT.json as a console-aligned table
#
# Validation of generated Mermaid is performed by the agent itself
# (PHASE V-4 in docs/visualisation-pipeline.md), not by this launcher.

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

# --- Run-table renderer (post-flight) -----------------------------------

function Show-DiagramRunTable {
    param([string]$JsonPath)
    if (-not (Test-Path $JsonPath)) {
        Write-Host "(no run-result JSON found at $JsonPath)" -ForegroundColor DarkGray
        return
    }
    try {
        $result = Get-Content $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        Write-Host "(could not parse run-result JSON: $($_.Exception.Message))" -ForegroundColor DarkYellow
        return
    }
    if (-not $result.tiers -or @($result.tiers).Count -eq 0) {
        Write-Host "(run-result has no tiers)" -ForegroundColor DarkGray
        return
    }

    $cols = @(
        [PSCustomObject]@{ Key="tier";     Header="Tier";     Cap=10 }
        [PSCustomObject]@{ Key="cluster";  Header="Cluster";  Cap=40 }
        [PSCustomObject]@{ Key="nodes";    Header="Nodes";    Cap=6  }
        [PSCustomObject]@{ Key="edges";    Header="Edges";    Cap=6  }
        [PSCustomObject]@{ Key="headline"; Header="Headline"; Cap=50 }
        [PSCustomObject]@{ Key="status";   Header="Status";   Cap=14 }
    )

    foreach ($c in $cols) {
        $max = $c.Header.Length
        foreach ($row in $result.tiers) {
            $v = if ($null -ne $row.($c.Key)) { [string]$row.($c.Key) } else { "" }
            if ($v.Length -gt $max) { $max = $v.Length }
        }
        if ($max -gt $c.Cap) { $max = $c.Cap }
        $c | Add-Member -NotePropertyName Width -NotePropertyValue $max -Force
    }

    Write-Host ""
    Write-Host ("Diagram run summary - {0} ({1})" -f $result.moc_stem, $result.generated) -ForegroundColor Cyan

    $headerLine = ($cols | ForEach-Object { $_.Header.PadRight($_.Width) }) -join "  "
    $sepLine    = ($cols | ForEach-Object { ("-" * $_.Width) }) -join "  "
    Write-Host $headerLine -ForegroundColor White
    Write-Host $sepLine    -ForegroundColor DarkGray

    foreach ($row in $result.tiers) {
        $line = ($cols | ForEach-Object {
            $val = if ($null -ne $row.($_.Key)) { [string]$row.($_.Key) } else { "" }
            if ($val.Length -gt $_.Width) { $val = $val.Substring(0, $_.Width - 3) + "..." }
            $val.PadRight($_.Width)
        }) -join "  "

        $colour = "Gray"
        if ($row.status -match "(?i)rendered") { $colour = "Green" }
        if ($row.status -match "(?i)quarantined|failed") { $colour = "Red" }
        if ($row.status -match "(?i)skipped|warn") { $colour = "Yellow" }

        Write-Host $line -ForegroundColor $colour
    }

    if ($result.grice) {
        Write-Host ""
        $g = $result.grice
        Write-Host ("Grice audit: Quantity {0} | Quality {1} | Relevance {2} | Manner {3}" -f $g.quantity, $g.quality, $g.relevance, $g.manner) -ForegroundColor DarkCyan
    }
    if ($result.pruned) {
        $p = $result.pruned
        Write-Host ("Pruned: {0} related-to edges, {1} dangling nodes" -f $p.related_to_edges, $p.dangling_nodes) -ForegroundColor DarkCyan
    }
    if ($result.warnings -and @($result.warnings).Count -gt 0) {
        Write-Host ""
        Write-Host "Warnings:" -ForegroundColor Yellow
        foreach ($w in $result.warnings) { Write-Host ("  - {0}" -f $w) -ForegroundColor Yellow }
    }
    if ($result.quarantined -and @($result.quarantined).Count -gt 0) {
        Write-Host ""
        Write-Host "Quarantined (open and fix manually):" -ForegroundColor Red
        foreach ($q in $result.quarantined) { Write-Host ("  - {0}" -f $q) -ForegroundColor Red }
    }
    Write-Host ""
}

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

# Write mode sentinel so the agent knows which command form to use
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

# Clear stale .mmd/.svg from any prior run for this MOC so the agent
# starts with an empty work area.
Get-ChildItem $buildFolder -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Clear any prior run-result JSON so a partial render doesn't get
# mis-rendered in the post-flight table.
$resultPath = Join-Path $vaultRoot "00_Inbox\DIAGRAM_RUN_RESULT.json"
if (Test-Path $resultPath) { Remove-Item $resultPath -Force }

# --- Invoke the agent ---------------------------------------------------

Write-Host ""
Write-Host "Starting visualisation agent..." -ForegroundColor Green
claude --remote-control "PKM Visualise MOC" "visualise-moc $MocStem"

# --- Post-flight: render run table --------------------------------------

Show-DiagramRunTable -JsonPath $resultPath
