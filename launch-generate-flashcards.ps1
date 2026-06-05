# ── Portable vault root ─────────────────────────────────────────────
# Set VAULT_ROOT in your environment, or this falls back to the
# directory the script lives in.
$VaultRoot = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
# Obsidian vault name (for the advanced-uri sync). Override with
# OBSIDIAN_VAULT; defaults to the vault root's folder name.
$VaultName = if ($env:OBSIDIAN_VAULT) { $env:OBSIDIAN_VAULT } else {
    Split-Path -Leaf $VaultRoot
}
# ────────────────────────────────────────────────────────────────────
Set-Location $VaultRoot

# UTF-8 console output so ✓, ⚠, em-dashes etc. render correctly in the run table.
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

# Renders FLASHCARD_RUN_RESULT.json as a console-aligned table.
function Show-FlashcardRunTable {
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
    if (-not $result.rows -or @($result.rows).Count -eq 0) {
        Write-Host "(run-result has no rows)" -ForegroundColor DarkGray
        return
    }

    # Column definitions in display order with header text and width cap
    $cols = @(
        [PSCustomObject]@{ Key="moc";     Header="MOC";              Cap=32 }
        [PSCustomObject]@{ Key="concept"; Header="Concept";          Cap=45 }
        [PSCustomObject]@{ Key="what";    Header="What";             Cap=6  }
        [PSCustomObject]@{ Key="how";     Header="How";              Cap=6  }
        [PSCustomObject]@{ Key="when";    Header="When";             Cap=6  }
        [PSCustomObject]@{ Key="status";  Header="Status & comment"; Cap=60 }
    )

    # Compute final column widths (max of header and longest data value, capped)
    foreach ($c in $cols) {
        $max = $c.Header.Length
        foreach ($row in $result.rows) {
            $v = if ($null -ne $row.($c.Key)) { [string]$row.($c.Key) } else { "" }
            if ($v.Length -gt $max) { $max = $v.Length }
        }
        if ($max -gt $c.Cap) { $max = $c.Cap }
        $c | Add-Member -NotePropertyName Width -NotePropertyValue $max -Force
    }

    Write-Host ""
    Write-Host ("Flashcard run summary - {0}" -f $result.generated) -ForegroundColor Cyan

    # Header + separator
    $headerLine = ($cols | ForEach-Object { $_.Header.PadRight($_.Width) }) -join "  "
    $sepLine    = ($cols | ForEach-Object { ("-" * $_.Width) }) -join "  "
    Write-Host $headerLine -ForegroundColor White
    Write-Host $sepLine    -ForegroundColor DarkGray

    # Sort and print rows; collapse repeated MOC values for visual grouping
    $sorted = $result.rows | Sort-Object @{Expression="moc"}, @{Expression="concept"}
    $lastMoc = $null
    foreach ($row in $sorted) {
        $line = ($cols | ForEach-Object {
            $val = if ($null -ne $row.($_.Key)) { [string]$row.($_.Key) } else { "" }
            if ($_.Key -eq "moc" -and $val -eq $lastMoc) { $val = "" }
            if ($val.Length -gt $_.Width) { $val = $val.Substring(0, $_.Width - 3) + "..." }
            $val.PadRight($_.Width)
        }) -join "  "

        # Colour cue based on status text
        $colour = "Gray"
        if ($row.status -match "(?i)patched") { $colour = "Green" }
        if ($row.status -match "(?i)skipped|FAILED|missing") { $colour = "Yellow" }
        if ($row.status -match "(?i)FAILED") { $colour = "Red" }

        Write-Host $line -ForegroundColor $colour
        $lastMoc = $row.moc
    }

    # Totals line
    if ($result.totals) {
        $t = $result.totals
        Write-Host ""
        $tot = "Generated: {0} concepts ({1} cards)  |  Sources patched: {2}  |  Skipped: {3}  |  MOC files: {4}" -f `
            $t.concepts_generated, $t.cards_total, $t.sources_patched, $t.skipped, $t.moc_files_touched
        Write-Host $tot -ForegroundColor Green
    }
    Write-Host ""
}


# Ensure Anki is running and AnkiConnect is ready
$ankiProcess = Get-Process -Name "anki" -ErrorAction SilentlyContinue
if (-not $ankiProcess) {
    Write-Host "Anki is not running - launching it..." -ForegroundColor Yellow
    $ankiPath = if ($env:ANKI_EXE) { $env:ANKI_EXE } else {
        "$env:LOCALAPPDATA\Programs\Anki\anki.exe"
    }
    if (Test-Path $ankiPath) { Start-Process $ankiPath }
    else { Write-Warning "Anki not found at $ankiPath - set ANKI_EXE to override." }
    Write-Host "Waiting for AnkiConnect to be ready..." -ForegroundColor Yellow
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8765" -Method Post `
                -Body '{"action":"version","version":6}' -ContentType "application/json" -ErrorAction Stop
            if ($response.result) { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) {
        Write-Host "AnkiConnect did not respond after 40s - aborting." -ForegroundColor Red
        exit 1
    }
    Write-Host "Anki is ready." -ForegroundColor Green
} else {
    Write-Host "Anki is already running." -ForegroundColor Green
}

Write-Host "Regenerating vault index..." -ForegroundColor Cyan
python generate_index.py

$indexPath = Join-Path $VaultRoot "00_Inbox\VAULT_INDEX.json"
$index = Get-Content $indexPath -Raw | ConvertFrom-Json
$eligible = @($index.notes | Where-Object { $_.status -eq "final" -and $_.reviewed -eq $true -and $_.flashcards -eq $false })

if ($eligible.Count -eq 0) {
    Write-Host "No final reviewed notes need flashcards - nothing to process." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($eligible.Count) note(s) eligible for flashcard generation." -ForegroundColor Cyan

Write-Host "`nExtracting candidate fields into manifest..." -ForegroundColor Cyan
& (Join-Path $VaultRoot "extract_flashcard_candidates.ps1")

Write-Host "`nStarting flashcard generator..." -ForegroundColor Green
claude --remote-control "PKM Generate Flashcards" generate-flashcards

# Render the run summary as a console-aligned table (uses GF-4 JSON output)
Show-FlashcardRunTable -JsonPath (Join-Path $VaultRoot "00_Inbox\FLASHCARD_RUN_RESULT.json")

# Sync each newly created flashcard file to Anki via Advanced URI
Write-Host "`nSyncing flashcards to Anki..." -ForegroundColor Cyan
$flashcardsFolder = Join-Path $VaultRoot "20_Learning\23_FlashCards"
$synced = 0

$encodedCommand = [Uri]::EscapeDataString("flashcards-obsidian:generate-flashcard-current-file")
$encodedVault   = [Uri]::EscapeDataString($VaultName)

# Build the set of MOC stems touched by this batch (one Flashcards_<MOC>.md per MOC).
$mocsTouched = @{}
foreach ($note in $eligible) {
    $mocStem = $null
    if ($note.moc) {
        if ($note.moc -is [array] -and $note.moc.Count -gt 0) {
            $mocStem = $note.moc[0]
        } elseif ($note.moc -is [string]) {
            $mocStem = $note.moc
        }
    }
    if ($mocStem) { $mocsTouched[$mocStem] = $true }
}

# Sync each MOC flashcard file that exists. Per-MOC = far fewer URI calls than per-concept.
foreach ($mocStem in $mocsTouched.Keys) {
    $mocFilePath = Join-Path $flashcardsFolder "Flashcards_$mocStem.md"
    if (Test-Path $mocFilePath) {
        $relPath = "20_Learning/23_FlashCards/Flashcards_$mocStem.md"
        $encodedPath = [Uri]::EscapeDataString($relPath)
        $uri = "obsidian://advanced-uri?vault=" + $encodedVault + "&filepath=" + $encodedPath + "&commandid=" + $encodedCommand
        Start-Process $uri
        Start-Sleep -Milliseconds 2500

        $synced++
        Write-Host "  Synced: Flashcards_$mocStem.md" -ForegroundColor DarkGray
    } else {
        Write-Host "  Skipped (file missing): Flashcards_$mocStem.md" -ForegroundColor DarkYellow
    }
}

Write-Host "Synced $synced flashcard file(s) to Anki." -ForegroundColor Green
