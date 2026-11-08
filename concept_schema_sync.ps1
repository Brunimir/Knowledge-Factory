<#
.SYNOPSIS
    Brings concept-note frontmatter to the current schema and keeps the
    trustworthiness score correct.

.DESCRIPTION
    Two jobs, both idempotent:

      1. Drops the retired `reviewed:` key (retired 2026-08-02 - it never
         carried information `status` did not already carry).
      2. Maintains `source_count:` and `trust:`.

    source_count = number of [[wikilinks]] on the note's "- Source" line.
    trust        = 0.0                  if source_count == 0
                   2 - 1/source_count   otherwise      (1.0, 1.5, 1.67, 1.75 ...)
                   + 0.2                if status: final

    The curve has diminishing returns and an asymptote at 2.0, so corroboration
    always helps but never dominates; the final bonus caps the scale at 2.2.
    `generate_index.py` re-derives trust from the stored source_count and flags
    any stale score, so drift is always visible even if this script is not run.

    SAFETY
    - DRY RUN BY DEFAULT. Nothing is written without -Apply.
    - Patches ONLY the frontmatter keys above, by targeted line replacement.
      Note bodies are never touched and no file is re-templated.
    - Writes status:final notes. That is permitted by the trust-score amendment
      to Safety Rule #6 (see "Trustworthiness Score - Decision"); before that
      Decision is accepted this script must not be run with -Apply on final
      notes. Use -DraftOnly to stay within the original rule.

.PARAMETER Apply
    Actually write. Without it the script reports what would change and exits.

.PARAMETER DraftOnly
    Skip status:final notes entirely (pre-amendment safe mode).

.EXAMPLE
    .\concept_schema_sync.ps1                 # dry run, full report
    .\concept_schema_sync.ps1 -Apply          # write
    .\concept_schema_sync.ps1 -Apply -DraftOnly
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$DraftOnly
)

$ErrorActionPreference = 'Stop'
$VaultRoot = if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
$ConceptsDir = Join-Path $VaultRoot "20_Learning\21_Concepts"

if (-not (Test-Path $ConceptsDir)) { throw "Concepts folder not found: $ConceptsDir" }

function Get-Trust {
    param([int]$SourceCount, [string]$Status)
    $base = if ($SourceCount -le 0) { 0.0 } else { 2 - (1 / [double]$SourceCount) }
    if ($Status -eq 'final') { $base += 0.2 }
    return [math]::Round($base, 2)
}

$files = Get-ChildItem -Path $ConceptsDir -Filter '*.md' -File
$changed = 0; $skippedFinal = 0; $unchanged = 0; $malformed = @()
$dist = @{}

foreach ($f in $files) {
    $raw = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    # Ordinal check by index, NOT String.StartsWith: .NET Framework compares
    # culture-sensitively by default, and U+FEFF is an ignorable character, so
    # StartsWith([char]0xFEFF) returns true for EVERY string and would chop the
    # first real character off each file.
    if ($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }

    # Frontmatter must be the first block; anything else is a shape problem the
    # sync must report rather than guess at.
    if ($raw -notmatch '(?s)^---\r?\n(.*?)\r?\n---\r?\n') {
        $malformed += $f.Name; continue
    }
    $fm = $Matches[1]
    $fmStart = $Matches[0]
    $body = $raw.Substring($fmStart.Length)

    $status = if ($fm -match '(?m)^status:\s*(\S+)') { $Matches[1].Trim() } else { '' }
    if ($DraftOnly -and $status -eq 'final') { $skippedFinal++; continue }

    # source_count comes from the body's "- Source" line (the house convention,
    # written with or without a colon).
    $srcCount = 0
    if ($body -match '(?m)^-\s*Source:?(.*)$') {
        $srcCount = ([regex]::Matches($Matches[1], '\[\[[^\]]+\]\]')).Count
    }
    $trust = Get-Trust -SourceCount $srcCount -Status $status
    $dist["$trust"] = 1 + ($dist["$trust"] | ForEach-Object { $_ })

    $newFm = $fm

    # 1. drop the retired key (whole line, including its newline)
    $newFm = $newFm -replace '(?m)^reviewed:.*\r?\n?', ''

    # 2. upsert source_count and trust, keeping them next to `flashcards`
    if ($newFm -match '(?m)^source_count:') {
        $newFm = $newFm -replace '(?m)^source_count:.*$', "source_count: $srcCount"
    } else {
        $newFm = $newFm -replace '(?m)^(flashcards:.*)$', "`$1`nsource_count: $srcCount"
    }
    if ($newFm -match '(?m)^trust:') {
        $newFm = $newFm -replace '(?m)^trust:.*$', "trust: $trust"
    } else {
        $newFm = $newFm -replace '(?m)^(source_count:.*)$', "`$1`ntrust: $trust"
    }

    if ($newFm -eq $fm) { $unchanged++; continue }

    $changed++
    if ($Apply) {
        $out = "---`n" + $newFm + "`n---`n" + $body
        Set-Content -LiteralPath $f.FullName -Value $out -Encoding UTF8 -NoNewline
    }
}

$mode = if ($Apply) { 'APPLIED' } else { 'DRY RUN - nothing written (use -Apply)' }
Write-Host ""
Write-Host "concept_schema_sync - $mode"
Write-Host ("-" * 60)
Write-Host ("  notes scanned      : {0}" -f $files.Count)
Write-Host ("  would change/changed: {0}" -f $changed)
Write-Host ("  already current    : {0}" -f $unchanged)
if ($DraftOnly) { Write-Host ("  skipped (final)    : {0}" -f $skippedFinal) }
if ($malformed.Count) {
    Write-Host ("  MALFORMED frontmatter (skipped): {0}" -f $malformed.Count) -ForegroundColor Yellow
    $malformed | Select-Object -First 10 | ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "  trust distribution:"
$dist.GetEnumerator() | Sort-Object { [double]$_.Key } | ForEach-Object {
    Write-Host ("    {0,5}  {1}" -f $_.Key, $_.Value)
}
Write-Host ""
if (-not $Apply) { Write-Host "  Re-run with -Apply to write. Then: python generate_index.py" }
