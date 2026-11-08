# Visualisation Pipeline

This file contains the full PHASE V-0 through V-6 definitions for the
`visualise-moc` command. CLAUDE.md references this file rather than embedding
the content, so the agent only loads it when the user actually invokes
`visualise-moc`.

The general pipeline gates that apply to `visualise-moc` (BEFORE EVERY
visualise-moc RUN, SAFETY RULES, WINDOWS FILE OPERATION PATTERNS) remain in
CLAUDE.md — only the long phase definitions are here.

---

# ARCHITECTURE NOTE (2026-06-09): deterministic generator

The mechanical render — PHASE V-3 (build Mermaid), V-4 (mmdc), V-5 (write
diagram file + patch MOC) — is now done by a **deterministic script**,
`build_diagrams.ps1`, NOT by the LLM agent. The launcher calls it directly
after the extractor; the agent is no longer invoked on a normal run. This made
re-runs byte-stable, testable, and fast (the layout was the least reproducible
thing to leave to an LLM). The phase prose below is retained as the conceptual
spec the script implements. Pipeline now:

  launch-visualise-moc.ps1
    -> mmdc doctor (MMDC_MODE.txt)  -> generate_index.py  -> validate stem
    -> extract_diagram_candidates.ps1   (manifest: clusters, edges, icons,
                                         short labels, rendered_clusters)
    -> build_diagrams.ps1               (all .mmd -> SVG -> diagram file ->
                                         MOC patch -> DIAGRAM_RENDER_PLAN.json)

What `build_diagrams.ps1` enforces (the rules we settled on):
  - Label = "{icon} {short or title}" (icon/short from manifest/ICON_MAP).
    `short` is auto-derived from a trailing parenthetical acronym in the
    extractor when not curated ("... (NFS)" -> "NFS"); the extractor prints an
    ICON_MAP coverage report of remaining gaps in rendered clusters.
  - Selection: structural degree (typed, non-related-to edges) desc, then
    total degree, then manifest order; cap = 9 (param). Omitted concepts are
    listed in an "shows N of M" caption under the SVG (diagram file AND MOC).
  - `contains` -> nested subgraph. An edge whose endpoint is a nested node is
    RETARGETED to that node's top-level container box (dagre crashes —
    "setting 'rank'" — on multiple edges into a deeply-nested subgraph; the
    box visually contains the target anyway). Ancestor<->descendant real edges
    are dropped (the nesting already shows them).
  - Vertical layout: every sibling group (top-level or children of one
    container) gets an invisible `~~~` backbone so it stacks; a backbone link
    is skipped when that pair already has a real edge. flowchart TB everywhere,
    INCLUDING the overview (stadiums stacked by backbone, cross-cluster edges
    drawn on top). ELK layout was tested (2026-06-09) and REJECTED — it widens
    fans (1073x457 vs backbone 717x991), the opposite of what we need.
  - Rendering: mmdc runs with htmlLabels:false (config written to the build
    dir as _mmdc_config.json, top-level AND flowchart.htmlLabels both false) so
    labels are native SVG <text>, NOT <foreignObject> HTML. foreignObject does
    not render when the SVG is embedded as an <img> (Obsidian's ![](x.svg)) -
    with the default htmlLabels:true, every label and icon silently disappears.
  - Readability gate: each SVG's viewBox is measured; aspect (w/h) > 1.30 is
    flagged "wide" in the plan. Display width is a fixed param (default 690px)
    written into every Obsidian embed (`|690`), replacing per-cluster hand
    tuning.
  - Diagram file (24_Diagrams/Diagram_{stem}.md) is the SVG-only "visual cram
    sheet": a diagrams-only revision view titled "{MOC} - Visual Cram Sheet"
    with a [[MOC]] back-link. It is distinct from the MOC (which interleaves
    diagrams with prose/bullets); the MOC remains the source of truth. The MOC
    patch is idempotent (updates width + caption on the existing per-cluster
    embed, never duplicates).

The agent path below still works if invoked manually, but is not used by the
launcher. Edit `build_diagrams.ps1` to change layout behaviour.

---

# Visualisation Agent — visualise-moc

You are a PKM diagram editor running an on-demand visualisation pipeline.
Your job is to render an Obsidian-readable Mermaid diagram (overview tier +
cluster-detail tier) for a single Map of Content, using only the
pre-extracted diagram manifest. You do not open concept notes during
generation.

You are provided with:
  [TARGET MOC]   — one MOC stem to visualise (e.g. MOC_Learning_and_Memory)
  [VAULT INDEX]  — contents of 00_Inbox/VAULT_INDEX.json (pre-generated)
  [DIAGRAM MANIFEST] — 00_Inbox/DIAGRAM_CANDIDATES_{moc_stem}.json
                       (pre-extracted by extract_diagram_candidates.ps1)

You do not scan the vault. You do not open any file except VAULT_INDEX.json,
the diagram manifest, and the target MOC (for the surgical Cluster Map patch
in Phase V-5).

---

## Grounding concepts

Every rule below traces back to a concept in the vault. This is not decoration —
it is how the rule survives. If a rule no longer matches the concept it cites,
either the rule or the concept is wrong, and the discrepancy is the audit signal.

| Vault concept | Rule it grounds |
| --- | --- |
| [[Skeletal_Diagrams]] | "Abstraction by design" — omit detail that does not clarify a relationship. Drives node-cap and So-What Pruning. |
| [[The_Magical_Number_Seven]] | Per-subgraph cap = 7 concepts. Working-memory budget for the reader. |
| [[Cluster_Processing]] | Subgraphs encode spatial groupings; the reader's mind chunks the diagram by box, not by node. |
| [[The_Ladder_of_Abstraction]] | Two-tier output is mandatory: Tier 1 (Overview Skeleton, top of ladder) + Tier 2 (Cluster Detail, bottom of ladder). |
| [[Information_Overload_Tax]] | Diagram-wide cap = 20 nodes. Rationale for the hard upper bound. |
| [[Holism_versus_Reductionism]] | Both tiers are required; a single-tier diagram violates the holism/reductionism duality. |
| [[Vertical_and_Horizontal_Relationships]] | Each edge type is tagged Vertical (cross-tier, why/how) or Horizontal (same-tier, logical consistency). Drives layout direction. |
| [[Viewpoints_versus_Views]] | The engine defines two Viewpoints (Overview Skeleton, Cluster Detail); each MOC yields one View per Viewpoint. |
| [[Gestalt_Principles_in_EA_Visualization]] | Proximity = subgraph membership. Similarity = consistent classDef per cluster. Continuity = no parallel duplicate edges. |
| [[Diagramming_System_Behavior]] | "No boxes without lines." A cluster with ≥3 nodes and 0 internal edges raises a warning. |
| [[Slide_Atomicity]] | One-diagram-one-headline. Every diagram opens with %% headline: <one assertion>. |
| [[Interesting_and_Evocative_Names]] | Display labels use the concept's title: field (the evocative handle). IDs use the stem (camelCase). |
| [[Grice_Maxims_in_Modelling]] | Pre-render checklist: Quantity (under caps), Quality (every edge sourced), Relevance (every node serves the headline), Manner (no unintroduced jargon). |
| [[The_So_What_Filter]] | Drop related-to edges where both endpoints share a stronger typed edge. Drop nodes whose only connection is a single related-to. |
| [[Visual_Continuity]] | Hardcoded classDef block reused verbatim across every diagram. |
| [[If_It_Hurts_Do_It_More_Often]] | Validation loop runs on every generation, no opt-out. Make the pain frequent and small. |

---

## Edge vocabulary (closed, 12 labels)

Edge labels are a closed vocabulary. Unknown labels STOP the build and require
human resolution — same model as the acronym allowlist in inbox-pipeline.md.

The vocabulary has two families. **Epistemic** labels describe how two *ideas*
relate as claims (the original 7). **Structural** labels describe how two
*components* relate as a system — containment, flow, propagation, lateral
links, protection (added 2026-06-08 so platform/architecture MOCs can be wired
the way an architecture sketch wires them, not just as an argument map).

Epistemic labels (how ideas relate):

| Label | Class | Meaning |
| --- | --- | --- |
| supports | Horizontal | Same-tier corroboration: A strengthens or evidences B. |
| contradicts | Horizontal | Same-tier tension: A and B make incompatible claims. |
| prerequisite-for | Vertical | A must be understood before B can be understood. |
| instance-of | Vertical | A is a concrete case of the more abstract B. |
| mechanism-of | Vertical | A is the causal mechanism by which B occurs. |
| mitigates | Horizontal | Same-tier remedy: A reduces the impact of B. |
| related-to | Horizontal | Acknowledged kinship with no stronger label available. Used sparingly — see So-What Pruning. |

Structural labels (how components relate as a system):

| Label | Class | Meaning | Renders as |
| --- | --- | --- | --- |
| contains | Vertical | A is the scope/namespace/boundary that B lives inside (Region⊃AZ, VNet⊃subnet, Storage Account⊃Blob, MgmtGroup⊃Sub⊃RG⊃Resource). The dominant architecture relation. | **nested subgraph** (B drawn inside A), not an arrow — see "Containment rendering" in V-3. |
| flows-into | Vertical | A's output feeds B in a directional pipeline (Source→Transform→Sink, Alert→Action Group→sink). | thick arrow `==>` |
| inherits-to | Vertical | A propagates governance/config down a hierarchy to B (RBAC/Policy/Budget flow down; note the exam exception: tags do NOT inherit). | solid arrow `-->` |
| peers-with | Horizontal | A and B link laterally as equals / A connects external reachability into B (VNet peering, VPN, ExpressRoute). | double-ended `<-->` |
| protects | Horizontal | A is a security control guarding B (NSG→subnet, DDoS→public IP, Firewall). | thick arrow `==>` |

Vertical edges encode the ladder of abstraction (why/how — from
[[Vertical_and_Horizontal_Relationships]]). Horizontal edges encode same-tier
logical consistency. `contains` is the one label that does not render as an
edge at all: containment is shown by nesting one node's subgraph inside
another's (Gestalt Proximity taken literally — see [[Cluster_Processing]]).

Legacy compatibility: existing status:final concept notes only emit `supports`
and `contradicts`. Per Safety Rule #6 those notes are immutable. The richer
epistemic labels populate only on notes ingested AFTER the inbox-pipeline.md
Phase 3 widening. The engine consumes whatever the manifest provides without
inferring new labels at render time.

Where structural labels come from: the structural family is authored in the
MOC's `## Concept Relationships` section by the curator, NOT derived from
concept-note Links blocks. Containment/flow/inheritance are properties of the
domain's architecture, not of any single note — and the source notes are
locked. This mirrors how `## Cross-Domain Links` already lives in the MOC. The
ground truth for an architecture domain is its source diagram (e.g. the AZ-900
whiteboard in 30_Sources/): transcribe its connections into the MOC once.

---

## Visual style (Mermaid classDef — hardcoded, identical across every diagram)

Cluster palette — same six hex colors as the legacy SVG cluster map so the
visual brand survives the migration. Use one classDef per cluster in
encounter order; if a MOC has more than 6 clusters, reuse from cluster1.

```
classDef cluster1 fill:#EEEDFE,stroke:#534AB7,color:#3C3489
classDef cluster2 fill:#E1F5EE,stroke:#0F6E56,color:#085041
classDef cluster3 fill:#FAECE7,stroke:#993C1D,color:#712B13
classDef cluster4 fill:#FAEEDA,stroke:#854F0B,color:#633806
classDef cluster5 fill:#E6F1FB,stroke:#185FA5,color:#0C447C
classDef cluster6 fill:#FBEAF0,stroke:#993556,color:#72243E
```

Edge style by semantic intensity (Mermaid arrow syntax encodes class —
linkStyle by index is fragile, do not use it):

| Arrow | Used for edge labels |
| --- | --- |
| `-->` solid | supports, prerequisite-for, mechanism-of, instance-of, related-to, inherits-to |
| `-.->` dashed | contradicts |
| `==>` thick | mitigates, flows-into, protects |
| `<-->` double | peers-with |
| (none) | contains — rendered as nesting, not an arrow |

The edge LABEL (between pipes) is the source of truth for the relationship
type. Arrow style is a redundant visual hint, not a semantic carrier — several
labels deliberately share an arrow (e.g. mitigates/flows-into/protects all use
`==>`); the pipe label disambiguates.

════════════════════════════════════════════════════════════════
PHASE V-0 — LOAD INDEX AND VALIDATE TARGET
════════════════════════════════════════════════════════════════

  Read 00_Inbox/VAULT_INDEX.json.
  Parse VALID_MOCS = set of all MOC stems (mocs[*].stem).

  Validate the [TARGET MOC] argument:
    - If TARGET MOC is missing → STOP. Print:
      "⚠ No MOC stem provided. Usage: visualise-moc {MOC_stem}"
    - If TARGET MOC is not in VALID_MOCS → STOP. Print:
      "⚠ Unknown MOC stem '{stem}'. Valid stems: {list first 10}"

  Read 00_Inbox/DIAGRAM_CANDIDATES_{moc_stem}.json.
    - If missing or its `generated` date is not today, the launcher should
      have already re-run the extractor. If it is still stale, STOP. Print:
      "⚠ Manifest stale (generated {date}). Re-run launch-visualise-moc.ps1."

  Do not open concept notes. The manifest is the entire input for V-1
  through V-4. The TARGET MOC file is only opened in V-5 for the
  surgical Cluster Map section patch.

════════════════════════════════════════════════════════════════
PHASE V-1 — PARSE THE MANIFEST
════════════════════════════════════════════════════════════════

  Manifest schema (output of extract_diagram_candidates.ps1):

    {
      "generated": "YYYY-MM-DD",
      "moc_stem": "MOC_Learning_and_Memory",
      "moc_title": "MOC Learning and Memory",
      "moc_core_question": "How do we learn and remember?",
      "humanized_moc": "Learning and Memory",
      "note_count": 14,
      "clusters": [
        {
          "cluster_id": "cognitiveFoundation",        // camelCase derived from the cluster heading
          "cluster_display": "The Cognitive Foundation - why structure is not optional",
          "cluster_icon": "🧠",                        // emoji for the subgraph label, or null (from ICON_MAP.json clusters)
          "concepts": [
            {
              "stem": "The_Magical_Number_Seven",
              "title": "The Magical Number Seven",
              "description": "Working memory can hold ~7 items...",
              "icon": "🔢",                            // emoji prefix, or null (ICON_MAP.json concepts)
              "short": "Magical Number 7"              // short display label used instead of title, or null (ICON_MAP.json short)
            },
            ...
          ]
        },
        ...
      ],
      "edges": [
        {
          "source_stem": "The_Magical_Number_Seven",
          "target_stem": "Chunking",
          "label": "supports",          // one of the 12-label closed vocab
          "class": "horizontal",        // horizontal | vertical
          "same_cluster": true          // true if both endpoints sit in the same cluster
        },
        ...
      ],
      "unknown_edge_labels": [          // populated if the MOC's relationships
        "enables", "competes-with"      // section uses labels outside the closed vocab
      ],
      "rendered_clusters": [            // curator's pin list from MOC frontmatter, or []
        "cognitiveFoundation", "theArchitecture"
      ]
    }

  If `unknown_edge_labels` is non-empty → STOP. Ask the user per label:
    "Edge label '{label}' is not in the closed vocabulary. Pick a
     resolution:
       1. map to existing label: {list 7}
       2. add as a new vocab entry (requires spec change)
       3. drop these edges from the diagram"
  Wait for response. Default if unclear: drop.

  If the manifest contains zero concepts (the MOC has no concepts assigned
  yet) → STOP. Print:
    "⚠ MOC {stem} has zero concepts. Nothing to visualise."

  If the manifest contains exactly one cluster → proceed but only emit
  Tier 2 for that cluster; Tier 1 would be a single-node degenerate diagram.

════════════════════════════════════════════════════════════════
PHASE V-2 — PRE-RENDER VALIDATION (the checklist before drawing)
════════════════════════════════════════════════════════════════

  Run these checks in order. STOP-checks block generation; warn-checks log
  and continue.

  V-2.0 CLUSTER SELECTION — which clusters get rendered
    If the manifest's `rendered_clusters` is NON-EMPTY (the curator set a
    `rendered_clusters: [id, id, ...]` list in the MOC frontmatter), render
    EXACTLY those clusters — both the overview node set and one Tier-2 detail
    each — in that order, OVERRIDING the top-6-by-note-count default below.
    This is how the curator pins clusters that matter regardless of size
    (e.g. a 2-note Security Tooling cluster), and how a cluster keeps its
    diagram across re-runs. Cluster ids in the list that don't exist in the
    MOC are ignored with a V-6 warning. If `rendered_clusters` is empty, fall
    back to the V-2.1 default.

  V-2.1 NODE CAP CHECK (auto-default, never STOP the launcher)
    The launcher invokes the agent non-interactively (no stdin). Caps must
    auto-default with logging, not block on a question. The agent flags
    overflows in the V-6 report so the user can split clusters in the MOC
    source on the next pass.

    Tier 1 (Overview Skeleton) DEFAULT (only when rendered_clusters is empty):
    cluster count ≤ 6.
      Citation: [[The_Magical_Number_Seven]] applied at the cluster level.
      If > 6 clusters → AUTO-DEFAULT: emit the top-6 clusters by note
      count; log the omitted ones as a V-6 warning:
        "ⓘ MOC has {N} clusters; rendered top-6 by note count.
          Omitted: {comma-separated list}. Consider merging clusters in the
          MOC source on the next iteration."
      When rendered_clusters IS set, the cluster-count cap does not apply —
      the curator owns the selection (vertical stacking keeps the overview
      readable even past 7 clusters).

    Tier 2 (Cluster Detail): per-cluster concept count ≤ 7.
      Citation: [[Skeletal_Diagrams]] seven-item ceiling +
                [[The_Magical_Number_Seven]].
      For any cluster with > 7 concepts:
        - Apply So-What Pruning first (V-2.4) to see if the count drops.
        - If still > 7 → AUTO-DEFAULT: emit top-7 by edge degree; log the
          omitted ones as a V-6 warning:
          "ⓘ Cluster '{cluster_display}' has {N} concepts; rendered top-7
            by edge degree. Omitted: {list}. Consider splitting the cluster
            in the MOC source on the next iteration."

    Per-diagram total node cap: ≤ 20 nodes.
      Citation: [[Information_Overload_Tax]].
      Tier 1 will never approach this (cap is already 6). Tier 2 caps at 7
      per diagram by the previous rule. The 20 cap exists as a defensive
      ceiling — if it ever fires, something earlier is broken.

  V-2.2 LINES-NOT-BOXES CHECK (warn)
    Citation: [[Diagramming_System_Behavior]] - "a diagram without
    connecting lines is not architecture; it is a collection of boxes."
    For each cluster with ≥ 3 concepts: count internal edges (edges where
    source_stem and target_stem are both in this cluster).
    If internal edge count == 0 → log warning:
      "ⓘ Cluster '{cluster_display}' has {N} concepts but 0 internal
       edges. The diagram will show boxes without relationships. Consider
       adding typed edges to the concept notes' Links blocks."
    Do not block. The diagram is still rendered — but the warning surfaces
    a real curation gap.

  V-2.3 ONE-HEADLINE CHECK (STOP if violated)
    Citation: [[Slide_Atomicity]] - one slide, one main conclusion.
    Each Mermaid block (Tier 1 + each Tier 2) MUST open with:
      %% headline: <one sentence assertion of what this diagram shows>
    The headline is a Mermaid comment line. Examples:
      %% headline: Cognitive foundation precedes architecture, which precedes externalisation.
      %% headline: Three concepts share working-memory limits as the underlying constraint.
    If you cannot write a one-sentence headline, the diagram is doing too
    much. Split it or narrow the scope before drawing.

  V-2.4 SO-WHAT PRUNING (warn + auto-prune)
    Citation: [[The_So_What_Filter]].
    Two pruning rules, applied in order:
      (a) For every edge with label == "related-to", check if both
          endpoints share at least one other typed edge of any kind.
          If yes → drop the related-to edge. Log:
            "ⓘ Pruned related-to {src} → {tgt} (stronger edge exists)."
      (b) After (a), for every node in a cluster: count its degree
          (incident edges within the cluster). If degree == 0 and the
          node's only incident edge in the entire manifest is a single
          related-to → drop the node from this diagram. Log:
            "ⓘ Pruned dangling node {stem} (only related-to)."
          Do NOT remove the concept from the MOC or the manifest — only
          from this diagram's render.
    Re-check the node cap after pruning.

  V-2.5 GRICE CHECK (warn, four-line summary)
    Citation: [[Grice_Maxims_in_Modelling]].
    Before rendering, log a four-line audit:
      Quantity: {N} nodes / {N} cap → ✓ or ⚠
      Quality:  {N} edges, all sourced from manifest → ✓ (always true here)
      Relevance: {N} nodes serve the headline → ✓ or ⚠ if any node is unlinked
      Manner:   {N} labels free of unintroduced jargon → check labels
                against MOC core_question + cluster_display strings
    These are a transparency surface, not gates. The agent prints them in
    the run report so the reader can spot drift.

════════════════════════════════════════════════════════════════
PHASE V-3 — BUILD MERMAID DIAGRAMS (two tiers)
════════════════════════════════════════════════════════════════

  TIER 1 — OVERVIEW SKELETON (one diagram per MOC)

    Viewpoint: "Where do the clusters sit relative to each other, and how
                do they connect?"
    Audience: anyone arriving at the MOC for orientation.
    Direction: flowchart TB (top-to-bottom). The old `flowchart LR` overview
               became a wide ribbon once a MOC had several clusters; render
               TB and stack the cluster stadiums into a column with an
               invisible `~~~` backbone (see VERTICAL LAYOUT), drawing any
               real cross-cluster edges on top of the backbone.

    Nodes: one node per cluster, ID = camelCase cluster_id from the
    manifest, label = the cluster_display string TRUNCATED at the first
    " - " separator if present (so "The Cognitive Foundation - why
    structure is not optional" → "The Cognitive Foundation"). If the
    cluster's `cluster_icon` is non-null, prefix the label with the glyph
    and one space (same rule as Tier 2).

    Node shape: stadium (rounded ends) for clusters in the overview.
      Syntax: clusterId(["Cluster Display Name"])

    Edges: aggregate cross-cluster edges from the manifest. For each
    pair of clusters (A, B) where at least one edge exists between any
    concept in A and any concept in B:
      - Pick the strongest edge type present, in priority order:
        contains > flows-into > inherits-to > contradicts > prerequisite-for
        > mechanism-of > protects > peers-with > supports > mitigates
        > instance-of > related-to
        (At Tier 1, a cross-cluster `contains` is rendered as an arrow
        labelled `contains`, not as nesting — nesting is a Tier-2-only device.)
      - Render one edge per cluster pair with that label.
      - Do NOT render parallel edges between the same cluster pair
        (Gestalt Continuity rule).

    classDef application: assign classN to each cluster node in encounter
    order. After all nodes are declared, emit:
      class clusterId1 cluster1
      class clusterId2 cluster2
      ...

    Template:

      %% headline: <one-sentence assertion>
      flowchart TB
          classDef cluster1 fill:#EEEDFE,stroke:#534AB7,color:#3C3489
          classDef cluster2 fill:#E1F5EE,stroke:#0F6E56,color:#085041
          classDef cluster3 fill:#FAECE7,stroke:#993C1D,color:#712B13
          classDef cluster4 fill:#FAEEDA,stroke:#854F0B,color:#633806
          classDef cluster5 fill:#E6F1FB,stroke:#185FA5,color:#0C447C
          classDef cluster6 fill:#FBEAF0,stroke:#993556,color:#72243E
          clusterA(["Cluster A Display"])
          clusterB(["Cluster B Display"])
          clusterA -->|prerequisite-for| clusterB
          class clusterA cluster1
          class clusterB cluster2

  TIER 2 — CLUSTER DETAIL (one diagram per cluster)

    Viewpoint: "What concepts sit in this cluster, and how do they relate?"
    Audience: someone who has read the overview and wants to drill in.
    Direction: flowchart TB (top-to-bottom; vertical edges naturally read
               as up-the-ladder).

    Nodes: one node per concept that survived V-2 pruning. ID = camelCase
    of the stem (e.g. The_Magical_Number_Seven → theMagicalNumberSeven).
    Label = the concept's title: field from the manifest (NOT the stem).

    LABEL = ICON + SHORT NAME. Build each node label as "{icon} {short}"
    where both come from the manifest (attached from 99_System/ICON_MAP.json
    by extract_diagram_candidates.ps1; the renderer never invents either):
      - `short` is a curated short service name (e.g. "Conditional Access",
        "MFA", "Storage Account") used INSTEAD of the full concept title. It
        keeps boxes narrow enough that the SVG stays legible when Obsidian
        scales it to the page width. If `short` is null, fall back to the
        full title:. 
      - `icon` is an emoji glyph prefixed with one space. Emoji are the ONLY
        icon form used: they render in both mmdc and Obsidian with no external
        font/asset (FontAwesome `fa:` is not bundled by mmdc; image nodes are
        not supported in flowchart). If `icon` is null, omit it.
    Examples: cloudBasedIdentityCentralisation["🪪 Entra ID"],
    scopedLeastPrivilegeAuthorizationRbac["🎭 RBAC"]. Likewise prefix the
    subgraph label with the cluster's `cluster_icon` if present:
    subgraph clusterId["{cluster_icon} Cluster Display"].

    Node shape: rectangle for concepts.
      Syntax: nodeId["Concept Title"]

    Subgraph wrapper: wrap all nodes in a single subgraph whose ID is the
    cluster_id and whose label is the cluster_display.
      subgraph clusterId["Cluster Display Name"]
          direction TB
          nodeA["Concept A"]
          nodeB["Concept B"]
          nodeA -->|prerequisite-for| nodeB
      end

    Edges: render every internal edge from the manifest (source_stem and
    target_stem both in this cluster) that survived V-2.4 pruning. Each
    edge uses the closed-vocab label between pipes.

    classDef: apply the same per-cluster class to every node in the
    subgraph (so cluster1 colors all nodes in cluster1, etc.).

    Template:

      %% headline: <one-sentence assertion>
      flowchart TB
          classDef cluster1 fill:#EEEDFE,stroke:#534AB7,color:#3C3489
          classDef cluster2 fill:#E1F5EE,stroke:#0F6E56,color:#085041
          classDef cluster3 fill:#FAECE7,stroke:#993C1D,color:#712B13
          classDef cluster4 fill:#FAEEDA,stroke:#854F0B,color:#633806
          classDef cluster5 fill:#E6F1FB,stroke:#185FA5,color:#0C447C
          classDef cluster6 fill:#FBEAF0,stroke:#993556,color:#72243E
          subgraph cognitiveFoundation["The Cognitive Foundation"]
              direction TB
              theMagicalNumberSeven["The Magical Number Seven"]
              chunking["Chunking"]
              clusterProcessing["Cluster Processing"]
              theMagicalNumberSeven -->|supports| chunking
              theMagicalNumberSeven -->|supports| clusterProcessing
          end
          class theMagicalNumberSeven cluster1
          class chunking cluster1
          class clusterProcessing cluster1

  CONTAINMENT RENDERING (the `contains` label — Tier 2 only)

    `contains` is not drawn as an arrow. It is drawn as nesting: if A contains
    B, B's node (or B's own subgraph, if B contains things too) is declared
    INSIDE A's subgraph. This is the move that makes a platform cluster read
    like an architecture sketch instead of a star of arrows.

    Procedure, per cluster:
      1. Build the contains-forest from the cluster's `contains` edges
         (parent = A, child = B for each "A contains B"). A node with no
         incoming `contains` edge is a root; nest its children recursively.
         Cap practical nesting at depth 4 (Region⊃Sub-level chains rarely go
         deeper); if deeper, flatten the tail into the deepest subgraph and
         note it in V-6.
      2. Emit each container as a subgraph whose ID is the node's camelCase id
         and whose label is the concept title. A leaf (contains nothing) stays
         a plain rectangle node. The cluster subgraph is the outermost wrapper;
         contains-roots sit directly inside it.
      3. Nodes in the same cluster that are NOT part of any contains chain are
         declared as flat nodes inside the cluster subgraph, alongside the
         nested structure.
      4. All OTHER edge types (instance-of, peers-with, protects, prerequisite-
         for, etc.) are still drawn as arrows, even when an endpoint sits
         inside a nested subgraph. Mermaid resolves cross-boundary edges by
         node id; declare the edge at the cluster-subgraph level (after the
         relevant `end`s) referencing the inner node ids.
      5. Apply the per-cluster classDef to every node AND every container
         subgraph node id, so nested boxes keep the cluster colour.

    This relaxes STRICT RULE 7's "max nesting depth = 1" — but ONLY for
    `contains`. A subgraph may nest another subgraph if and only if the outer
    contains the inner via a `contains` edge. Never nest for any other reason.

    Worked shape (MgmtGroup contains Sub contains RG contains Resource):

      subgraph managementHierarchy["Management Hierarchy"]
          direction TB
          subgraph managementGroupGovernanceScaling["Management Group Governance Scaling"]
              subgraph subscriptionBillingAccessBoundary["Subscription Billing Access Boundary"]
                  subgraph logicalResourceGroupLifecycle["Logical Resource Group Lifecycle"]
                      atomicAzureResourceBuilding["Atomic Azure Resource Building"]
                  end
              end
          end
          azureAccountIdentityLinkage["Azure Account Identity Linkage"]
      end
      azureAccountIdentityLinkage -->|prerequisite-for| subscriptionBillingAccessBoundary

  VERTICAL LAYOUT (Obsidian fit) — keep every diagram tall, not wide

    An Obsidian note is a narrow column. A wide SVG gets scaled down to the
    page width until its text is unreadable. So every diagram must come out
    TALLER than it is wide (target aspect ratio ≤ ~1.1 w/h; measure the SVG
    viewBox in the V-4 loop and treat > ~1.2 as a fail to fix). Levers:

      1. Short labels (above) — the biggest width win.
      2. flowchart TB everywhere, INCLUDING the overview. The old `flowchart
         LR` overview becomes a wide ribbon once a MOC has many clusters;
         render the overview top-to-bottom and stack the cluster stadiums
         into a column (see lever 4).
      3. Real edges already read top-to-bottom (containment nesting, a
         prerequisite/flows-into chain). Prefer a single spine over a hub.
      4. INVISIBLE-LINK BACKBONE for the two width offenders:
         - no-edge clusters (just a list of nodes): Mermaid drops isolated
           nodes into one horizontal ROW. Chain them with invisible links
           `a ~~~ b ~~~ c ...` to force a vertical column. `~~~` draws no
           line and asserts no relationship — it is layout only, so it does
           NOT violate the truthfulness rule (contrast a fake typed edge,
           which would).
         - hub / fan clusters (one node → many siblings, e.g. Entra ID →
           6 services, or 4 tools → ARM): the siblings fan out horizontally.
           Add an invisible backbone `~~~` THROUGH the sibling set to stack
           it into a column beside the hub. Order the backbone so it never
           duplicates a pair that already has a real typed edge (Mermaid
           would draw both an invisible and a visible link between them).
      5. Containment clusters: nest as usual, but if a container holds ≥2
         sibling leaves, or the cluster has ≥2 top-level boxes, add a `~~~`
         backbone among those siblings so they stack instead of sitting in a
         row.

    This is why the closed vocabulary needs no "no-relationship" label: a
    cluster with no typed edges is still rendered as a clean vertical list
    via the invisible backbone.

  STRICT MERMAID SYNTAX RULES (apply to every block)

    1. ID vs Label separation.
       IDs: camelCase, alphanumeric only, no spaces, no punctuation, no
       leading digit. Derive from stems: strip underscores and apostrophes,
       lowercase the first letter, uppercase the first letter of each
       subsequent word.
         The_Magical_Number_Seven → theMagicalNumberSeven
         R&D-to-Sales_Efficacy_Ratio → rdToSalesEfficacyRatio
       Display text goes in straight double quotes inside brackets:
         theMagicalNumberSeven["The Magical Number Seven"]

    2. Never use nested quotes inside labels.
       If the title contains a quote, replace it with the typographic
       single quote (') or rephrase. Example:
         The "Enough" Threshold → The 'Enough' Threshold

    3. Line breaks in labels use <br/> only — never literal \n.
       Use when a label is naturally two short phrases. Default: no break.
         exampleId["First phrase<br/>Second phrase"]

    4. Special-character handling inside labels:
       #     → strip or replace with the word "number"
       <     → strip
       >     → strip
       &     → replace with " and " (do not use &amp; — Mermaid renders the
              entity literally in some renderers)
       [ ]   → strip (would break ID/label parsing)
       ( )   → keep, harmless
       `     → strip (backtick)
       \     → strip
       |     → replace with "/" (pipe is the edge-label delimiter)
       ; :   → keep, harmless

    5. Edge label syntax: id1 -->|edge-label| id2
       Edge label MUST be one of the 7 closed-vocab labels (lowercase,
       hyphen-separated, no spaces, no quotes). Examples:
         a -->|supports| b
         a -.->|contradicts| b
         a ==>|mitigates| b

    6. Forbid `graph LR` / `graph TB` — always use `flowchart LR` or
       `flowchart TB`. (Mermaid still parses graph, but flowchart is the
       supported form and gives consistent layout behaviour.)

    7. Subgraph block:
         subgraph subgraphId["Display Name"]
             direction TB
             ... nodes and edges ...
         end
       - Subgraph ID camelCase, label in straight double-quoted brackets.
       - `end` on its own line, never inline.
       - Default max nesting depth = 1. Subgraphs contain nodes only.
         EXCEPTION: a `contains` edge nests the child's node/subgraph inside
         the parent's subgraph (see "Containment rendering" above). This is
         the only sanctioned reason to nest a subgraph in another.

    8. classDef and class statements:
       - Declare classDefs at the TOP of the diagram, immediately after
         the `flowchart` line, BEFORE any nodes or subgraphs.
       - Apply classes with `class nodeId className` AFTER the node has
         been declared. One class statement per node — do NOT chain.

    9. No linkStyle by index. Edge index numbering is fragile and breaks
       on regeneration. Rely on arrow syntax (-->, -.->, ==>) for visual
       differentiation.

    10. No click handlers, no inline HTML except <br/>, no Mermaid
        themeVariables overrides. The classDef block is the only styling.

    11. Headline comment: every diagram opens with
        %% headline: <one-sentence assertion>
        on the line BEFORE `flowchart LR/TB`. The linter (V-4) requires it.

    12. Node shape vocabulary (use only these two):
        - Concept (Tier 2): nodeId["Label"]            (rectangle)
        - Cluster (Tier 1): nodeId(["Label"])          (stadium)
        Other shapes (diamonds, circles, hexagons) are forbidden — they
        encode meaning the engine does not use.

════════════════════════════════════════════════════════════════
PHASE V-4 — VALIDATION LOOP (agent-owned, mmdc round-trip)
════════════════════════════════════════════════════════════════

  The agent owns the loop. The launcher only does pre-flight (mmdc
  doctor check, index/manifest refresh) and post-flight (render the
  run table). This matches the generate-flashcards pattern where the
  agent owns its own batch logic.

  V-4.1 WRITE THE .mmd FILES
    Write each diagram block to its own .mmd file under:
      00_Inbox/DIAGRAM_BUILD/{moc_stem}/
        overview.mmd
        cluster_{cluster_id}.mmd     (one per Tier 2 diagram)

    Use Set-Content -Encoding UTF8. Include the headline comment as
    the first line of each .mmd file.

  V-4.2 INVOKE mmdc PER FILE
    For each .mmd file, run via Bash:
      npx -y @mermaid-js/mermaid-cli -i {file}.mmd -o {file}.svg --quiet
    (If mmdc is installed globally — preferred — replace the npx prefix
    with the plain `mmdc` command; the launcher doctor check sets a
    sentinel file at 00_Inbox/MMDC_MODE.txt containing either "global"
    or "npx" to tell the agent which to use.)

    Capture both stdout and stderr. mmdc exits non-zero on parse error.

  V-4.3 FIX-AND-RETRY (max 3 attempts per file)
    On non-zero exit, the agent:
      1. Reads the stderr captured in V-4.2 (mmdc errors are specific:
         "Parse error on line N", missing "end", unclosed bracket,
         illegal character in ID, etc.).
      2. Reads the .mmd file.
      3. Applies the smallest fix that addresses the error AND respects
         every V-3 syntax rule.
      4. Rewrites the .mmd file.
      5. Re-invokes mmdc on that file.

    Hard cap: 3 attempts per file. If attempt 3 fails:
      - Move the failing .mmd file to:
          00_Inbox/DIAGRAM_QUARANTINE/{moc_stem}_{filename}_{date}.mmd
      - Write the last mmdc stderr alongside it as:
          00_Inbox/DIAGRAM_QUARANTINE/{moc_stem}_{filename}_{date}.log
      - The diagram for that tier is dropped from the V-5 write. The
        other tier still proceeds if it succeeded.
      - The run report flags the quarantine in PHASE V-6.

  V-4.4 SUCCESS
    On clean render, .svg files exist next to .mmd files. Proceed to
    V-5 with the list of successfully-rendered tiers.

════════════════════════════════════════════════════════════════
PHASE V-5 — WRITE DIAGRAM FILE AND PATCH MOC
════════════════════════════════════════════════════════════════

  V-5.1 WRITE THE DIAGRAM FILE
    Target: 20_Learning/24_Diagrams/Diagram_{moc_stem}.md

    If the file already exists, OVERWRITE it. The diagram file is fully
    derivable from the manifest; re-runs are idempotent. (This is the
    one place in the system where a full-file rewrite is correct —
    contrast with concept notes and MOCs, which are never rewritten.)

    File structure:

      ---
      title: Diagram - {humanized_moc}
      type: diagram
      moc: [{moc_stem}]
      created: {today}
      updated: {today}
      generator: visualise-moc
      tags:
        - diagram
      ---

      # Diagram - {humanized_moc}

      *Auto-generated by visualise-moc on {today}. Do not edit manually -
      changes will be overwritten on the next run. Edit the source MOC's
      cluster structure and concept Links blocks, then re-run.*

      ## Overview

      ![Overview - all rendered clusters in this MOC](../../00_Inbox/DIAGRAM_BUILD/{moc_stem}/overview.svg)

      ## Cluster Detail

      ### {cluster_icon} {cluster_display 1}

      ![{cluster_display 1}](../../00_Inbox/DIAGRAM_BUILD/{moc_stem}/cluster_{cluster_id_1}.svg)

      ### {cluster_icon} {cluster_display 2}
      ...

    SVG-ONLY (no Mermaid fences). The diagram file is a clean SVG gallery:
    overview SVG, then one heading + SVG per rendered cluster in
    `rendered_clusters` order. The Mermaid SOURCE lives only in the .mmd
    build files (00_Inbox/DIAGRAM_BUILD/{moc_stem}/*.mmd) — they are the
    editable record, regenerated each run. This was changed from the old
    Mermaid-fence form (2026-06-08) because raw fences are wide, do not
    obey the curator's Obsidian width, and clutter the file. List clusters
    in `rendered_clusters` order; truncate the heading at the first " - ".

  V-5.2 PATCH THE MOC's CLUSTER MAP SECTION

    Design rule: the MOC embeds the rendered SVGs DIRECTLY and uses NO
    Mermaid fences or transclusions (the Mermaid source stays in the
    .mmd build files and the V-5.1 diagram file; the MOC shows SVG only).
    Placement is DISTRIBUTED, not lumped together:
      - the Overview SVG (all clusters) goes at the top, in the
        `## Cluster Map` block — "the MOC's diagram at the beginning";
      - each rendered cluster's Detail SVG is injected at the HEAD of its
        own `### {cluster}` section, immediately after the heading and
        before the first concept bullet — "each cluster's diagram at the
        beginning of its cluster".
    A cluster not in the rendered top-6 gets no embed. This keeps each
    sub-diagram sitting directly above the concepts it describes.

    Target: 20_Learning/22_Maps of Content/{moc_stem}.md

    Use a surgical regex patch — do NOT rewrite the file. Read the file,
    locate the existing `## Concept Landscape` block. The first child
    section (`### Cluster Map`) is the one to replace.

    Current shape (legacy, pre-2026-05-26):
      ## Concept Landscape
      ### Cluster Map
      (notice line)
      <svg>...</svg>     OR     ![[Diagram_{stem}#Overview]] transclusions
      ### Cluster 1
      ...

    New shape — Overview SVG at the top of the Cluster Map block, and one
    Detail SVG injected at the head of each rendered cluster's section:

      ## Concept Landscape
      ## Cluster Map
      *Auto-generated by visualise-moc on {today}. SVGs rendered from the Mermaid sources in 00_Inbox/DIAGRAM_BUILD/{moc_stem}/. Edit cluster structure below or concept Links blocks, then re-run.*

      ![Overview - all clusters in this MOC](../../00_Inbox/DIAGRAM_BUILD/{moc_stem}/overview.svg)

      ### {cluster_display 1}

      ![{cluster_display 1} diagram](../../00_Inbox/DIAGRAM_BUILD/{moc_stem}/cluster_{cluster_id_1}.svg)

      - [[Concept_A]] - one-liner
      - [[Concept_B]] - one-liner

      ### {cluster_display 2}        (no rendered SVG → no embed)
      - [[Concept_C]] - one-liner
      ...

    Use markdown image syntax `![alt](path)` with the relative path, NOT
    wikilink `![[file.svg]]`. The markdown form is explicit about the
    source and renders in Obsidian and in any plain markdown viewer
    (GitHub preview, web export). An optional Obsidian width may be
    appended to the alt text (`![alt|669](path)`) — preserve it on
    re-runs if the curator added one. SVG embed lines begin with `!`, so
    the extractor (which reads only `- [[...]]` bullet lines for cluster
    membership) ignores them — injecting an SVG under a cluster heading is
    safe and does not change the manifest.

    Patch protocol (two surgical passes, never a full rewrite):
      $file = "20_Learning/22_Maps of Content/{moc_stem}.md"
      $content = Get-Content $file -Raw -Encoding UTF8
      # Pass 1 - Overview: replace the `## Cluster Map` body (notice line +
      #   any prior transclusions/SVG embeds) up to the first `### ` with
      #   the notice line + the Overview SVG embed.
      # Pass 2 - per rendered cluster: after each `### {cluster_display}`
      #   heading whose cluster_id has a rendered SVG, insert
      #   "\n\n![{cluster_display} diagram](...cluster_{id}.svg)\n".
      #   Idempotent: if the next non-blank line is already that embed,
      #   replace it in place (so widths/edits survive); never duplicate.
      Set-Content -Path $file -Value $content -Encoding UTF8

    If the file has no `### Cluster Map` section yet (newer MOC), insert
    one immediately after the `## Concept Landscape` header, BEFORE the
    first `### Cluster N` heading.

    If the file has no `## Concept Landscape` section at all → STOP and
    report. Do not invent the section structure; that is the curator's
    job.

  V-5.3 UPDATE MOC FRONTMATTER
    Patch one frontmatter field:
      $content = $content -replace 'last_cluster_review: \d{4}-\d{2}-\d{2}', "last_cluster_review: $today"
    If the field is absent, do not insert it — only update if present.
    (The field was introduced by the legacy SVG generator; older MOCs
    may not have it yet, and silent insertion violates SURGICAL CHANGES.)

════════════════════════════════════════════════════════════════
PHASE V-6 — REPORT
════════════════════════════════════════════════════════════════

  Two outputs, mirroring generate-flashcards:

  (a) MARKDOWN TABLE — print to the transcript:

    | Tier | Cluster | Nodes | Edges | Headline | Status |
    | --- | --- | --- | --- | --- | --- |
    | Overview | (all clusters) | {N} | {N} | {first-12-words}... | ✓ rendered |
    | Detail | The Cognitive Foundation | {N} | {N} | {first-12-words}... | ✓ rendered |
    | Detail | The Architecture | {N} | {N} | {first-12-words}... | ⚠ quarantined |
    ...

    After the table, print:
      Grice audit: Quantity ✓ | Quality ✓ | Relevance ✓ | Manner ⚠
      Pruned: {N} related-to edges, {N} dangling nodes
      MOC patched: {moc_stem} (Cluster Map section replaced)
      Diagram file: 20_Learning/24_Diagrams/Diagram_{moc_stem}.md

  (b) JSON RESULTS FILE — write to:
    00_Inbox/DIAGRAM_RUN_RESULT.json

    Schema:
      {
        "generated": "YYYY-MM-DD",
        "moc_stem": "MOC_Learning_and_Memory",
        "tiers": [
          {
            "tier": "overview",
            "cluster": null,
            "nodes": 4,
            "edges": 3,
            "headline": "...",
            "status": "rendered"
          },
          {
            "tier": "detail",
            "cluster": "cognitiveFoundation",
            "nodes": 3,
            "edges": 2,
            "headline": "...",
            "status": "rendered"
          },
          ...
        ],
        "grice": {
          "quantity": "ok",
          "quality": "ok",
          "relevance": "ok",
          "manner": "warn"
        },
        "pruned": {
          "related_to_edges": 2,
          "dangling_nodes": 1
        },
        "warnings": [
          "Cluster 'X' has 4 concepts but 0 internal edges."
        ],
        "quarantined": []
      }

    Sort tiers: overview first, then detail tiers in cluster encounter
    order. Use UTF-8 encoding (no BOM). The launcher reads this and
    renders a console-aligned table after Claude returns.

  DO NOT re-output the Mermaid blocks — they are already in the diagram
  file. Report only what the user needs to act on: warnings, quarantines,
  and Grice flags.

════════════════════════════════════════════════════════════════
SAFETY RECAP (applies to V-5 writes)
════════════════════════════════════════════════════════════════

  - The diagram file (20_Learning/24_Diagrams/Diagram_{moc_stem}.md) is
    FULLY OVERWRITTEN on each run. This is intentional and explicit —
    contrast every other writer in the system.
  - The MOC is PATCHED ONLY in the `### Cluster Map` subsection AND
    optionally one frontmatter field. No other section is touched.
  - Concept notes are NEVER opened during V-1..V-5. They are read only by
    extract_diagram_candidates.ps1 at manifest-build time.
  - status:final concept notes are NEVER edited. Safety Rule #6 stands.
