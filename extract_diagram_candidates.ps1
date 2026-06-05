# extract_diagram_candidates.ps1
# Builds the per-MOC diagram manifest consumed by the visualise-moc agent.
#
# Reads VAULT_INDEX.json and the target MOC file. Parses the cluster
# structure (### Cluster N subsections under ## Concept Landscape) and the
# typed edges (### Supports / ### Contradicts / ### Prerequisite-for /
# ### Mechanism-of / ### Instance-of / ### Mitigates / ### Related-to under
# ## Concept Relationships). Writes DIAGRAM_CANDIDATES_{moc_stem}.json.
#
# The agent then reads ONLY the manifest in PHASE V-1, never the MOC or any
# concept note - this is the context-window discipline.

param(
    [Parameter(Mandatory=$true)]
    [string]$MocStem,
    [string]$VaultRoot = $(if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else { (Get-Location).Path })
)

$indexPath  = Join-Path $VaultRoot "00_Inbox\VAULT_INDEX.json"
$mocsFolder = Join-Path $VaultRoot "20_Learning\22_Maps of Content"
$mocPath    = Join-Path $mocsFolder ($MocStem + ".md")
$outPath    = Join-Path $VaultRoot ("00_Inbox\DIAGRAM_CANDIDATES_" + $MocStem + ".json")

if (-not (Test-Path $indexPath)) {
    Write-Error "VAULT_INDEX.json not found at $indexPath - run generate_index.py first."
    exit 1
}
if (-not (Test-Path $mocPath)) {
    Write-Error "MOC file not found at $mocPath."
    exit 1
}

$index = Get-Content $indexPath -Raw -Encoding UTF8 | ConvertFrom-Json
$today = Get-Date -Format "yyyy-MM-dd"

# --- Closed edge vocabulary (mirrors docs/visualisation-pipeline.md) -----

$EdgeClass = @{
    "supports"          = "horizontal"
    "contradicts"       = "horizontal"
    "mitigates"         = "horizontal"
    "related-to"        = "horizontal"
    "prerequisite-for"  = "vertical"
    "mechanism-of"      = "vertical"
    "instance-of"       = "vertical"
}

# Map of "## Concept Relationships" subsection headers (case-insensitive)
# to the canonical edge label. Allow both forms the inbox-pipeline.md
# spec might emit (Supports vs supports, Prerequisite-for vs prerequisite-for).
$HeaderToLabel = @{
    "supports"         = "supports"
    "contradicts"      = "contradicts"
    "prerequisite-for" = "prerequisite-for"
    "prerequisite for" = "prerequisite-for"
    "mechanism-of"     = "mechanism-of"
    "mechanism of"     = "mechanism-of"
    "instance-of"      = "instance-of"
    "instance of"      = "instance-of"
    "mitigates"        = "mitigates"
    "related-to"       = "related-to"
    "related to"       = "related-to"
}

# --- Read MOC file ------------------------------------------------------

$bytes = [System.IO.File]::ReadAllBytes($mocPath)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.StartsWith([char]0xFEFF)) { $content = $content.Substring(1) }

# Frontmatter scraping (regex; YAML parse is overkill here)
$mocTitle = $null
if ($content -match '(?m)^title:\s*"?(.+?)"?\s*$') { $mocTitle = $matches[1].Trim() }

$humanizedMoc = ($MocStem -replace '^MOC_', '') -replace '_', ' '

$noteCount = $null
if ($content -match '(?m)^note_count:\s*(\d+)') { $noteCount = [int]$matches[1] }

# Core Question = first paragraph of ## Core Question section
$coreQuestion = $null
$cqMatch = [regex]::Match($content, '(?ms)^##\s*Core Question\s*\n(.+?)(?=\n##\s|\Z)')
if ($cqMatch.Success) {
    $coreQuestion = ($cqMatch.Groups[1].Value -replace '\s+', ' ').Trim()
}

# --- Build the index lookup: stem -> { title, description } -------------

$NoteByStem = @{}
foreach ($n in $index.notes) {
    if ($n.stem) { $NoteByStem[$n.stem] = $n }
}

# --- Helpers ------------------------------------------------------------

function To-CamelCase {
    # Convert a stem or cluster name to camelCase: first word lowercase,
    # rest capitalised, non-alphanumeric stripped.
    param([string]$s)
    if (-not $s) { return "" }
    # Split on anything non-alphanumeric. Force array context with @() so
    # single-word inputs ("Storage") don't collapse to a scalar string whose
    # [0] indexer would return a [char] (which has no ToLower method).
    $parts = @([regex]::Split($s, '[^A-Za-z0-9]+') | Where-Object { $_ -ne "" })
    if ($parts.Count -eq 0) { return "" }
    $first = ([string]$parts[0]).ToLower()
    $rest = @()
    for ($i = 1; $i -lt $parts.Count; $i++) {
        $w = [string]$parts[$i]
        if ($w.Length -eq 0) { continue }
        $rest += ($w.Substring(0,1).ToUpper() + $w.Substring(1).ToLower())
    }
    $id = $first + ($rest -join "")
    # Mermaid IDs cannot start with a digit
    if ($id -match '^[0-9]') { $id = "n" + $id }
    return $id
}

function Extract-ClusterMemberStems {
    # For cluster parsing: return only the FIRST [[stem]] of each bullet
    # line (lines starting with optional whitespace + "-"). This avoids
    # picking up wikilinks embedded in descriptions ("stub pointing to
    # [[Cluster_Processing]]") and treating them as cluster members.
    # Skips source-file links ([[some-file.pdf]]). Deduplicates while
    # preserving encounter order.
    param([string]$text)
    $stems = @()
    $seen = @{}
    foreach ($line in $text -split "(\r\n|\n|\r)") {
        if ($line -notmatch '^\s*-\s') { continue }
        $m = [regex]::Match($line, '\[\[([^\]\|]+?)(?:\|[^\]]+?)?\]\]')
        if (-not $m.Success) { continue }
        $s = $m.Groups[1].Value.Trim()
        if ($s -eq "") { continue }
        if ($s -match '\.(pdf|md|epub|docx)$') { continue }
        if ($seen.ContainsKey($s)) { continue }
        $seen[$s] = $true
        $stems += $s
    }
    return $stems
}

# --- Parse cluster structure --------------------------------------------
#
# Layout under ## Concept Landscape:
#   ### Cluster Map           (legacy SVG, ignored here)
#   ### {Cluster Display 1}
#   - [[Stem_A]] - one-liner
#   - [[Stem_B]] - one-liner
#   ### {Cluster Display 2}
#   ...
#
# Find the ## Concept Landscape section, then split it on ### headings.
# Drop the "Cluster Map" heading; treat every other ### as a cluster.

$clusters = @()
$conceptToCluster = @{}

$landscapeMatch = [regex]::Match($content, '(?ms)^##\s*Concept Landscape\s*\n(.+?)(?=\n##\s|\Z)')
if ($landscapeMatch.Success) {
    $landscape = $landscapeMatch.Groups[1].Value

    # Split on ### headings, keep the heading text
    $h3Matches = [regex]::Matches($landscape, '(?ms)^###\s*(.+?)\s*\n(.+?)(?=\n###\s|\Z)')
    $idsSeen = @{}
    foreach ($h in $h3Matches) {
        $heading = $h.Groups[1].Value.Trim()
        $body    = $h.Groups[2].Value

        # Skip the auto-generated cluster map subsection
        if ($heading -match '^(?i)Cluster Map$') { continue }

        # Cluster ID = camelCase of the heading text before any " - " separator
        $shortHeading = $heading
        $dashIdx = $heading.IndexOf(" - ")
        if ($dashIdx -gt 0) { $shortHeading = $heading.Substring(0, $dashIdx) }
        $clusterId = To-CamelCase $shortHeading

        # Guarantee uniqueness within this MOC
        $baseId = $clusterId
        $suffix = 2
        while ($idsSeen.ContainsKey($clusterId)) {
            $clusterId = $baseId + $suffix
            $suffix++
        }
        $idsSeen[$clusterId] = $true

        # Enumerate concepts in this cluster: only the first wikilink of
        # each bullet line counts. First-assignment-wins for
        # conceptToCluster (a concept legitimately listed in two clusters
        # by the curator binds to the first one for same_cluster
        # purposes — explicit and predictable).
        $concepts = @()
        foreach ($stem in (Extract-ClusterMemberStems $body)) {
            $n = $NoteByStem[$stem]
            $title = if ($n) { $n.title } else { $stem }
            $description = if ($n) { $n.description } else { $null }
            $concepts += [PSCustomObject]@{
                stem        = $stem
                title       = $title
                description = $description
            }
            if (-not $conceptToCluster.ContainsKey($stem)) {
                $conceptToCluster[$stem] = $clusterId
            }
        }

        $clusters += [PSCustomObject]@{
            cluster_id      = $clusterId
            cluster_display = $heading
            concepts        = $concepts
        }
    }
}

# --- Parse typed edges from ## Concept Relationships --------------------
#
# Today: only ### Supports / ### Contradicts subsections exist.
# After widening: subsection per typed label.

$edges = @()
$unknownLabels = @{}

$relMatch = [regex]::Match($content, '(?ms)^##\s*Concept Relationships\s*\n(.+?)(?=\n##\s|\Z)')
if ($relMatch.Success) {
    $relBlock = $relMatch.Groups[1].Value

    $relH3 = [regex]::Matches($relBlock, '(?ms)^###\s*(.+?)\s*\n(.+?)(?=\n###\s|\Z)')
    foreach ($h in $relH3) {
        $headerRaw = $h.Groups[1].Value.Trim().ToLower()
        $body      = $h.Groups[2].Value

        if (-not $HeaderToLabel.ContainsKey($headerRaw)) {
            # Unknown subsection - track it; agent will STOP and ask.
            $unknownLabels[$headerRaw] = $true
            continue
        }
        $label = $HeaderToLabel[$headerRaw]
        $class = $EdgeClass[$label]

        # Each edge line is roughly "- [[A]] {label} [[B]]"
        foreach ($lineMatch in [regex]::Matches($body, '(?m)^[-\s]*\[\[([^\]\|]+?)\]\]\s*[^\[]*?\[\[([^\]\|]+?)\]\]')) {
            $src = $lineMatch.Groups[1].Value.Trim()
            $tgt = $lineMatch.Groups[2].Value.Trim()
            if (-not $src -or -not $tgt) { continue }

            $sameCluster = $false
            if ($conceptToCluster.ContainsKey($src) -and $conceptToCluster.ContainsKey($tgt)) {
                $sameCluster = ($conceptToCluster[$src] -eq $conceptToCluster[$tgt])
            }

            $edges += [PSCustomObject]@{
                source_stem   = $src
                target_stem   = $tgt
                label         = $label
                class         = $class
                same_cluster  = $sameCluster
            }
        }
    }
}

# --- Assemble manifest --------------------------------------------------

$manifest = [PSCustomObject]@{
    generated            = $today
    moc_stem             = $MocStem
    moc_title            = $mocTitle
    moc_core_question    = $coreQuestion
    humanized_moc        = $humanizedMoc
    note_count           = $noteCount
    clusters             = $clusters
    edges                = $edges
    unknown_edge_labels  = @($unknownLabels.Keys)
}

$json = $manifest | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($outPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Diagram manifest written: $outPath" -ForegroundColor Green
Write-Host ("  Clusters: {0}" -f $clusters.Count)
$conceptTotal = 0
foreach ($c in $clusters) { $conceptTotal += $c.concepts.Count }
Write-Host ("  Concepts (across clusters): {0}" -f $conceptTotal)
Write-Host ("  Edges (typed): {0}" -f $edges.Count)
if ($unknownLabels.Count -gt 0) {
    Write-Host ("  ⚠ Unknown edge labels: {0}" -f (($unknownLabels.Keys) -join ", ")) -ForegroundColor Yellow
}
