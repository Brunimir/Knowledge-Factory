# Skill: vault-graph
**Engine:** 03 — Interconnect
**Requires:** `graphifyy` (`pip install graphifyy` or `pip install -r requirements.txt`)

## Purpose
Analyse the vault's concept graph using graphifyy: detect near-duplicate concepts via fuzzy matching (rapidfuzz + MinHash) and surface structural insights — centrality, clustering, and path finding — from the wikilink graph (networkx).

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
Read all concept note titles and first paragraphs from `21_Concepts/`. If `VAULT_INDEX.json` exists and is fresh, use it; otherwise parse files directly.

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

## Safety rules
- **Read-only.** This skill never creates, edits, or deletes vault files.
- Prefer `VAULT_INDEX.json` as graph source when available (avoids re-parsing the whole vault).
- Never auto-merge or auto-link flagged pairs — similarity results are for human review only.
- Report missing wikilink targets as dead links, not errors; the referenced MOC may exist in the user's full vault but outside this export.
