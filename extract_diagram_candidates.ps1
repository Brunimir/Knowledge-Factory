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
    [string]$VaultRoot = $(if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else { Split-Path -Parent $MyInvocation.MyCommand.Path })
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
    # Structural family (added 2026-06-08) - see docs/visualisation-pipeline.md
    "contains"          = "vertical"
    "flows-into"        = "vertical"
    "inherits-to"       = "vertical"
    "peers-with"        = "horizontal"
    "protects"          = "horizontal"
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
    "contains"         = "contains"
    "flows-into"       = "flows-into"
    "flows into"       = "flows-into"
    "inherits-to"      = "inherits-to"
    "inherits to"      = "inherits-to"
    "peers-with"       = "peers-with"
    "peers with"       = "peers-with"
    "protects"         = "protects"
}

# --- Read MOC file ------------------------------------------------------

$bytes = [System.IO.File]::ReadAllBytes($mocPath)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.Length -gt 0 -and $content[0] -eq [char]0xFEFF) { $content = $content.Substring(1) }

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

# --- Load optional icon registry (99_System\ICON_MAP.json) --------------
# Concept stems / cluster_ids absent from the map render without an icon.
$IconByStem    = @{}
$IconByCluster = @{}
$ShortByStem   = @{}
$iconMapPath = Join-Path $VaultRoot "99_System\ICON_MAP.json"
if (Test-Path $iconMapPath) {
    try {
        $iconMap = Get-Content $iconMapPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($iconMap.concepts) {
            foreach ($p in $iconMap.concepts.PSObject.Properties) { $IconByStem[$p.Name] = $p.Value }
        }
        if ($iconMap.clusters) {
            foreach ($p in $iconMap.clusters.PSObject.Properties) { $IconByCluster[$p.Name] = $p.Value }
        }
        if ($iconMap.short) {
            foreach ($p in $iconMap.short.PSObject.Properties) { $ShortByStem[$p.Name] = $p.Value }
        }
    } catch {
        Write-Host "  ⚠ Could not parse ICON_MAP.json - rendering without icons/short labels." -ForegroundColor Yellow
    }
}

# --- Parse the optional rendered_clusters pin list from frontmatter -----
# A YAML inline list of camelCase cluster_ids the curator wants rendered,
# overriding the default top-6-by-note-count selection. Absent => default.
$renderedClusters = @()
if ($content -match '(?m)^rendered_clusters:\s*\[(.+?)\]') {
    $renderedClusters = @($matches[1] -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
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
        $dashIdx = -1
        foreach ($sepStr in @(" - ", (" " + [char]0x2014 + " "), (" " + [char]0x2013 + " "))) {
            $ix = $heading.IndexOf($sepStr)
            if ($ix -ge 0 -and ($dashIdx -lt 0 -or $ix -lt $dashIdx)) { $dashIdx = $ix }
        }
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
            $icon  = if ($IconByStem.ContainsKey($stem))  { $IconByStem[$stem] }  else { $null }
            $short = if ($ShortByStem.ContainsKey($stem)) { $ShortByStem[$stem] } else { $null }
            # Auto-derive a short label from a trailing parenthetical acronym
            # ("Network File System (NFS)" -> "NFS") when none is curated.
            if (-not $short -and $title -match '\(([^)]{1,12})\)\s*$') { $short = $matches[1].Trim() }
            $concepts += [PSCustomObject]@{
                stem        = $stem
                title       = $title
                description = $description
                icon        = $icon
                short       = $short
            }
            if (-not $conceptToCluster.ContainsKey($stem)) {
                $conceptToCluster[$stem] = $clusterId
            }
        }

        $clusterIcon = if ($IconByCluster.ContainsKey($clusterId)) { $IconByCluster[$clusterId] } else { $null }
        $clusters += [PSCustomObject]@{
            cluster_id      = $clusterId
            cluster_display = $heading
            cluster_icon    = $clusterIcon
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
    rendered_clusters    = $renderedClusters
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

# --- Icon/short coverage report for rendered clusters -------------------
# Flags concepts that WILL appear in a diagram but still lack an icon or short
# label, so the curator knows what to add to 99_System\ICON_MAP.json.
if ($renderedClusters.Count -gt 0) {
    $gapIcon  = @()
    $gapShort = @()
    foreach ($c in $clusters) {
        if ($renderedClusters -notcontains $c.cluster_id) { continue }
        foreach ($cn in $c.concepts) {
            if (-not $cn.icon)  { $gapIcon  += $cn.stem }
            if (-not $cn.short) { $gapShort += $cn.stem }
        }
    }
    if ($gapIcon.Count -gt 0 -or $gapShort.Count -gt 0) {
        Write-Host ""
        Write-Host "ICON_MAP coverage gaps (rendered clusters):" -ForegroundColor Yellow
        if ($gapIcon.Count -gt 0)  { Write-Host ("  no icon  ({0}): {1}" -f $gapIcon.Count,  ($gapIcon  -join ", ")) -ForegroundColor DarkYellow }
        if ($gapShort.Count -gt 0) { Write-Host ("  no short ({0}): {1}" -f $gapShort.Count, ($gapShort -join ", ")) -ForegroundColor DarkYellow }
    } else {
        Write-Host "ICON_MAP coverage: complete for all rendered clusters." -ForegroundColor Green
    }
}

# --- Structural connectedness gate -------------------------------------
# A cluster is "useful to learn" when its concepts are wired by STRUCTURAL
# edges (a backbone), not just supports/contradicts/related-to (an argument
# map) or nothing. Flag list-only clusters so the curator knows which need a
# connect_clusters pass.
$structuralLabels = @("contains","flows-into","inherits-to","peers-with","protects","instance-of","prerequisite-for","mechanism-of","mitigates")
$stemClusterC = @{}
foreach ($c in $clusters) { foreach ($cn in $c.concepts) { $stemClusterC[$cn.stem] = $c.cluster_id } }
$structCount = @{}
foreach ($c in $clusters) { $structCount[$c.cluster_id] = 0 }
foreach ($e in $edges) {
    $cs = $stemClusterC[$e.source_stem]; $ct = $stemClusterC[$e.target_stem]
    if ($cs -and ($cs -eq $ct) -and ($structuralLabels -contains $e.label)) { $structCount[$cs]++ }
}
$reportSet = if ($renderedClusters.Count -gt 0) { $renderedClusters } else { @($clusters | ForEach-Object { $_.cluster_id }) }
$listOnly = @()
foreach ($cid in $reportSet) {
    $cl = $clusters | Where-Object { $_.cluster_id -eq $cid } | Select-Object -First 1
    if (-not $cl) { continue }
    if ($structCount[$cid] -eq 0 -and $cl.concepts.Count -ge 2) { $listOnly += $cid }
}
Write-Host ""
if ($listOnly.Count -eq 0) {
    Write-Host "Structural connectedness: every rendered cluster has a backbone." -ForegroundColor Green
} else {
    Write-Host ("Structural connectedness: {0} list-only cluster(s) (no structural edges - just a list):" -f $listOnly.Count) -ForegroundColor Yellow
    foreach ($cid in $listOnly) {
        $cl = $clusters | Where-Object { $_.cluster_id -eq $cid } | Select-Object -First 1
        Write-Host ("  - {0} ({1} concepts)" -f $cid, $cl.concepts.Count) -ForegroundColor DarkYellow
    }
    Write-Host ("  -> draft edges:  .\connect_clusters.ps1 -MocStem {0}" -f $MocStem) -ForegroundColor DarkYellow
}

