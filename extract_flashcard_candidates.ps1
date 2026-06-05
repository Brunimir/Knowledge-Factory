# extract_flashcard_candidates.ps1
# One-shot extraction of all flashcard candidates from VAULT_INDEX.json.
# Reads source notes once each and outputs a single structured JSON manifest
# at 00_Inbox/FLASHCARD_CANDIDATES.json. The agent reads ONLY the manifest
# instead of opening 27+ source files individually.
#
# Eligibility: status:final AND reviewed:true AND flashcards:false

param(
    [string]$VaultRoot = $(if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else { (Get-Location).Path })
)

$indexPath      = Join-Path $VaultRoot "00_Inbox\VAULT_INDEX.json"
$conceptsFolder = Join-Path $VaultRoot "20_Learning\21_Concepts"
$outPath        = Join-Path $VaultRoot "00_Inbox\FLASHCARD_CANDIDATES.json"

if (-not (Test-Path $indexPath)) {
    Write-Error "VAULT_INDEX.json not found at $indexPath - run generate_index.py first."
    exit 1
}

$index = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
$today = Get-Date -Format "yyyy-MM-dd"

$eligible = @($index.notes | Where-Object {
    $_.status -eq "final" -and $_.reviewed -eq $true -and $_.flashcards -eq $false
})

Write-Host "Found $($eligible.Count) eligible candidates." -ForegroundColor Cyan

# --- Section extraction helpers ---

function Get-Section {
    # Returns the prose between '## <header>' and the next '##' (or end of file).
    param([string]$content, [string]$header)
    $pattern = '(?ms)^##\s*' + [regex]::Escape($header) + '\s*\n(.+?)(?=\n##\s|\Z)'
    $m = [regex]::Match($content, $pattern)
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

function Get-LabelValue {
    # Extracts the value after '**<label>:**' on the same line. Tolerates a leading bullet.
    param([string]$section, [string]$label)
    if (-not $section) { return $null }
    $pattern = '(?m)^[-\s]*\*\*' + [regex]::Escape($label) + ':\*\*\s*(.+?)\s*$'
    $m = [regex]::Match($section, $pattern)
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

function Get-MetaphorBlock {
    # Metaphor can span multiple lines; capture from '**Metaphor:**' until blank line or next bold-label or section end.
    param([string]$section)
    if (-not $section) { return $null }
    $pattern = '(?ms)\*\*Metaphor:\*\*\s*(.+?)(?=\n\s*\n|\n\s*\*\*[A-Z]|\Z)'
    $m = [regex]::Match($section, $pattern)
    if ($m.Success) {
        $val = $m.Groups[1].Value.Trim()
        # Strip residual ** markdown emphasis around inner phrases
        $val = $val -replace '\*\*', ''
        return $val
    }
    return $null
}

function Get-CoreProse {
    # Returns just the lead prose of the Core Idea section, before any '**Label:**' sub-blocks.
    param([string]$coreSection)
    if (-not $coreSection) { return $null }
    $m = [regex]::Match($coreSection, '(?s)^(.+?)(?:\n\s*\*\*[A-Z][a-zA-Z ]+:\*\*|\Z)')
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $coreSection.Trim()
}

# --- Per-candidate processing ---

$candidates = @()
$skipped = @()

foreach ($note in $eligible) {
    $stem = $note.stem
    $path = Join-Path $conceptsFolder ($stem + ".md")
    if (-not (Test-Path $path)) {
        $skipped += [PSCustomObject]@{ stem = $stem; reason = "source file not found" }
        continue
    }

    $bytes = [System.IO.File]::ReadAllBytes($path)
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($content.StartsWith([char]0xFEFF)) { $content = $content.Substring(1) }

    # Frontmatter fields
    $title = $null
    if ($content -match '(?m)^title:\s*"?(.+?)"?\s*$') { $title = $matches[1].Trim() }

    $description = $null
    if ($content -match '(?m)^description:\s*"?(.+?)"?\s*$') { $description = $matches[1].Trim() }

    # MOC from index (already a parsed array)
    $mocStem = $null
    if ($note.moc -is [array] -and $note.moc.Count -gt 0) {
        $mocStem = $note.moc[0]
    } elseif ($note.moc -is [string]) {
        $mocStem = $note.moc
    }
    $humanizedMoc = $null
    if ($mocStem) { $humanizedMoc = ($mocStem -replace '^MOC_', '') -replace '_', ' ' }

    # Sections
    $coreSection        = Get-Section -content $content -header 'Core Idea (Summary)'
    if (-not $coreSection) { $coreSection = Get-Section -content $content -header 'Core Idea' }
    $mechanismSection   = Get-Section -content $content -header 'Mechanism (Key details)'
    if (-not $mechanismSection) { $mechanismSection = Get-Section -content $content -header 'Mechanism' }
    $applicationSection = Get-Section -content $content -header 'Application'

    # Lead prose of core (without the **Metaphor:** / **Example:** / etc. sub-blocks)
    $coreProse = Get-CoreProse -coreSection $coreSection

    # Metaphor (multi-line capable)
    $metaphor = Get-MetaphorBlock -section $coreSection

    # Boundary condition - look in mechanism first, then application, then core
    $boundary = $null
    foreach ($sec in @($mechanismSection, $applicationSection, $coreSection)) {
        if ($sec) {
            $b = Get-LabelValue -section $sec -label 'Boundary condition'
            if ($b) { $boundary = $b; break }
        }
    }

    # When to use / When NOT to use - from application
    $whenTo  = Get-LabelValue -section $applicationSection -label 'When to use'
    $whenNot = Get-LabelValue -section $applicationSection -label 'When NOT to use'

    # Legacy label fallback (older notes)
    if (-not $whenTo)  { $whenTo  = Get-LabelValue -section $applicationSection -label 'Strengths' }
    if (-not $whenNot) {
        $whenNot = Get-LabelValue -section $applicationSection -label 'Opportunities'
        if (-not $whenNot) { $whenNot = Get-LabelValue -section $applicationSection -label 'Limitations' }
    }

    # Stub detection - signal only, don't auto-skip (user decides)
    $isStub     = $false
    $stubReason = $null
    if ($coreProse -and $coreProse -match '(?i)has been split into') {
        $isStub = $true; $stubReason = "core says 'has been split into'"
    } elseif ($description -and $description -match '(?i)navigation stub|^\s*stub|split into') {
        $isStub = $true; $stubReason = "description suggests stub"
    } elseif ($title -and $title -match '(?i)\(stub\)') {
        $isStub = $true; $stubReason = "title contains '(stub)'"
    }

    $hasRequired = ([bool]$title -and [bool]$mocStem -and [bool]$coreProse -and ([bool]$whenTo -or [bool]$whenNot))

    $candidates += [PSCustomObject]@{
        stem          = $stem
        title         = $title
        moc_stem      = $mocStem
        humanized_moc = $humanizedMoc
        description   = $description
        core          = $coreProse
        metaphor      = $metaphor
        mechanism     = $mechanismSection
        boundary      = $boundary
        when_to       = $whenTo
        when_not      = $whenNot
        is_stub       = $isStub
        stub_reason   = $stubReason
        has_required  = $hasRequired
    }
}

$manifest = [PSCustomObject]@{
    generated      = $today
    eligible_count = $candidates.Count
    skipped_count  = $skipped.Count
    candidates     = $candidates
    skipped        = $skipped
}

# Write JSON without BOM
$json = $manifest | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($outPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Manifest written: $outPath" -ForegroundColor Green
Write-Host "  Candidates: $($candidates.Count)"
Write-Host "  Skipped (file missing): $($skipped.Count)"

$stubs = @($candidates | Where-Object { $_.is_stub })
if ($stubs.Count -gt 0) {
    Write-Host "  Stubs flagged (agent will ask before processing): $($stubs.Count)" -ForegroundColor Yellow
    $stubs | ForEach-Object { Write-Host "    - $($_.stem): $($_.stub_reason)" }
}

$missingRequired = @($candidates | Where-Object { -not $_.has_required })
if ($missingRequired.Count -gt 0) {
    Write-Host "  Missing required fields (will be skipped): $($missingRequired.Count)" -ForegroundColor Yellow
    $missingRequired | ForEach-Object {
        $missing = @()
        if (-not $_.title)    { $missing += "title" }
        if (-not $_.moc_stem) { $missing += "moc" }
        if (-not $_.core)     { $missing += "core" }
        if (-not $_.when_to -and -not $_.when_not) { $missing += "when_to_or_not" }
        Write-Host "    - $($_.stem): missing $($missing -join ', ')"
    }
}
