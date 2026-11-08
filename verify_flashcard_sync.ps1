<#
.SYNOPSIS
  Verify flashcards-obsidian <-> Anki sync integrity. Run AFTER a plugin sync.

.DESCRIPTION
  AnkiConnect is treated as the SOURCE OF TRUTH (so a missing markdown marker can
  never again be misread as "cards did not reach Anki"). The script:

    1. Parses every Flashcards_*.md and counts inline cards (lines with the '::'
       separator) and their '^<13-digit-id>' block-ref markers (the format the
       flashcards-obsidian plugin writes back on a successful sync).
    2. Queries AnkiConnect (findNotes deck:"...", notesInfo) and reconciles:
         - every markdown ^id exists in the Anki deck         (else: STALE LINK)
         - every Anki note is referenced by a markdown ^id     (else: ORPHAN in Anki)
         - markdown cards with NO id whose front ({H1} > {question}) already exists
           in Anki                                             (the DUPLICATE TRAP:
           card is live in Anki but the markdown is unlinked, so the next sync would
           create a duplicate)

  Exit codes:  0 = clean   |   1 = mismatch found   |   2 = AnkiConnect unreachable

.PARAMETER Deck
  Anki deck to check. Default matches folderBasedDeck for this vault.

.EXAMPLE
  powershell -File verify_flashcard_sync.ps1
#>
param(
  [string]$FlashcardsDir = $(
      $vr = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
      Join-Path $vr "20_Learning\23_FlashCards"
  ),
  [string]$Deck          = "20_Learning::23_FlashCards",
  [string]$AnkiUrl       = "http://127.0.0.1:8765"
)

function Invoke-Anki($action, $params) {
  $body = @{ action = $action; version = 6 }
  if ($params) { $body.params = $params }
  Invoke-RestMethod -Uri $AnkiUrl -Method Post -Body ($body | ConvertTo-Json -Depth 8) `
                    -ContentType "application/json" -TimeoutSec 30
}
function Clean([string]$s) {
  $s = $s -replace '<[^>]+>',''                  # strip HTML tags Anki adds
  $s = [System.Net.WebUtility]::HtmlDecode($s)   # &gt; &amp; -> > &
  ($s -replace '\s+',' ').Trim()
}

$cardRe = '^(.*\S.*?)\s*::\s*(.+)$'
$files = @(Get-ChildItem $FlashcardsDir -Filter "Flashcards_*.md" -File -ErrorAction SilentlyContinue)
if ($files.Count -eq 0) { Write-Host "No flashcard files in $FlashcardsDir"; exit 0 }

# ---- 1. Parse markdown -------------------------------------------------------
$mdCards = New-Object System.Collections.Generic.List[object]
$perFile = New-Object System.Collections.Generic.List[object]
$idOwner = @{}      # id -> first file that used it (duplicate-id detection)
$dupIds  = New-Object System.Collections.Generic.List[string]

foreach ($f in $files) {
  $lines = Get-Content $f.FullName -Encoding UTF8
  $h1 = (($lines | Where-Object { $_ -match '^#\s+\S' } | Select-Object -First 1) -replace '^#\s+','').Trim()
  $cards = 0; $ids = 0
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $cardRe) {
      $q = Clean $Matches[1]
      $cards++
      $id = $null
      $next = if ($i + 1 -lt $lines.Count) { $lines[$i + 1] } else { '' }
      if ($next -match '^\^(\d{13})$') {
        $id = $Matches[1]; $ids++
        if ($idOwner.ContainsKey($id)) { $dupIds.Add("id $id reused in '$($idOwner[$id])' and '$($f.Name)'") }
        else { $idOwner[$id] = $f.Name }
      }
      $mdCards.Add([pscustomobject]@{ File = $f.Name; Key = "$h1 > $q"; Id = $id })
    }
  }
  $perFile.Add([pscustomobject]@{ File = $f.Name; Cards = $cards; Ids = $ids; Missing = ($cards - $ids) })
}

$totalCards   = ($perFile | Measure-Object Cards -Sum).Sum
$totalIds     = ($perFile | Measure-Object Ids   -Sum).Sum
$totalMissing = ($perFile | Measure-Object Missing -Sum).Sum

Write-Host ""
Write-Host "=== Markdown ($($files.Count) files) ==="
$perFile | Sort-Object File | Format-Table -AutoSize | Out-String | Write-Host
Write-Host ("Markdown totals: {0} cards | {1} with ^id | {2} missing id" -f $totalCards, $totalIds, $totalMissing)

$problems = New-Object System.Collections.Generic.List[string]
if ($totalMissing -gt 0) { $problems.Add("$totalMissing card(s) have no ^id marker (unsynced or write-back failed)") }
foreach ($d in $dupIds) { $problems.Add($d) }

# ---- 2. AnkiConnect cross-check (source of truth) ----------------------------
$ankiReachable = $true
try { [void](Invoke-Anki "version" $null) }
catch { $ankiReachable = $false }

if (-not $ankiReachable) {
  Write-Host ""
  Write-Host "AnkiConnect UNREACHABLE at $AnkiUrl - open Anki (with the AnkiConnect add-on) to cross-check." -ForegroundColor Yellow
  Write-Host "Markdown-only check complete; could not confirm against Anki."
  if ($problems.Count -gt 0) { Write-Host ""; Write-Host "ISSUES:"; $problems | ForEach-Object { Write-Host "  - $_" } }
  exit 2
}

$ankiIds = @((Invoke-Anki "findNotes" @{ query = "deck:`"$Deck`"" }).result | ForEach-Object { "$_" })
$ankiSet = @{}; $ankiIds | ForEach-Object { $ankiSet[$_] = $true }

Write-Host ""
Write-Host "=== Anki (deck `"$Deck`") ==="
Write-Host ("Anki notes in deck: {0}   |   markdown ^ids: {1}" -f $ankiIds.Count, $totalIds)

# a) markdown ^ids that no longer exist in Anki (stale links)
$stale = @($mdCards | Where-Object { $_.Id -and -not $ankiSet.ContainsKey($_.Id) })
foreach ($s in $stale) { $problems.Add("stale link: $($s.File) -> ^$($s.Id) not found in Anki") }

# b) Anki notes not referenced by any markdown ^id (orphan / possible duplicate)
$refSet = @{}; $mdCards | Where-Object { $_.Id } | ForEach-Object { $refSet[$_.Id] = $true }
$orphanAnki = @($ankiIds | Where-Object { -not $refSet.ContainsKey($_) })
if ($orphanAnki.Count -gt 0) { $problems.Add("$($orphanAnki.Count) Anki note(s) in the deck are not referenced by any markdown ^id (orphans/duplicates)") }

# c) duplicate trap: unsynced markdown cards whose front already exists in Anki
$unsynced = @($mdCards | Where-Object { -not $_.Id })
if ($unsynced.Count -gt 0) {
  $info = @((Invoke-Anki "notesInfo" @{ notes = ($ankiIds | ForEach-Object { [int64]$_ }) }).result)
  $frontSet = @{}
  foreach ($n in $info) { $front = ($n.fields.PSObject.Properties | Select-Object -First 1).Value.value; $frontSet[(Clean $front)] = $true }
  $trap = @($unsynced | Where-Object { $frontSet.ContainsKey($_.Key) })
  if ($trap.Count -gt 0) {
    $problems.Add("$($trap.Count) unsynced card(s) ALREADY exist in Anki by front text - re-syncing now would create duplicates (relink ^ids instead of re-adding)")
  }
}

# ---- 3. Verdict --------------------------------------------------------------
Write-Host ""
if ($problems.Count -eq 0) {
  Write-Host "PASS - markdown and Anki are fully reconciled ($totalCards cards <-> $($ankiIds.Count) notes)." -ForegroundColor Green
  exit 0
} else {
  Write-Host "FAIL - $($problems.Count) issue(s):" -ForegroundColor Red
  $problems | ForEach-Object { Write-Host "  - $_" }
  exit 1
}
