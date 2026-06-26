#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
vault_graph.py — local graph backend for the `vault-graph` skill.

Replaces the external `graphifyy` package (unreviewed, anonymous, heavy) with a
thin local module over the THREE libraries the skill actually uses:

    rapidfuzz   — title fuzzy matching   (similarity S-1)
    datasketch  — MinHash + LSH          (similarity S-2)
    networkx    — directed link graph    (topology / path)

No other third-party imports. Frontmatter titles are read with a tiny regex so
this module does not even pull in PyYAML — keeping the dependency tree to
exactly the three libraries the Decision names (plus datasketch's numpy/scipy).

READ-ONLY. This module never creates, edits, or deletes a vault file. It mirrors
the phases defined in SKILL.md (S-0..S-3, T-0..T-3, P-0..P-2) and exposes them
both as importable functions and as a CLI:

    python vault_graph.py similarity
    python vault_graph.py topology
    python vault_graph.py path "Concept A" "Concept B"

Thresholds are the canonical ones shared with process-inbox Phase 2 overlap
detection (SKILL.md "Similarity thresholds"):
    TITLE_FUZZ_MIN = 80          rapidfuzz.fuzz.token_sort_ratio
    CONTENT_JACCARD_MIN = 0.5    datasketch MinHash, 128 permutations
"""

import os
import re
from pathlib import Path

from rapidfuzz import fuzz
from datasketch import MinHash, MinHashLSH
import networkx as nx

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

# VAULT = the repo root. This file lives at
# <VAULT>/99_System/Claude/vault-graph/vault_graph.py — four parents up.
VAULT = Path(__file__).resolve().parents[3]

CONCEPTS_DIR = VAULT / "20_Learning" / "21_Concepts"
MOCS_DIR     = VAULT / "20_Learning" / "22_Maps of Content"

# Canonical thresholds (shared with inbox-pipeline Phase 2 — keep in sync there).
TITLE_FUZZ_MIN      = 80
CONTENT_JACCARD_MIN = 0.5
MINHASH_PERM        = 128

_WIKILINK_RE  = re.compile(r"\[\[([^\]]+)\]\]")
_TITLE_RE     = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_WORD_RE      = re.compile(r"[a-z0-9]+")


# ── LOADING (S-0 / T-0) ───────────────────────────────────────────────────────

def _read(path: Path) -> str:
    """Read a vault file, tolerating a leading UTF-8 BOM (Windows editors)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("﻿"):
        text = text[1:]
    return text


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text, body_text). If no closing '---', body is ''."""
    if not text.startswith("---"):
        return "", text
    try:
        end = text.index("---", 3)
    except ValueError:
        return text, ""
    return text[3:end], text[end + 3:]


def _title_of(frontmatter: str, stem: str) -> str:
    m = _TITLE_RE.search(frontmatter)
    if not m:
        return stem
    return m.group(1).strip().strip("'\"")


def _link_target(raw: str) -> str:
    """Normalise a raw [[...]] inner string to its target stem.
    Handles [[target|alias]] and [[target#heading]]; '' for empty placeholders."""
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    return target


def load_notes(dirs=None) -> dict:
    """S-0 / T-0 load. Returns {stem: {"title", "body", "links": [stem,...]}}.
    `dirs` defaults to concepts + MOCs (the wikilink graph spans both)."""
    if dirs is None:
        dirs = [CONCEPTS_DIR, MOCS_DIR]
    notes = {}
    for d in dirs:
        if not d.exists():
            print(f"  [WARN] directory not found, skipping: {d}")
            continue
        for root, subdirs, files in os.walk(d):
            subdirs[:] = [s for s in subdirs if not s.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                stem = fname[:-3]
                if stem in notes:
                    continue  # first-seen wins, matching generate_index.py
                text = _read(Path(root) / fname)
                fm, body = _split_frontmatter(text)
                links = []
                for m in _WIKILINK_RE.finditer(body):
                    t = _link_target(m.group(1))
                    if t:
                        links.append(t)
                notes[stem] = {
                    "title": _title_of(fm, stem),
                    "body":  body,
                    "links": links,
                }
    return notes


# ── SIMILARITY (S-1 / S-2 / S-3) ──────────────────────────────────────────────

def title_pairs(notes: dict, threshold: int = TITLE_FUZZ_MIN) -> list:
    """S-1. Flag note pairs whose titles score >= threshold on
    rapidfuzz.fuzz.token_sort_ratio. Returns [(stem_a, stem_b, score), ...]."""
    stems = sorted(notes)
    out = []
    for i in range(len(stems)):
        ti = notes[stems[i]]["title"]
        for j in range(i + 1, len(stems)):
            score = fuzz.token_sort_ratio(ti, notes[stems[j]]["title"])
            if score >= threshold:
                out.append((stems[i], stems[j], round(score, 1)))
    return sorted(out, key=lambda r: -r[2])


def _minhash(text: str, num_perm: int = MINHASH_PERM) -> MinHash:
    mh = MinHash(num_perm=num_perm)
    for tok in set(_WORD_RE.findall(text.lower())):
        mh.update(tok.encode("utf-8"))
    return mh


def content_pairs(notes: dict, threshold: float = CONTENT_JACCARD_MIN,
                  num_perm: int = MINHASH_PERM) -> list:
    """S-2. MinHash + LSH on full note bodies. Returns
    [(stem_a, stem_b, estimated_jaccard), ...] for pairs >= threshold."""
    sigs = {stem: _minhash(n["body"], num_perm) for stem, n in notes.items()}
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    for stem, mh in sigs.items():
        lsh.insert(stem, mh)
    seen, out = set(), []
    for stem, mh in sigs.items():
        for other in lsh.query(mh):
            if other == stem:
                continue
            key = tuple(sorted((stem, other)))
            if key in seen:
                continue
            seen.add(key)
            jac = sigs[key[0]].jaccard(sigs[key[1]])
            if jac >= threshold:
                out.append((key[0], key[1], round(jac, 3)))
    return sorted(out, key=lambda r: -r[2])


def _recommend(in_title: bool, in_content: bool) -> str:
    if in_title and in_content:
        return "merge"
    if in_content:
        return "review"
    return "link"


def similarity(notes: dict = None) -> dict:
    """S-1..S-3. Returns {"title": [...], "content": [...], "pairs": [...]}
    where pairs carries a per-pair recommendation (merge/link/review)."""
    if notes is None:
        notes = load_notes([CONCEPTS_DIR])
    tp = title_pairs(notes)
    cp = content_pairs(notes)
    tset = {(a, b) for a, b, _ in tp}
    cset = {(a, b) for a, b, _ in cp}
    pairs = []
    for a, b in sorted(tset | cset):
        pairs.append({
            "a": a, "b": b,
            "title_score":   next((s for x, y, s in tp if (x, y) == (a, b)), None),
            "content_jaccard": next((s for x, y, s in cp if (x, y) == (a, b)), None),
            "recommendation": _recommend((a, b) in tset, (a, b) in cset),
        })
    return {"title": tp, "content": cp, "pairs": pairs}


# ── TOPOLOGY (T-0..T-3) and PATH (P-0..P-2) ───────────────────────────────────

def build_graph(notes: dict = None) -> "nx.DiGraph":
    """T-0 / P-0. Directed wikilink graph: nodes = note stems (every loaded
    note, plus any link target so dead links are visible), edges = references."""
    if notes is None:
        notes = load_notes()
    G = nx.DiGraph()
    G.add_nodes_from(notes)
    for stem, n in notes.items():
        for target in n["links"]:
            G.add_edge(stem, target)
    return G


def centrality(G: "nx.DiGraph", top: int = 10) -> dict:
    """T-1. Top-N by degree, betweenness, and PageRank."""
    deg = nx.degree_centrality(G)
    bet = nx.betweenness_centrality(G)
    pr  = nx.pagerank(G) if G.number_of_edges() else {n: 0.0 for n in G}
    rank = lambda d: sorted(d.items(), key=lambda kv: -kv[1])[:top]
    return {"degree": rank(deg), "betweenness": rank(bet), "pagerank": rank(pr)}


def structure(G: "nx.DiGraph", present_stems: set = None) -> dict:
    """T-2. Weakly connected components, orphans (no in/out edges), and dead
    links (edge targets that are not real notes). `present_stems` = the set of
    stems that actually exist on disk; defaults to nodes with any out-link or
    explicitly added note nodes is not knowable here, so caller passes it."""
    components = [sorted(c) for c in nx.weakly_connected_components(G)]
    components.sort(key=len, reverse=True)
    orphans = sorted(n for n in G if G.in_degree(n) == 0 and G.out_degree(n) == 0)
    dead = sorted(present_stems is not None
                  and {t for _, t in G.edges() if t not in present_stems}
                  or set())
    return {"components": components, "orphans": orphans, "dead_links": dead}


def topology(notes: dict = None, top: int = 10) -> dict:
    if notes is None:
        notes = load_notes()
    G = build_graph(notes)
    present = set(notes)
    return {"centrality": centrality(G, top), **structure(G, present),
            "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges()}


def shortest_path(a: str, b: str, notes: dict = None) -> dict:
    """P-1/P-2. Shortest wikilink chain a -> b. On no path, report the
    nearest reachable node from each end."""
    if notes is None:
        notes = load_notes()
    G = build_graph(notes)
    if a not in G:
        return {"error": f"source not found: {a}"}
    if b not in G:
        return {"error": f"target not found: {b}"}
    try:
        return {"path": nx.shortest_path(G, a, b)}
    except nx.NetworkXNoPath:
        reach_a = sorted(nx.descendants(G, a))
        reach_b = sorted(nx.ancestors(G, b))
        return {"path": None,
                "reachable_from_source": reach_a[:10],
                "can_reach_target": reach_b[:10]}


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_similarity(res: dict) -> None:
    print(f"== vault-graph similarity ==  "
          f"{len(res['title'])} title pairs, {len(res['content'])} content pairs\n")
    for p in res["pairs"]:
        ts = "-" if p["title_score"] is None else f"{p['title_score']}"
        cj = "-" if p["content_jaccard"] is None else f"{p['content_jaccard']}"
        print(f"  [{p['recommendation']:6}] {p['a']}  <>  {p['b']}"
              f"   (title={ts}, jaccard={cj})")
    if not res["pairs"]:
        print("  (no near-duplicate pairs above threshold)")


def _print_topology(res: dict) -> None:
    print(f"== vault-graph topology ==  "
          f"{res['n_nodes']} nodes, {res['n_edges']} edges\n")
    for metric in ("degree", "betweenness", "pagerank"):
        print(f"  -- top {metric} --")
        for stem, score in res["centrality"][metric]:
            print(f"     {score:.4f}  {stem}")
        print()
    print(f"  weakly connected components: {len(res['components'])}"
          f"  (largest = {len(res['components'][0]) if res['components'] else 0})")
    print(f"  orphans (no in/out links): {len(res['orphans'])}")
    for o in res["orphans"][:20]:
        print(f"     {o}")
    if len(res["orphans"]) > 20:
        print(f"     ... and {len(res['orphans']) - 20} more")
    print(f"  dead wikilinks (target not a real note): {len(res['dead_links'])}")
    for d in res["dead_links"][:20]:
        print(f"     {d}")
    if len(res["dead_links"]) > 20:
        print(f"     ... and {len(res['dead_links']) - 20} more")


def _print_path(res: dict) -> None:
    print("== vault-graph path ==\n")
    if "error" in res:
        print(f"  {res['error']}")
        return
    if res["path"]:
        print("  " + "  ->  ".join(res["path"]))
    else:
        print("  no path exists.")
        print(f"  reachable from source: {res['reachable_from_source']}")
        print(f"  can reach target:      {res['can_reach_target']}")


def main(argv: list) -> int:
    if not argv:
        print("usage: vault_graph.py {similarity|topology|path A B}")
        return 2
    cmd = argv[0]
    if cmd == "similarity":
        _print_similarity(similarity())
    elif cmd == "topology":
        _print_topology(topology())
    elif cmd == "path":
        if len(argv) < 3:
            print("usage: vault_graph.py path \"Concept A\" \"Concept B\"")
            return 2
        _print_path(shortest_path(argv[1], argv[2]))
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
