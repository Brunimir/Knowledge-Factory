# Resolve flagged navigation stubs up front. -IncludeStubs generates cards
# for them without prompting; omit it to be asked once (default: skip).
param(
    [switch]$IncludeStubs
)

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
# Eligibility is `status:final` AND `flashcards:false`. The retired `reviewed`
# key was dropped from this filter: it was retired from the schema, so
# `$_.reviewed` was $null on every note and this predicate matched NOTHING
# while eligible notes silently piled up. Keep this in step with
# extract_flashcard_candidates.ps1, which owns the same rule.
$eligible = @($index.notes | Where-Object { $_.status -eq "final" -and $_.flashcards -eq $false })

if ($eligible.Count -eq 0) {
    Write-Host "No final notes need flashcards - nothing to process." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($eligible.Count) note(s) eligible for flashcard generation." -ForegroundColor Cyan

Write-Host "`nExtracting candidate fields into manifest..." -ForegroundColor Cyan
& (Join-Path $VaultRoot "extract_flashcard_candidates.ps1")

# Resolve flagged navigation stubs ONCE here so the agent never stops mid-batch
# to ask. Write the decision into the manifest; GF-1 obeys it.
$candManifestPath = Join-Path $VaultRoot "00_Inbox\FLASHCARD_CANDIDATES.json"
if (Test-Path $candManifestPath) {
    try {
        $cand = Get-Content $candManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $stubs = @($cand.candidates | Where-Object { $_.is_stub -eq $true })
        $decision = [bool]$IncludeStubs
        if ($stubs.Count -gt 0 -and -not $IncludeStubs) {
            Write-Host ""
            Write-Host "$($stubs.Count) candidate(s) flagged as navigation stubs:" -ForegroundColor Yellow
            foreach ($s in $stubs) { Write-Host "  - $($s.stem): $($s.stub_reason)" -ForegroundColor DarkYellow }
            $ans = Read-Host "Generate stub-cards anyway? (y/N)"
            $decision = ($ans -match '^(y|yes)$')
        }
        $cand | Add-Member -NotePropertyName include_stubs -NotePropertyValue $decision -Force
        $cand | ConvertTo-Json -Depth 10 | Set-Content -Path $candManifestPath -Encoding UTF8
        if ($stubs.Count -gt 0) {
            Write-Host "Stub decision recorded in manifest: include_stubs = $decision" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  (could not resolve stubs from manifest: $($_.Exception.Message))" -ForegroundColor DarkYellow
    }
}

Write-Host "`nStarting flashcard generator..." -ForegroundColor Green
# Capture run start BEFORE the agent writes any file, so the fallback
# "newest Flashcards_*.md modified since the run began" is reliable.
$runStart = Get-Date
claude --model sonnet --remote-control "PKM Generate Flashcards" generate-flashcards

# Render the run summary as a console-aligned table (uses GF-4 JSON output)
$resultPath = Join-Path $VaultRoot "00_Inbox\FLASHCARD_RUN_RESULT.json"
Show-FlashcardRunTable -JsonPath $resultPath

# Sync each newly WRITTEN flashcard file to Anki via Advanced URI.
# CRITICAL: sync the file the agent actually wrote this run, not a guessed
# batch-1 name. From batch 2 onward the new file is "Flashcards_{MOC} - Batch N.md";
# syncing the bare "Flashcards_{MOC}.md" re-syncs an old file and silently drops
# the new cards (the documented AnkiConnect duplicate trap).
Write-Host "`nSyncing flashcards to Anki..." -ForegroundColor Cyan
$flashcardsFolder = Join-Path $VaultRoot "20_Learning\23_FlashCards"
$synced = 0
$syncFailures = @()

$encodedCommand = [Uri]::EscapeDataString("flashcards-obsidian:generate-flashcard-current-file")
$encodedVault   = [Uri]::EscapeDataString($VaultName)

# PRIMARY source of truth: files_written[] written by GF-4.
$filesToSync = @()
$resultJson = $null
if (Test-Path $resultPath) {
    try {
        $resultJson = Get-Content $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($resultJson.files_written) {
            $filesToSync = @($resultJson.files_written | ForEach-Object { Split-Path $_ -Leaf })
        }
    } catch {
        Write-Host "  (could not parse $resultPath : $($_.Exception.Message))" -ForegroundColor DarkYellow
    }
}

# FALLBACK: any flashcard file modified since the run began.
if ($filesToSync.Count -eq 0) {
    Write-Host "  GF-4 produced no files_written[]; falling back to newest-modified flashcard files." -ForegroundColor DarkYellow
    $filesToSync = @(Get-ChildItem $flashcardsFolder -Filter "Flashcards_*.md" |
        Where-Object { $_.LastWriteTime -gt $runStart } |
        ForEach-Object { $_.Name })
}

if ($filesToSync.Count -eq 0) {
    Write-Host "  Nothing to sync (no flashcard files written this run)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------- GATE-KF-05
# THIS IS THE LAST REVERSIBLE MOMENT IN THE RUN. Once the plugin syncs a file
# it writes a 13-digit ^id into it and the cards acquire Anki review history;
# correcting them afterwards destroys that history. So the content checks run
# HERE - after the agent has written, before anything reaches Anki - and a
# blocked file is removed from the sync set rather than fixed in place.
if ($filesToSync.Count -gt 0) {
    Write-Host "`nGATE-KF-05 (flashcard content checks)..." -ForegroundColor Cyan
    python (Join-Path $VaultRoot "gate_kf05.py")
    $gateExit = $LASTEXITCODE
    $gatePath = Join-Path $VaultRoot "00_Inbox\GATE_KF05_RESULT.json"

    if ($gateExit -eq 2 -or -not (Test-Path $gatePath)) {
        # Fail CLOSED. A gate that cannot run must not wave the batch through
        # into a store we cannot correct.
        Write-Host "  GATE-KF-05 could not run - refusing to sync this run." -ForegroundColor Red
        $filesToSync = @()
    } else {
        $gate = Get-Content $gatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $blockedFiles = @($gate.blocked)
        if ($blockedFiles.Count -gt 0) {
            $filesToSync = @($filesToSync | Where-Object { $blockedFiles -notcontains $_ })

            # A blocked file was never really generated, so its sources must not
            # claim it was. GF-3 has already set flashcards:true, so revert
            # exactly that line - Safety Rule #6a permits this toggle on a
            # status:final note, and nothing else here is touched.
            foreach ($r in $gate.results) {
                if (-not $r.blocked) { continue }
                foreach ($c in $r.concepts) {
                    $src = Join-Path $VaultRoot "20_Learning\21_Concepts\$($c.stem).md"
                    if (Test-Path $src) {
                        $body = Get-Content $src -Raw -Encoding UTF8
                        $rev  = $body -replace '(?m)^flashcards: true\s*$', 'flashcards: false'
                        if ($rev -ne $body) {
                            Set-Content -Path $src -Value $rev -Encoding UTF8 -NoNewline
                            Write-Host "    reverted flashcards:false on $($c.stem) - its file was blocked" -ForegroundColor Yellow
                        }
                    }
                }
            }
            Write-Host "  $($blockedFiles.Count) file(s) BLOCKED, not synced: $($blockedFiles -join ', ')" -ForegroundColor Red
        }
    }
}

# Track per-file sync verification to write back into the result JSON.
$syncVerification = @()

foreach ($fileName in $filesToSync) {
    $leaf = Split-Path $fileName -Leaf
    $filePath = Join-Path $flashcardsFolder $leaf
    if (-not (Test-Path $filePath)) {
        Write-Host "  Skipped (file missing): $leaf" -ForegroundColor DarkYellow
        $syncVerification += [PSCustomObject]@{ file = $leaf; synced = $false; reason = "file missing" }
        $syncFailures += $leaf
        continue
    }

    $relPath = "20_Learning/23_FlashCards/$leaf"
    $encodedPath = [Uri]::EscapeDataString($relPath)
    $uri = "obsidian://advanced-uri?vault=" + $encodedVault + "&filepath=" + $encodedPath + "&commandid=" + $encodedCommand
    Start-Process $uri
    Start-Sleep -Milliseconds 2500

    # VERIFY: a successfully synced file gains Anki ID markers written back by the
    # plugin (<!--ID:nnn--> or a ^NNNNNNNNNNNNN line). No IDs => the silent-fail
    # duplicate trap likely fired. Retry a few times to absorb async write-back.
    $hasIds = $false
    for ($r = 0; $r -lt 3; $r++) {
        $body = Get-Content $filePath -Raw -Encoding UTF8
        if ($body -match '<!--ID:\d+-->' -or $body -match '(?m)^\^\d{13}\s*$') { $hasIds = $true; break }
        Start-Sleep -Milliseconds 1500
    }

    if ($hasIds) {
        $synced++
        Write-Host "  Synced + verified (Anki IDs present): $leaf" -ForegroundColor Green
        $syncVerification += [PSCustomObject]@{ file = $leaf; synced = $true; reason = "ids present" }
    } else {
        Write-Host "  WARNING: $leaf has NO Anki IDs after sync." -ForegroundColor Red
        Write-Host "           The AnkiConnect silent-fail duplicate trap may have fired." -ForegroundColor Red
        Write-Host "           Open Obsidian dev console (Ctrl+Shift+I) for 'duplicate' errors," -ForegroundColor Red
        Write-Host "           delete the orphan Anki cards via Browse, then re-sync this file." -ForegroundColor Red
        $syncVerification += [PSCustomObject]@{ file = $leaf; synced = $false; reason = "no Anki IDs after sync" }
        $syncFailures += $leaf
    }
}

# Persist verification back into the result JSON so GF-3's flashcards:true claim
# can be reconciled against sync reality (vault-health reads this).
if ($resultJson) {
    $resultJson | Add-Member -NotePropertyName sync_verification -NotePropertyValue $syncVerification -Force
    try {
        $resultJson | ConvertTo-Json -Depth 8 | Set-Content -Path $resultPath -Encoding UTF8
    } catch {
        Write-Host "  (could not write sync_verification back to result JSON: $($_.Exception.Message))" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Synced + verified $synced flashcard file(s) to Anki." -ForegroundColor Green
if ($syncFailures.Count -gt 0) {
    Write-Host "$($syncFailures.Count) file(s) FAILED verification: $($syncFailures -join ', ')" -ForegroundColor Red
    Write-Host "Their source notes should NOT be trusted as 'studied' until re-synced." -ForegroundColor Red
}

# Final reconciliation against Anki (source of truth). The per-file marker check
# above reads markdown only, so it cannot tell "card is in Anki but the markdown is
# unlinked" (write-back lost the race with cloud sync) from "never reached Anki".
# verify_flashcard_sync.ps1 asks AnkiConnect directly and reconciles both sides.
Write-Host "`nFinal sync verification (AnkiConnect = source of truth)..." -ForegroundColor Cyan
& (Join-Path $VaultRoot "verify_flashcard_sync.ps1") -FlashcardsDir $flashcardsFolder
$verifyExit = $LASTEXITCODE
if ($verifyExit -eq 0) {
    Write-Host "Flashcard sync verification: PASS." -ForegroundColor Green
} elseif ($verifyExit -eq 2) {
    Write-Host "Flashcard sync verification could not reach Anki - re-run verify_flashcard_sync.ps1 with Anki open." -ForegroundColor Yellow
} else {
    Write-Host "Flashcard sync verification FAILED (exit $verifyExit) - see issues above; source notes' 'studied' status is not trustworthy until resolved." -ForegroundColor Red
}
