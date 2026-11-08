# build_diagrams.ps1
# Deterministic diagram generator for the visualise-moc pipeline.
#
# Reads the per-MOC manifest (DIAGRAM_CANDIDATES_{stem}.json, built by
# extract_diagram_candidates.ps1) and emits every Mermaid (.mmd) file, renders
# each to SVG via mmdc, runs a readability gate (vertical-aspect check),
# computes a comfortable Obsidian display width, and writes the SVG-only
# diagram file plus a render-plan JSON.
#
# This replaces the LLM agent's hand-authoring of Mermaid (old PHASE V-3/V-4):
# the layout is now a pure function of (manifest + ICON_MAP), so re-runs are
# byte-stable. The agent is no longer in the mechanical path.
#
# Layout rules (ported verbatim from the rules we settled on):
#   - node label  = "{icon} {short or title}"   (icon/short from manifest)
#   - contains    -> nested subgraph (not an arrow)
#   - other edges -> arrows (==> mitigates/flows-into/protects, <--> peers-with,
#                    -.-> contradicts, --> everything else)
#   - every sibling group (top-level, or children of one container) with >=2
#     members gets an invisible `~~~` backbone so it stacks VERTICALLY; a
#     backbone link is skipped when that exact pair already has a real edge.
#   - overview is flowchart TB: one stadium per rendered cluster, cross-cluster
#     edges drawn, the rest stacked by an invisible backbone.

param(
    [Parameter(Mandatory = $true)] [string] $MocStem,
    [string] $VaultRoot   = $(if ($env:VAULT_ROOT) { $env:VAULT_ROOT } else { Split-Path -Parent $MyInvocation.MyCommand.Path }),
    [int]    $Cap         = 9,      # max concepts rendered per cluster
    [int]    $ClusterCap  = 0,      # max CLUSTERS rendered per MOC; 0 = every cluster
    [int]    $DisplayWidth = 690,   # Obsidian embed width (|NNN) for every SVG
    [double] $AspectWarn  = 1.30    # w/h above this is flagged as too wide
)

$ErrorActionPreference = "Continue"   # mmdc writes to stderr on success; Stop would treat that as fatal in PS 5.1
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$utf8 = New-Object System.Text.UTF8Encoding($false)
$infoMark = [char]0x24D8   # circled-i, built at runtime to keep this source ASCII-only

$manifestPath = Join-Path $VaultRoot ("00_Inbox\DIAGRAM_CANDIDATES_" + $MocStem + ".json")
$buildDir     = Join-Path $VaultRoot ("00_Inbox\DIAGRAM_BUILD\" + $MocStem)
$diagramFile  = Join-Path $VaultRoot ("20_Learning\24_Diagrams\Diagram_" + $MocStem + ".md")
$planPath     = Join-Path $VaultRoot "00_Inbox\DIAGRAM_RENDER_PLAN.json"
$modePath     = Join-Path $VaultRoot "00_Inbox\MMDC_MODE.txt"

if (-not (Test-Path $manifestPath)) { Write-Error "Manifest not found: $manifestPath"; exit 1 }
if (-not (Test-Path $buildDir)) { New-Item -ItemType Directory -Path $buildDir -Force | Out-Null }

$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$mmdcMode = if (Test-Path $modePath) { (Get-Content $modePath -Raw).Trim() } else { "global" }

# Mermaid config: htmlLabels:false renders labels as native SVG <text> instead
# of <foreignObject> HTML. foreignObject does NOT render when an SVG is embedded
# as an <img> (which is how Obsidian shows ![](x.svg)), so labels + their emoji
# would silently disappear. <text> renders reliably as an image.
$mmConfigPath = Join-Path $buildDir "_mmdc_config.json"
# htmlLabels:false must be set at BOTH the top level AND under flowchart -
# flowchart.htmlLabels alone is not honoured (verified empirically).
[System.IO.File]::WriteAllText($mmConfigPath, '{"htmlLabels":false,"flowchart":{"htmlLabels":false}}', $utf8)

# ---- cluster palette (hardcoded, same six as the legacy map) ------------
$palette = @(
    "fill:#EEEDFE,stroke:#534AB7,color:#3C3489",
    "fill:#E1F5EE,stroke:#0F6E56,color:#085041",
    "fill:#FAECE7,stroke:#993C1D,color:#712B13",
    "fill:#FAEEDA,stroke:#854F0B,color:#633806",
    "fill:#E6F1FB,stroke:#185FA5,color:#0C447C",
    "fill:#FBEAF0,stroke:#993556,color:#72243E"
)

# ---- helpers -----------------------------------------------------------

function To-CamelCase {
    param([string]$s)
    if (-not $s) { return "" }
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
    if ($id -match '^[0-9]') { $id = "n" + $id }
    return $id
}

function Esc-Label {
    param([string]$s)
    if (-not $s) { return "" }
    $s = $s -replace '\|', '/'
    $s = $s -replace '\s*&\s*', ' and '
    $s = $s -replace '[#<>\[\]`\\]', ''
    $s = $s -replace '"', "'"
    $s = $s -replace '\s{2,}', ' '
    return $s.Trim()
}

function Trunc-Display {
    # Truncate a cluster heading at the first dash separator (hyphen, em, or en
    # dash with surrounding spaces). Mirrors the extractor's cluster_id logic.
    param([string]$s)
    if (-not $s) { return "" }
    $best = $s.Length
    foreach ($sep in @(" - ", (" " + [char]0x2014 + " "), (" " + [char]0x2013 + " "))) {
        $ix = $s.IndexOf($sep)
        if ($ix -ge 0 -and $ix -lt $best) { $best = $ix }
    }
    if ($best -lt $s.Length) { return $s.Substring(0, $best).Trim() }
    return $s.Trim()
}

function Arrow-For {
    param([string]$label)
    switch ($label) {
        "contradicts" { return "-.->" }
        "mitigates"   { return "==>" }
        "flows-into"  { return "==>" }
        "protects"    { return "==>" }
        "peers-with"  { return "<-->" }
        default       { return "-->" }
    }
}

# ---- per-cluster Mermaid builder ---------------------------------------

function Build-Cluster {
    param($cluster, $classIdx)

    $cid    = $cluster.cluster_id
    $display = Trunc-Display $cluster.cluster_display
    $cicon = $cluster.cluster_icon
    $clusterLabel = if ($cicon) { "$cicon " + (Esc-Label $display) } else { (Esc-Label $display) }
    $cls = "c$($classIdx)"

    $concepts = @($cluster.concepts)
    $stems = @($concepts | ForEach-Object { $_.stem })

    # same-cluster edges only
    $edges = @($manifest.edges | Where-Object { $_.same_cluster -and ($stems -contains $_.source_stem) -and ($stems -contains $_.target_stem) })

    # degree per stem: structural (typed, non-related-to) weighted above total,
    # so architecturally-connected nodes outrank acronym stubs that only carry
    # weak related-to links.
    $sdeg = @{}; $tdeg = @{}
    foreach ($s in $stems) { $sdeg[$s] = 0; $tdeg[$s] = 0 }
    foreach ($e in $edges) {
        $tdeg[$e.source_stem]++; $tdeg[$e.target_stem]++
        if ($e.label -ne "related-to") { $sdeg[$e.source_stem]++; $sdeg[$e.target_stem]++ }
    }

    # selection: structural degree, then total degree, then manifest order, cap
    $order = @{}
    for ($i = 0; $i -lt $stems.Count; $i++) { $order[$stems[$i]] = $i }
    $ranked = $stems | Sort-Object @{ Expression = { -$sdeg[$_] } }, @{ Expression = { -$tdeg[$_] } }, @{ Expression = { $order[$_] } }
    $selected = @($ranked | Select-Object -First $Cap)
    # keep contained partners together: if a contains-child is in, ensure parent in (and vice versa)
    $containsEdges = @($edges | Where-Object { $_.label -eq "contains" })
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($ce in $containsEdges) {
            if (($selected -contains $ce.source_stem) -and (-not ($selected -contains $ce.target_stem))) { $selected += $ce.target_stem; $changed = $true }
            if (($selected -contains $ce.target_stem) -and (-not ($selected -contains $ce.source_stem))) { $selected += $ce.source_stem; $changed = $true }
        }
    }
    $selected = @($selected | Select-Object -Unique)
    $omitted = @($stems | Where-Object { $selected -notcontains $_ })

    # only keep edges whose both endpoints survived
    $edges = @($edges | Where-Object { ($selected -contains $_.source_stem) -and ($selected -contains $_.target_stem) })
    $containsEdges = @($edges | Where-Object { $_.label -eq "contains" })
    $realEdges = @($edges | Where-Object { $_.label -ne "contains" })

    # transitive containment ancestry (child -> {all ancestors})
    $ancestors = @{}
    foreach ($s in $selected) { $ancestors[$s] = @{} }
    $chg = $true
    while ($chg) {
        $chg = $false
        foreach ($ce in $containsEdges) {
            $child = $ce.target_stem; $par = $ce.source_stem
            if (-not $ancestors[$child].ContainsKey($par)) { $ancestors[$child][$par] = $true; $chg = $true }
            foreach ($a in @($ancestors[$par].Keys)) {
                if (-not $ancestors[$child].ContainsKey($a)) { $ancestors[$child][$a] = $true; $chg = $true }
            }
        }
    }
    # Drop real edges between an ancestor and its descendant: the nesting already
    # expresses that relation, and a container->descendant edge crashes dagre
    # ("Cannot set properties of undefined (setting 'rank')").
    $realEdges = @($realEdges | Where-Object {
        $s = $_.source_stem; $t = $_.target_stem
        -not ($ancestors[$t].ContainsKey($s) -or $ancestors[$s].ContainsKey($t))
    })

    # lookup: stem -> concept
    $byStem = @{}
    foreach ($c in $concepts) { $byStem[$c.stem] = $c }

    # containment: child -> parent ; parent -> [children]
    $parentOf = @{}
    $childrenOf = @{}
    foreach ($ce in $containsEdges) {
        $parentOf[$ce.target_stem] = $ce.source_stem
        if (-not $childrenOf.ContainsKey($ce.source_stem)) { $childrenOf[$ce.source_stem] = @() }
        $childrenOf[$ce.source_stem] += $ce.target_stem
    }

    # Retarget edges that point INTO a nested node to that node's TOP-LEVEL
    # container box. dagre crashes ("setting 'rank'") on multiple edges into a
    # deeply-nested subgraph; pointing at the outermost container is safe and
    # visually equivalent (the box contains the nested target anyway).
    $rt = @(); $seenE = @{}
    foreach ($e in $realEdges) {
        $s = $e.source_stem; while ($parentOf.ContainsKey($s)) { $s = $parentOf[$s] }
        $t = $e.target_stem; while ($parentOf.ContainsKey($t)) { $t = $parentOf[$t] }
        if ($s -eq $t) { continue }
        $k = "$s|$($e.label)|$t"
        if ($seenE.ContainsKey($k)) { continue }
        $seenE[$k] = $true
        $rt += [PSCustomObject]@{ source_stem = $s; target_stem = $t; label = $e.label }
    }
    $realEdges = $rt

    # So-What prune: drop a weak edge (supports/contradicts/related-to) on a pair
    # that already has a STRUCTURAL edge - the structural one carries the meaning
    # and the duplicate just clutters/widens the cluster.
    $structuralSet = @{ "contains"=1;"flows-into"=1;"inherits-to"=1;"peers-with"=1;"protects"=1;"instance-of"=1;"prerequisite-for"=1;"mechanism-of"=1;"mitigates"=1 }
    $structPair = @{}
    foreach ($e in $realEdges) {
        if ($structuralSet.ContainsKey($e.label)) {
            $structPair["$($e.source_stem)|$($e.target_stem)"] = $true
            $structPair["$($e.target_stem)|$($e.source_stem)"] = $true
        }
    }
    $realEdges = @($realEdges | Where-Object {
        $weak = ($_.label -eq "supports" -or $_.label -eq "contradicts" -or $_.label -eq "related-to")
        -not ($weak -and $structPair.ContainsKey("$($_.source_stem)|$($_.target_stem)"))
    })

    # real-edge pair set (unordered) to skip backbone duplicates
    $realPair = @{}
    foreach ($e in $realEdges) {
        $k1 = "$($e.source_stem)|$($e.target_stem)"; $k2 = "$($e.target_stem)|$($e.source_stem)"
        $realPair[$k1] = $true; $realPair[$k2] = $true
    }

    $nodeId = @{}
    foreach ($s in $selected) { $nodeId[$s] = (To-CamelCase $s) }

    $lines = New-Object System.Collections.Generic.List[string]
    $classLines = New-Object System.Collections.Generic.List[string]

    function Node-Label($stem) {
        $c = $byStem[$stem]
        $txt = if ($c.short) { $c.short } else { $c.title }
        $txt = Esc-Label $txt
        if ($c.icon) { return "$($c.icon) $txt" } else { return $txt }
    }

    # recursive emitter for a sibling list at indent depth
    function Emit-Siblings {
        param([string[]]$sibs, [int]$depth)
        $pad = "    " * $depth
        # stable order: by manifest order
        $sibs = @($sibs | Sort-Object @{ Expression = { $order[$_] } })
        foreach ($s in $sibs) {
            $id = $nodeId[$s]
            $classLines.Add("    class $id $cls") | Out-Null
            if ($childrenOf.ContainsKey($s)) {
                $lines.Add("$pad" + "subgraph $id" + '["' + (Node-Label $s) + '"]') | Out-Null
                $lines.Add("$pad    direction TB") | Out-Null
                Emit-Siblings -sibs $childrenOf[$s] -depth ($depth + 1)
                $lines.Add("$pad" + "end") | Out-Null
            } else {
                $lines.Add("$pad$id" + '["' + (Node-Label $s) + '"]') | Out-Null
            }
        }
        # invisible backbone among these siblings - chain ALL consecutive pairs
        # (the ~~~ is invisible, so a real edge on the same pair is harmless and
        # they reinforce each other; skipping pairs drops nodes off the vertical
        # chain and widens the cluster).
        if ($sibs.Count -ge 2) {
            for ($i = 0; $i -lt $sibs.Count - 1; $i++) {
                $a = $sibs[$i]; $b = $sibs[$i+1]
                $lines.Add("$pad$($nodeId[$a]) ~~~ $($nodeId[$b])") | Out-Null
            }
        }
    }

    # top-level = selected nodes that are not contained
    $topLevel = @($selected | Where-Object { -not $parentOf.ContainsKey($_) })

    $mmd = New-Object System.Collections.Generic.List[string]
    $mmd.Add("flowchart TB") | Out-Null
    $mmd.Add("    classDef $cls $($palette[$classIdx % 6])") | Out-Null
    # wrapper id is prefixed so it can never collide with a concept node id
    # (node ids are pure camelCase, no underscore) - e.g. cluster "Microsoft
    # Sentinel" and concept "Microsoft_Sentinel" both camelCase to the same id.
    $mmd.Add('    subgraph cl_' + $cid + '["' + $clusterLabel + '"]') | Out-Null
    $mmd.Add("        direction TB") | Out-Null
    # nodes + nested + backbone (depth 2 -> inside the cluster subgraph)
    $script:lines = $lines
    Emit-Siblings -sibs $topLevel -depth 2
    foreach ($l in $lines) { $mmd.Add($l) | Out-Null }
    # real edges (drawn after the cluster subgraph close so cross-boundary works)
    $mmd.Add("    end") | Out-Null
    foreach ($e in $realEdges) {
        $arr = Arrow-For $e.label
        $mmd.Add("    $($nodeId[$e.source_stem]) $arr|$($e.label)| $($nodeId[$e.target_stem])") | Out-Null
    }
    foreach ($cl in $classLines) { $mmd.Add($cl) | Out-Null }

    return [PSCustomObject]@{
        mmd       = ($mmd -join "`n") + "`n"
        selected  = $selected.Count
        total     = $stems.Count
        omitted   = @($omitted | ForEach-Object { $b = $byStem[$_]; if ($b.short) { $b.short } else { $b.title } })
        edges     = $realEdges.Count + $containsEdges.Count
    }
}

# ---- overview builder --------------------------------------------------

function Build-Overview {
    param($renderedClusters)

    # concept -> cluster_id
    $clusterOf = @{}
    foreach ($cl in $manifest.clusters) {
        foreach ($c in $cl.concepts) { $clusterOf[$c.stem] = $cl.cluster_id }
    }
    $clById = @{}
    foreach ($cl in $manifest.clusters) { $clById[$cl.cluster_id] = $cl }

    # cross-cluster edges between rendered clusters: strongest per pair
    $priority = @{ "contains"=12;"flows-into"=11;"inherits-to"=10;"contradicts"=9;"prerequisite-for"=8;"mechanism-of"=7;"protects"=6;"peers-with"=5;"supports"=4;"mitigates"=3;"instance-of"=2;"related-to"=1 }
    $pairLabel = @{}
    foreach ($e in $manifest.edges) {
        if ($e.same_cluster) { continue }
        $cs = $clusterOf[$e.source_stem]; $ct = $clusterOf[$e.target_stem]
        if (-not $cs -or -not $ct) { continue }
        if ($cs -eq $ct) { continue }
        if (($renderedClusters -notcontains $cs) -or ($renderedClusters -notcontains $ct)) { continue }
        $key = "$cs|$ct"
        $p = $priority[$e.label]
        if ((-not $pairLabel.ContainsKey($key)) -or ($p -gt $pairLabel[$key].p)) {
            $pairLabel[$key] = [PSCustomObject]@{ src=$cs; tgt=$ct; label=$e.label; p=$p }
        }
    }

    $crossPairSet = @{}
    foreach ($v in $pairLabel.Values) { $crossPairSet["$($v.src)|$($v.tgt)"] = $true; $crossPairSet["$($v.tgt)|$($v.src)"] = $true }

    $mmd = New-Object System.Collections.Generic.List[string]
    $mmd.Add("flowchart TB") | Out-Null
    for ($i = 0; $i -lt 6; $i++) { $mmd.Add("    classDef c$i $($palette[$i])") | Out-Null }

    $idx = 0
    foreach ($cid in $renderedClusters) {
        $cl = $clById[$cid]
        if (-not $cl) { continue }
        $disp = Trunc-Display $cl.cluster_display
        $lbl = if ($cl.cluster_icon) { "$($cl.cluster_icon) " + (Esc-Label $disp) } else { (Esc-Label $disp) }
        $mmd.Add('    ' + $cid + '(["' + $lbl + '"])') | Out-Null
        $idx++
    }
    # cross-cluster edges
    foreach ($v in $pairLabel.Values) {
        $arr = Arrow-For $v.label
        $mmd.Add("    $($v.src) $arr|$($v.label)| $($v.tgt)") | Out-Null
    }
    # backbone over rendered clusters in order (chain all; ~~~ is invisible so a
    # cross-cluster edge on the same pair is harmless)
    for ($i = 0; $i -lt $renderedClusters.Count - 1; $i++) {
        $a = $renderedClusters[$i]; $b = $renderedClusters[$i+1]
        $mmd.Add("    $a ~~~ $b") | Out-Null
    }
    # class assignment
    $idx = 0
    foreach ($cid in $renderedClusters) {
        if (-not $clById[$cid]) { continue }
        $mmd.Add("    class $cid c$($idx % 6)") | Out-Null
        $idx++
    }
    return ($mmd -join "`n") + "`n"
}

# ---- render + measure --------------------------------------------------

function Render-Mmd {
    param([string]$mmdPath, [string]$svgPath)
    if (Test-Path $svgPath) { Remove-Item $svgPath -Force -ErrorAction SilentlyContinue }
    # Do NOT redirect native stderr (PS 5.1 wraps it as a terminating error). Out-Null only on stdout.
    try {
        if ($mmdcMode -eq "npx") {
            & npx -y @mermaid-js/mermaid-cli -i $mmdPath -o $svgPath -c $mmConfigPath --quiet | Out-Null
        } else {
            & mmdc -i $mmdPath -o $svgPath -c $mmConfigPath --quiet | Out-Null
        }
    } catch { }
    if (-not (Test-Path $svgPath)) { return $null }
    $svg = Get-Content $svgPath -Raw -Encoding UTF8
    if ($svg -match 'viewBox="0 0 ([0-9.]+) ([0-9.]+)"') {
        return [PSCustomObject]@{ w = [double]$matches[1]; h = [double]$matches[2] }
    }
    return $null
}

# ---- MOC embed patcher (idempotent: width + caption) -------------------

function Patch-Moc {
    param($renderedClusters, $clusterMeta, $clById)
    $mocPath = Join-Path $VaultRoot ("20_Learning\22_Maps of Content\" + $MocStem + ".md")
    if (-not (Test-Path $mocPath)) { Write-Host "  (MOC not found; skipped MOC patch)" -ForegroundColor DarkYellow; return }
    $bytes = [System.IO.File]::ReadAllBytes($mocPath)
    $text = [System.Text.Encoding]::UTF8.GetString($bytes)
    # Ordinal char check; $text.StartsWith([char]0xFEFF) uses culture comparison
    # where U+FEFF is IGNORABLE -> always true -> strips a real char every run.
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) { $text = $text.Substring(1) }
    $lines = $text -split "`r`n|`n|`r"
    $esc = [regex]::Escape($MocStem)
    $renderedSet = @{}
    foreach ($cid in $renderedClusters) { $renderedSet[$cid] = $true }
    $ovEmbed = "![Overview - all clusters in this MOC|$DisplayWidth](../../00_Inbox/DIAGRAM_BUILD/$MocStem/overview.svg)"

    $out = New-Object System.Collections.Generic.List[string]
    $i = 0; $ovEmitted = $false; $ins = 0; $upd = 0
    while ($i -lt $lines.Count) {
        $line = $lines[$i]

        # existing overview embed -> update in place
        if ($line -match ('^!\[[^\]]*\]\(\.\./\.\./00_Inbox/DIAGRAM_BUILD/' + $esc + '/overview\.svg\)\s*$')) {
            $out.Add($ovEmbed) | Out-Null; $ovEmitted = $true; $upd++; $i++; continue
        }

        # cluster heading -> ensure exactly one embed (+caption) follows
        $hm = [regex]::Match($line, '^###\s+(.+?)\s*$')
        if ($hm.Success) {
            $cid = To-CamelCase (Trunc-Display $hm.Groups[1].Value)
            # the overview must sit before the first cluster heading
            if (-not $ovEmitted) { $out.Add($ovEmbed) | Out-Null; $out.Add("") | Out-Null; $ovEmitted = $true; $ins++ }
            $out.Add($line) | Out-Null
            if ($renderedSet.ContainsKey($cid)) {
                # consume following blanks + this cluster's old embed + caption
                $j = $i + 1; $had = $false
                while ($j -lt $lines.Count -and ($lines[$j].Trim() -eq "" -or ($lines[$j] -match ('cluster_' + [regex]::Escape($cid) + '\.svg')) -or $lines[$j].TrimStart().StartsWith(">"))) {
                    if ($lines[$j] -match 'cluster_') { $had = $true }
                    $j++
                }
                $cl = $clById[$cid]
                $disp = if ($cl) { Trunc-Display $cl.cluster_display } else { $cid }
                $out.Add("") | Out-Null
                $out.Add("![$disp|$DisplayWidth](../../00_Inbox/DIAGRAM_BUILD/$MocStem/cluster_$cid.svg)") | Out-Null
                $meta = $clusterMeta[$cid]
                if ($meta -and $meta.omitted.Count -gt 0) {
                    $out.Add("") | Out-Null
                    $out.Add("> $infoMark Diagram shows $($meta.selected) of $($meta.total) concepts. Also in this cluster: " + ($meta.omitted -join ", ") + ".") | Out-Null
                }
                $out.Add("") | Out-Null
                if ($had) { $upd++ } else { $ins++ }
                $i = $j; continue
            }
            $i++; continue
        }

        $out.Add($line) | Out-Null
        $i++
    }
    # Surgically refresh last_cluster_review to today — ONLY if the field
    # already exists in the MOC frontmatter (never insert it). Per
    # visualisation-pipeline.md V-5.3. The first match is the frontmatter line.
    $today = (Get-Date).ToString('yyyy-MM-dd')
    $lcrUpdated = $false
    for ($k = 0; $k -lt $out.Count; $k++) {
        if ($out[$k] -match '^\s*last_cluster_review:') {
            $out[$k] = "last_cluster_review: $today"
            $lcrUpdated = $true
            break
        }
    }
    [System.IO.File]::WriteAllText($mocPath, ($out -join "`n"), $utf8)
    $lcrMsg = if ($lcrUpdated) { "; last_cluster_review -> $today" } else { "" }
    Write-Host ("  MOC patched: {0} updated, {1} inserted (width $DisplayWidth)$lcrMsg." -f $upd, $ins) -ForegroundColor Green
}

# ---- main --------------------------------------------------------------

$rendered = @($manifest.rendered_clusters)
$clusterOmitted = @()
if ($rendered.Count -eq 0) {
    # Default: EVERY cluster in the manifest, largest first.
    #
    # This was `Select-Object -First 6`, which silently dropped every cluster
    # past the sixth and chose the survivors by raw concept count - so which
    # cluster fell off a tie was decided by sort order, not by worth. Nothing
    # downstream said so: the render plan lists only what was built, so an
    # omitted cluster looked identical to one that never existed. Caught when
    # MOC_Azure_Data_Platform (7 clusters, sizes 5,4,5,4,5,5,4) quietly lost
    # streamAndBatchArchitectures - a DP-900 exam objective - to a 3-way tie.
    # A cap is still available via -ClusterCap, but it is opt-in and it
    # ANNOUNCES what it dropped, here and in the render plan.
    $ordered = @($manifest.clusters | Sort-Object @{ Expression = { -$_.concepts.Count } } | ForEach-Object { $_.cluster_id })
    if ($ClusterCap -gt 0 -and $ordered.Count -gt $ClusterCap) {
        $rendered       = @($ordered | Select-Object -First $ClusterCap)
        $clusterOmitted = @($ordered | Select-Object -Skip  $ClusterCap)
    } else {
        $rendered = $ordered
    }
}

Write-Host "Generating diagrams for $MocStem ($($rendered.Count) of $(@($manifest.clusters).Count) clusters)..." -ForegroundColor Cyan
if ($clusterOmitted.Count -gt 0) {
    Write-Host ("  WARNING: -ClusterCap $ClusterCap omitted {0} cluster(s): {1}" -f $clusterOmitted.Count, ($clusterOmitted -join ", ")) -ForegroundColor Yellow
}

$planTiers = New-Object System.Collections.Generic.List[object]
$clById = @{}
foreach ($cl in $manifest.clusters) { $clById[$cl.cluster_id] = $cl }

# overview
$ovMmd = Build-Overview -renderedClusters $rendered
$ovMmdPath = Join-Path $buildDir "overview.mmd"
[System.IO.File]::WriteAllText($ovMmdPath, $ovMmd, $utf8)
$ovSvg = Join-Path $buildDir "overview.svg"
$ovDim = Render-Mmd -mmdPath $ovMmdPath -svgPath $ovSvg
$ovAspect = if ($ovDim) { [math]::Round($ovDim.w / $ovDim.h, 2) } else { $null }
$planTiers.Add([PSCustomObject]@{ tier="overview"; cluster=$null; nodes=$rendered.Count; aspect=$ovAspect; width=$DisplayWidth; status=$(if($ovDim){"rendered"}else{"failed"}) }) | Out-Null

# clusters
$classIdx = 0
$clusterMeta = @{}
foreach ($cid in $rendered) {
    $cl = $clById[$cid]
    if (-not $cl) { Write-Host "  - unknown cluster id '$cid' (skipped)" -ForegroundColor Yellow; continue }
    $res = Build-Cluster -cluster $cl -classIdx $classIdx
    $mmdPath = Join-Path $buildDir ("cluster_" + $cid + ".mmd")
    [System.IO.File]::WriteAllText($mmdPath, $res.mmd, $utf8)
    $svgPath = Join-Path $buildDir ("cluster_" + $cid + ".svg")
    $dim = Render-Mmd -mmdPath $mmdPath -svgPath $svgPath
    $aspect = if ($dim) { [math]::Round($dim.w / $dim.h, 2) } else { $null }
    $status = if (-not $dim) { "failed" } elseif ($aspect -gt $AspectWarn) { "wide" } else { "rendered" }
    $clusterMeta[$cid] = [PSCustomObject]@{ selected=$res.selected; total=$res.total; omitted=$res.omitted; aspect=$aspect }
    $planTiers.Add([PSCustomObject]@{ tier="detail"; cluster=$cid; nodes=$res.selected; total=$res.total; edges=$res.edges; aspect=$aspect; width=$DisplayWidth; omitted=$res.omitted; status=$status }) | Out-Null
    $flag = switch ($status) { "rendered" {"OK "} "wide" {"WIDE"} default {"FAIL"} }
    Write-Host ("  {0,-26} {1}  aspect {2}  {3}/{4} concepts" -f $cid, $flag, $aspect, $res.selected, $res.total)
    $classIdx++
}

# ---- write SVG-only diagram file --------------------------------------
$humanMoc = ($MocStem -replace '^MOC_','') -replace '_',' '
$today = Get-Date -Format "yyyy-MM-dd"
$df = New-Object System.Collections.Generic.List[string]
$df.Add("---") | Out-Null
$df.Add("title: $humanMoc - Visual Cram Sheet") | Out-Null
$df.Add("type: diagram") | Out-Null
$df.Add("moc: [$MocStem]") | Out-Null
$df.Add("created: $today") | Out-Null
$df.Add("updated: $today") | Out-Null
$df.Add("generator: build_diagrams.ps1") | Out-Null
$df.Add("tags:") | Out-Null
$df.Add("  - diagram") | Out-Null
$df.Add("  - cram-sheet") | Out-Null
$df.Add("---") | Out-Null
$df.Add("") | Out-Null
$df.Add("# $humanMoc - Visual Cram Sheet") | Out-Null
$df.Add("") | Out-Null
$df.Add("> Every diagram for [[$MocStem]] in one place, no prose - flip through for quick revision.") | Out-Null
$df.Add("> The MOC is the source of truth: edit its cluster structure / relationships there, then re-run launch-visualise-moc.ps1.") | Out-Null
$df.Add("") | Out-Null
$df.Add("*Auto-generated by build_diagrams.ps1 on $today - do not edit (regenerated each run). Mermaid sources in 00_Inbox/DIAGRAM_BUILD/$MocStem/; icons & short labels in 99_System/ICON_MAP.json.*") | Out-Null
$df.Add("") | Out-Null
$df.Add("## Overview") | Out-Null
$df.Add("") | Out-Null
$df.Add("![Overview - all rendered clusters|$DisplayWidth](../../00_Inbox/DIAGRAM_BUILD/$MocStem/overview.svg)") | Out-Null
$df.Add("") | Out-Null
$df.Add("## Cluster Detail") | Out-Null
$df.Add("") | Out-Null
foreach ($cid in $rendered) {
    $cl = $clById[$cid]; if (-not $cl) { continue }
    $disp = $cl.cluster_display; $d = $disp.IndexOf(" - "); if ($d -gt 0) { $disp = $disp.Substring(0,$d) }
    $icon = $cl.cluster_icon
    $head = if ($icon) { "### $icon $disp" } else { "### $disp" }
    $df.Add($head) | Out-Null
    $df.Add("") | Out-Null
    $df.Add("![$disp|$DisplayWidth](../../00_Inbox/DIAGRAM_BUILD/$MocStem/cluster_$cid.svg)") | Out-Null
    $meta = $clusterMeta[$cid]
    if ($meta -and $meta.omitted.Count -gt 0) {
        $df.Add("") | Out-Null
        $df.Add("> $infoMark Diagram shows $($meta.selected) of $($meta.total) concepts. Also in this cluster: " + ($meta.omitted -join ", ") + ".") | Out-Null
    }
    $df.Add("") | Out-Null
}
$dfText = ($df -join "`n")
[System.IO.File]::WriteAllText($diagramFile, $dfText, $utf8)

# ---- patch the MOC (overview + per-cluster embeds, widths, captions) ---
Patch-Moc -renderedClusters $rendered -clusterMeta $clusterMeta -clById $clById

# ---- render plan -------------------------------------------------------
$plan = [PSCustomObject]@{ generated=$today; moc_stem=$MocStem; display_width=$DisplayWidth; cap=$Cap; cluster_cap=$ClusterCap; clusters_total=@($manifest.clusters).Count; clusters_omitted=$clusterOmitted; tiers=$planTiers }
[System.IO.File]::WriteAllText($planPath, ($plan | ConvertTo-Json -Depth 8), $utf8)

Write-Host ""
Write-Host "Diagram file: $diagramFile" -ForegroundColor Green
Write-Host "Render plan : $planPath" -ForegroundColor Green
$wide = @($planTiers | Where-Object { $_.status -eq "wide" })
if ($wide.Count -gt 0) {
    Write-Host ("WIDE (aspect > {0}): {1}" -f $AspectWarn, (($wide | ForEach-Object { $_.cluster }) -join ", ")) -ForegroundColor Yellow
}

