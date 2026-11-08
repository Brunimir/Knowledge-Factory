# Skill: vault-graph
**Engine:** 03 — Interconnect
**Requires:** the local module `99_System/Claude/vault-graph/vault_graph.py` over
`rapidfuzz` + `datasketch` + `networkx`. Install hash-locked:
`pip install --require-hashes -r 99_System/Claude/vault-graph/requirements.lock`

> **Dependency note.** The previous external dependency `graphifyy` (new,
> anonymous `author: None`, unreviewed, heavy) was **removed on 2026-06-20** and
> replaced by the local module `vault_graph.py`, a thin read-only backend over
> the three libraries this skill actually uses (`rapidfuzz`, `datasketch`,
> `networkx`). The dependency tree now contains no unreviewed third-party code
> and is pinned + hash-locked (`requirements.lock`), clearing the publish gate
> that graphifyy held. The phase descriptions below are implemented by
> `vault_graph.py` (functions `similarity()`, `topology()`, `shortest_path()`)
> and runnable directly: `python vault_graph.py {similarity|topology|path A B}`.

## Purpose
Analyse the vault's concept graph: detect near-duplicate concepts via fuzzy
matching (rapidfuzz + MinHash) and surface structural insights — centrality,
clustering, and path finding — from the wikilink graph (networkx). vault-graph
is the **read-only graph-metric backend for `vault-health`**: its topology
output (orphans, dead wikilinks, centrality) feeds the weekly vault-health
report (feedback loops D and E), rather than being a standalone command users
discover separately.

## Commands

| Command | What it does |
|---|---|
| `vault-graph similarity` | Find near-duplicate concept notes by title and content |
| `vault-graph topology` | Centrality, clustering, and orphan detection across the wikilink graph |
| `vault-graph path {concept-a} {concept-b}` | Shortest wikilink path between two concepts |

---

## `vault-graph similarity`

Find concept notes that are suspiciously similar but filed separately — candidates for merging, linking, or consolidating.

### Phases

**S-0 — Load**
Read all concept note titles and first paragraphs from `20_Learning/21_Concepts/`. If `VAULT_INDEX.json` exists and is fresh, use it; otherwise parse files directly.

**S-1 — Title fuzzy match**
Use `rapidfuzz.fuzz.token_sort_ratio` on all title pairs. Flag pairs scoring ≥ 80.

**S-2 — Content MinHash**
Use `datasketch.MinHash` + LSH on full note bodies (128 permutations). Flag pairs with Jaccard similarity ≥ 0.5.

**S-3 — Report**
For each flagged pair, print:
- Both note titles + their similarity score
- A recommendation: `merge` / `link` / `review`

Output: printed report only. **No vault writes.**

---

## `vault-graph topology`

Build the directed wikilink graph and compute structural metrics to surface the vault's most important, most bridging, and most isolated concepts.

### Phases

**T-0 — Build graph**
Parse all `[[wikilinks]]` from concept notes and MOCs into a directed `networkx.DiGraph`. Nodes = note stems; edges = wikilink references.

**T-1 — Centrality**
Compute and rank:
- **Degree centrality** — most linked-to (hub concepts)
- **Betweenness centrality** — bridge concepts connecting otherwise distant clusters
- **PageRank** — importance weighted by the quality of incoming links

Surface top 10 for each metric.

**T-2 — Clustering**
Find weakly connected components. Flag isolated nodes (no inbound or outbound links) as orphans for human review.

**T-3 — Report**
Print ranked tables + flag structural anomalies (orphans, dead wikilinks pointing to non-existent notes).

Output: printed report only. **No vault writes.**

---

## `vault-graph path {concept-a} {concept-b}`

Trace the shortest wikilink chain between two concepts — useful for understanding how ideas in different MOCs are connected.

### Phases

**P-0 — Build graph**
Same as T-0.

**P-1 — Path find**
Run `networkx.shortest_path(G, source=concept-a, target=concept-b)`.

**P-2 — Report**
Print the full chain of notes from source to target. If no path exists, report the closest reachable node from each end and the gap between them.

Output: printed report only. **No vault writes.**

---

## Similarity thresholds (canonical — shared with the Phase 2 overlap classifier)
The similarity thresholds are defined here, once, and reused by both dedup
paths so they agree:
- **Title fuzzy match:** `rapidfuzz.fuzz.token_sort_ratio ≥ 80`
- **Content MinHash:** Jaccard `≥ 0.5` (128 permutations)
- **Dense cosine floor:** `≥ 0.70` (bge-micro-v2, via `overlap_candidates.py`)

### The dense floor is MEASURED, not chosen (added 2026-08-12)
Calibrated against the vault's own link graph by
`python overlap_candidates.py calibrate` — POSITIVE = concept pairs joined by a
typed edge (pairs the curator chose to **link**, i.e. explicitly decided were
*not* the same concept); NEGATIVE = random concept pairs:

```
POSITIVE 762   NEGATIVE 2286
linked median 0.771   random median 0.600   separation +0.171
best-F1 floor 0.71   recall 0.870  FPR 0.052  precision 0.848
90%-recall floor 0.702
```

Re-derive it as the corpus grows; 0.70 came from a 631-document index.

### No cosine may ever mean "merge"
This calibration measures **relatedness, not identity**, and no higher bar fixes
that. The top of the scale is where contradictions live:

```
0.936  Anycast-Enhanced_Name_Resolution ↔ Domain_Name_System_(DNS)      Related
0.892  Attended_AI_Authentication       ↔ Unattended_AI_Authentication  Related
0.888  Private_Cloud_Model              ↔ Public_Cloud_Model            Contradicts
```

Cosine measures topical proximity and antonyms are maximally topically
proximate. Further, **215 pairs (28% of all linked pairs) score ≥ 0.80** and
every one was deliberately kept separate by the curator; at 0.78 it is 322.
Thresholds gate **attention**; a reader of both bodies gates the verdict. See
[[Concept Corroboration and the Overlap Audit Gate - Decision]].

`process-inbox` Phase 2 OVERLAP DETECTION (see `docs/inbox-pipeline.md`) uses
the SAME fuzz ≥ 80 tripwire to flag spelling-variant / near-duplicate titles
before classifying TYPE 1/2/3/MERGE. If you tune these numbers, change them
here and update the cross-reference in inbox-pipeline.md — do not let the two
dedup paths drift to different thresholds.

## Safety rules
- **Read-only.** This skill never creates, edits, or deletes vault files.
- `VAULT_INDEX.json` can seed the **node set and titles** (stems + frontmatter),
  but it stores **no body wikilinks and no edge list** — so `topology` and
  `path` MUST parse note bodies for `[[wikilinks]]` to build the graph. The
  index alone cannot supply edges. (Extending `generate_index.py` to emit a
  link list would remove that parse, but that is a larger change — not assumed
  here.)
- Never auto-merge or auto-link flagged pairs — similarity results are for human review only.
- Report missing wikilink targets as dead links, not errors; the referenced MOC may exist in the user's full vault but outside this export.
