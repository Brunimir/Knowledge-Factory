"""Shared candidate generator for concept-concept overlap.

Owned by [[Concept Corroboration and the Overlap Audit Gate - Decision]] (2026-08-12).
Called by BOTH `process-inbox` (via launch-process-inbox.ps1) and `weave-links`,
so the two discovery paths cannot drift to different thresholds — the failure
99_System/Claude/vault-graph/SKILL.md already warns about for the two dedup paths.

WHAT THIS DOES NOT DO
  It never decides that two concepts are the same. Cosine measures topical
  proximity, and antonyms are maximally topically proximate — measured on this
  vault, Private_Cloud_Model <-> Public_Cloud_Model scores 0.888 and is a
  *Contradicts*. 215 pairs (28% of all linked pairs) score >= 0.80 and every one
  was deliberately kept separate by the curator. So thresholds here gate
  ATTENTION; the agent, having read both bodies, gates the verdict.

USAGE
  python overlap_candidates.py generate            # from Note Pipe -> manifest
  python overlap_candidates.py weave MOC_A MOC_B   # cross-MOC -> manifest (weave-links)
  python overlap_candidates.py calibrate           # re-derive the floor
  python overlap_candidates.py query "some text"   # ad-hoc probe
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from pathlib import Path

import numpy as np

VAULT = Path(__file__).parent
CONCEPTS = VAULT / "20_Learning" / "21_Concepts"
NOTE_PIPE = VAULT / "00_Inbox" / "Note Pipe"
MANIFEST = VAULT / "00_Inbox" / "OVERLAP_CANDIDATES.json"

sys.path.insert(0, str(VAULT / "99_System" / "Claude" / "vault-retrieval"))
sys.path.insert(0, str(VAULT))

# ── canonical thresholds ─────────────────────────────────────────────────────
# DENSE_FLOOR is MEASURED, not chosen. See calibrate(): it separates 762 concept
# pairs the curator chose to link from 2286 random pairs (linked median 0.771,
# random median 0.600). Best-F1 0.71 / recall 0.870 / FPR 0.052; 90%-recall
# 0.702. Kept in step with vault-graph/SKILL.md — change both or neither.
DENSE_FLOOR = 0.70
FUZZ_TRIPWIRE = 80        # rapidfuzz token_sort_ratio — retained as a SEPARATE
JACCARD_TRIPWIRE = 0.5    # high-confidence lexical flag, never folded into cos
SEED_K = 2                # start with the two nearest
EXPAND_K = 2              # ...then fetch two more while the lowest still clears
MAX_CANDIDATES = 12       # hard stop; a note matching everything is a signal

TYPED_LABELS = ("Related", "Supports", "Contradicts", "Prerequisite-for",
                "Mechanism-of", "Instance-of", "Mitigates")


# ── vault access ─────────────────────────────────────────────────────────────
def _retrieval():
    import retrieval
    return retrieval


def concept_stems() -> set:
    return {p.stem for p in CONCEPTS.glob("*.md")}


def note_vectors(idx) -> dict:
    """L2-normalised mean of each note's chunk vectors."""
    out = {}
    for i, n in enumerate(idx["notes"]):
        mask = idx["chunk_note"] == i
        if not mask.any():
            continue
        v = idx["vecs"][mask].mean(axis=0)
        norm = np.linalg.norm(v)
        if norm > 0:
            out[n["stem"]] = v / norm
    return out


# ── candidate generation ─────────────────────────────────────────────────────
def candidates_for(text: str, exclude: set, retrieval=None) -> list:
    """Adaptive expansion: take SEED_K nearest concept notes; while the LOWEST of
    the current set still scores >= DENSE_FLOOR, pull EXPAND_K more.

    Corpus is CONCEPT NOTES ONLY. The shadow index also spans 40_Solutions and
    10_Ideas, which is why an early probe returned PKMS_Audit_Report as a "match"
    for a database concept. Solutions and Ideas are not corroboration targets.
    """
    retrieval = retrieval or _retrieval()
    hits = retrieval.search(text, top_k=60)["results"]
    ranked = [
        {"stem": h["stem"], "dense_cos": round(float(h["dense_cos"]), 4),
         "bm25": round(float(h["bm25"]), 2), "title": h.get("title", h["stem"])}
        for h in hits
        if "21_Concepts" in h["path"].replace("\\", "/") and h["stem"] not in exclude
    ]
    if not ranked:
        return []

    take = SEED_K
    while (take < len(ranked) and take < MAX_CANDIDATES
           and ranked[take - 1]["dense_cos"] >= DENSE_FLOOR):
        take += EXPAND_K
    return ranked[:min(take, MAX_CANDIDATES)]


def lexical_flags(title: str, body: str, target_stem: str) -> dict:
    """The precision-oriented signal, carried alongside the dense score rather
    than merged into it. On 2026-08-12 it produced 1 candidate from 26,624 pairs
    and missed the batch's strongest match (cos 0.814) — useful as a strong hint,
    useless as the only instrument."""
    try:
        from rapidfuzz import fuzz
    except ImportError:
        return {"fuzz": None, "jaccard": None, "tripwire": False}
    tgt = CONCEPTS / f"{target_stem}.md"
    tgt_title = target_stem.replace("_", " ")
    tgt_body = tgt.read_text(encoding="utf-8") if tgt.exists() else ""
    f = fuzz.token_sort_ratio(title, tgt_title)
    aw, bw = _words(body), _words(tgt_body)
    j = len(aw & bw) / len(aw | bw) if (aw | bw) else 0.0
    return {"fuzz": round(f, 1), "jaccard": round(j, 3),
            "tripwire": bool(f >= FUZZ_TRIPWIRE or j >= JACCARD_TRIPWIRE)}


_STOP = set("""a an the and or of to in on for with by as is are be that this it its from at into than
then when what which how why not no use used using can may must if each other same""".split())


def _words(text: str) -> set:
    text = re.sub(r"\[\[[^\]]*\]\]", " ", text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


# ── inbox parsing (format 1 only — by design) ────────────────────────────────
BLOCK_RE = re.compile(
    r"Concept title:\s*(?P<title>.+?)\s+Stem \(safe\):\s*(?P<stem>\S+)", re.M)
DESC_RE = re.compile(r"Description:\s*(?P<d>.+?)\s+Suggested MOC:", re.S)


def parse_pipe(src_dir: Path = None) -> tuple:
    """Returns (blocks, unaudited).

    Only format (1) structured blocks carry a literal `Description:` field.
    Formats (2) Gist/Evidence and (3) Concept/Why-it-matters do not, so a
    script cannot build a query for them — they go to unaudited[] and the AGENT
    audits them after Phase 1 normalises them. Zero candidates must never be
    indistinguishable from never-looked-at.
    """
    blocks, unaudited = [], []
    for f in sorted((src_dir or NOTE_PIPE).glob("*.md")):
        text = f.read_text(encoding="utf-8")
        found = list(BLOCK_RE.finditer(text))
        if not found:
            unaudited.append({"file": f.name, "reason":
                              "no format-(1) `Concept title:` / `Stem (safe):` header; "
                              "agent must audit after Phase 1 normalisation"})
            continue
        for i, m in enumerate(found):
            seg = text[m.start(): found[i + 1].start() if i + 1 < len(found) else len(text)]
            d = DESC_RE.search(seg)
            if not d:
                unaudited.append({"file": f.name, "stem": m.group("stem"),
                                  "reason": "block has no parseable `Description:` field"})
                continue
            blocks.append({"stem": m.group("stem"),
                           "title": m.group("title").strip(),
                           "description": " ".join(d.group("d").split()),
                           "body": seg, "file": f.name})
    return blocks, unaudited


# ── commands ─────────────────────────────────────────────────────────────────
def generate(src_dir: Path = None, out: Path = None, refresh: bool = True) -> dict:
    retrieval = _retrieval()
    # Q-0 refresh (vault-retrieval SKILL.md). Content-hashed and incremental, so
    # unchanged notes cost nothing. Skipping it silently searches a stale corpus:
    # on 2026-08-12 the index held 631 docs against 920+ live artefacts, which
    # means notes written since the last build are INVISIBLE as candidates.
    if refresh:
        try:
            retrieval.build_index(verbose=False)
        except Exception as e:                      # never block the run on this
            print(f"[warn] shadow-index refresh failed ({e}); using existing index")
    idx = retrieval.load_index()
    blocks, unaudited = parse_pipe(src_dir)
    batch = {b["stem"] for b in blocks}

    # Judge-once: a pair already carrying a verdict in the overlap ledger is not
    # offered for adjudication a second time. Without this the manifest re-asks
    # questions the curator has already answered, and the answer can drift.
    try:
        import overlap_ledger
        judged = overlap_ledger.load()
    except Exception as e:                          # never block the run on this
        print(f"[warn] overlap ledger unreadable ({e}); every pair offered as new")
        judged, overlap_ledger = {}, None

    records, seen = [], 0
    for b in blocks:
        cands = candidates_for(b["description"], exclude=batch, retrieval=retrieval)
        for c in cands:
            c.update(lexical_flags(b["title"], b["body"], c["stem"]))
            c["above_floor"] = c["dense_cos"] >= DENSE_FLOOR
            # adjudication is the AGENT's to write back; never pre-filled
            c["outcome"] = None
            # ...but a PRIOR verdict is evidence, not a pre-fill: it is reported
            # under its own key so the agent can skip the pair, and `outcome`
            # stays None so nothing is mistaken for a fresh judgement.
            row = judged.get(overlap_ledger.key(b["stem"], c["stem"])) if overlap_ledger else None
            c["prior_outcome"] = row["outcome"] if row else None
            seen += 1 if row else 0
        records.append({"stem": b["stem"], "title": b["title"],
                        "source_file": b["file"], "candidates": cands,
                        "adjudicated": False})

    manifest = {
        "generated": __import__("datetime").date.today().isoformat(),
        "dense_floor": DENSE_FLOOR,
        "shadow_index_docs": len(idx["notes"]),
        "concept_corpus": len(concept_stems()),
        "ready_blocks": len(records),
        "concepts": records,
        "unaudited": unaudited,
        "outcome_vocabulary": ["corroborates", "contradicts", "instance-of", "distinct"],
        "already_judged": seen,
    }
    dest = out or MANIFEST
    dest.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    above = sum(1 for r in records for c in r["candidates"] if c["above_floor"])
    print(f"[ok] {dest.name}: {len(records)} concept(s), {above} candidate(s) "
          f">= {DENSE_FLOOR}, {len(unaudited)} unaudited, index {len(idx['notes'])} docs")
    if seen:
        print(f"     {seen} pair(s) carry a prior ledger verdict — do not re-judge")
    return manifest


def weave(moc_stems: list, out: Path = None) -> dict:
    """Cross-MOC candidate generator for `weave-links` PHASE IC-2.

    Was missing entirely until now: IC-2 had the agent eyeball
    `notes[*].description` in the index with no numeric floor at all, despite
    this file's own header claiming weave-links shared `candidates_for()` with
    process-inbox. This closes that gap the same way `generate()` closes it
    for process-inbox: adaptive SEED_K/EXPAND_K expansion at the SAME
    DENSE_FLOOR, against the SAME corpus (concept notes only), via the SAME
    function — one search, not two that can drift.

    Scope is exactly PHASE IC-0/IC-2's own rule: both endpoints must be
    concept notes, and the candidate must sit in an in-scope MOC that is NOT
    among the source concept's own in-scope MOCs (a concept can carry several
    MOCs in its `moc:` list). This function only proposes the ATTENTION set —
    IC-3's grounding-by-quotation pass is still the verdict, unchanged.
    """
    retrieval = _retrieval()
    idx = retrieval.load_index()
    scope = set(moc_stems)

    vault_index_path = VAULT / "00_Inbox" / "VAULT_INDEX.json"
    vault_index = json.loads(vault_index_path.read_text(encoding="utf-8"))

    concept_mocs, concept_text, concept_title = {}, {}, {}
    for n in vault_index["notes"]:
        mocs = set(n.get("moc") or [])
        if mocs & scope:
            concept_mocs[n["stem"]] = mocs
            concept_text[n["stem"]] = n.get("description") or n.get("title", "")
            concept_title[n["stem"]] = n.get("title", n["stem"])

    records = []
    for stem in sorted(concept_mocs):
        mocs_in_scope = concept_mocs[stem] & scope
        text = concept_text[stem]
        if not text:
            records.append({"stem": stem, "title": concept_title[stem],
                            "mocs": sorted(mocs_in_scope), "candidates": [],
                            "skipped": "no description in index"})
            continue

        cands = candidates_for(text, exclude={stem}, retrieval=retrieval)
        cross = []
        for c in cands:
            c_mocs = concept_mocs.get(c["stem"])
            if not c_mocs:
                continue  # candidate not native to any in-scope MOC
            foreign = (c_mocs & scope) - mocs_in_scope
            if not foreign:
                continue  # same in-scope MOC(s) as the source -> not cross-MOC
            c["mocs"] = sorted(foreign)
            c["above_floor"] = c["dense_cos"] >= DENSE_FLOOR
            cross.append(c)
        records.append({"stem": stem, "title": concept_title[stem],
                        "mocs": sorted(mocs_in_scope), "candidates": cross})

    manifest = {
        "generated": __import__("datetime").date.today().isoformat(),
        "scope": sorted(scope),
        "dense_floor": DENSE_FLOOR,
        "shadow_index_docs": len(idx["notes"]),
        "concepts_in_scope": len(records),
        "concepts": records,
    }
    dest = out or (VAULT / "00_Inbox" / "WEAVE_CANDIDATES.json")
    dest.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(len(r["candidates"]) for r in records)
    above = sum(1 for r in records for c in r["candidates"] if c["above_floor"])
    print(f"[ok] {dest.name}: {len(records)} in-scope concept(s), {total} cross-MOC "
          f"candidate(s) ({above} >= {DENSE_FLOOR})")
    return manifest


def calibrate() -> dict:
    """Re-derive DENSE_FLOOR from the vault's OWN link graph.

    POSITIVE = concept pairs joined by a typed edge (pairs the curator chose to
               LINK, i.e. explicitly decided were NOT the same concept)
    NEGATIVE = random concept pairs
    This calibrates RELATEDNESS. It cannot calibrate identity, because the vault
    contains almost no duplicates to learn from — which is itself the finding.
    """
    retrieval = _retrieval()
    idx = retrieval.load_index()
    nvec = note_vectors(idx)
    indexed = {s for s in nvec if s in concept_stems()}

    pos = set()
    for stem in indexed:
        text = (CONCEPTS / f"{stem}.md").read_text(encoding="utf-8")
        if "## Links" not in text:
            continue
        block = text.split("## Links")[1].split("## Ideas")[0]
        for line in block.splitlines():
            m = re.match(r"\s*-\s*(%s):(.*)" % "|".join(TYPED_LABELS), line)
            if m:
                for tgt in re.findall(r"\[\[([^\]]+)\]\]", m.group(2)):
                    if tgt in indexed and tgt != stem:
                        pos.add(tuple(sorted((stem, tgt))))

    random.seed(17)
    pool, neg = sorted(indexed), set()
    while len(neg) < max(len(pos) * 3, 300):
        a, b = random.sample(pool, 2)
        if (k := tuple(sorted((a, b)))) not in pos:
            neg.add(k)

    cos = lambda a, b: float(np.dot(nvec[a], nvec[b]))
    P = np.array([cos(*p) for p in pos])
    N = np.array([cos(*n) for n in neg])

    best, rows = None, []
    for thr in np.arange(0.55, 0.92, 0.01):
        tp, fn = float((P >= thr).sum()), float((P < thr).sum())
        fp, tn = float((N >= thr).sum()), float((N < thr).sum())
        rec = tp / (tp + fn) if tp + fn else 0
        fpr = fp / (fp + tn) if fp + tn else 0
        pre = tp / (tp + fp) if tp + fp else 0
        f1 = 2 * pre * rec / (pre + rec) if pre + rec else 0
        rows.append((thr, rec, fpr, pre, f1))
        if best is None or f1 > best[4]:
            best = (thr, rec, fpr, pre, f1)

    print(f"POSITIVE (linked) {len(P)}   NEGATIVE (random) {len(N)}")
    print(f"linked median {np.median(P):.3f}   random median {np.median(N):.3f}"
          f"   separation {np.median(P) - np.median(N):+.3f}")
    print(f"best-F1 floor {best[0]:.2f}  recall {best[1]:.3f}  FPR {best[2]:.3f}"
          f"  precision {best[3]:.3f}")
    print(f"90%-recall floor {np.percentile(P, 10):.3f}")
    print(f"module DENSE_FLOOR is {DENSE_FLOOR} — update vault-graph/SKILL.md in step")
    return {"best_f1_floor": round(float(best[0]), 2),
            "recall90_floor": round(float(np.percentile(P, 10)), 3),
            "positives": len(P), "negatives": len(N)}


def main(argv) -> int:
    cmd = argv[0] if argv else "generate"
    if cmd == "generate":
        generate(Path(argv[1]) if len(argv) > 1 else None,
                 Path(argv[2]) if len(argv) > 2 else None)
    elif cmd == "weave":
        if len(argv) < 3:
            print("usage: python overlap_candidates.py weave MOC_A MOC_B [MOC_C ...]")
            return 2
        weave(argv[1:])
    elif cmd == "calibrate":
        calibrate()
    elif cmd == "query":
        for c in candidates_for(" ".join(argv[1:]), exclude=set()):
            print(f"  {c['dense_cos']:.3f}  {c['stem']}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

# ---------------------------------------------------------------- coverage KPI
#
# "Where haven't I looked for connections?" - kf/interconnect's second question.
#
# You cannot count relationships nobody has written down. You CAN count the pairs
# THIS generator would surface, and how many sit in a neighbourhood the weave pass
# has never touched.
#
# TWO MISTAKES AVOIDED, both measured on this vault 2026-08-14:
#
# 1. NOT every pair above DENSE_FLOOR. That enumerates 18,856 cross-MOC pairs and
#    means nothing - the floor was calibrated for top-K per note (SEED_K=2 +
#    EXPAND_K=2), and this module already records that 215 pairs above 0.80 were
#    each deliberately kept separate by the curator. Exhaustive enumeration
#    inherits that false-positive rate thousands of times over. The attention set
#    mirrors the generator instead: top-K per note. 2,666 pairs, not 18,856.
#
# 2. NOT "share of candidate pairs that ended up linked" (4.7%). A pair with no
#    link may have been examined and correctly rejected - weave-links records
#    findings, never rejections, so that figure conflates "never looked at" with
#    "looked at and ruled out". The denominator that IS knowable is whether the
#    pass has swept the neighbourhood at all.
#
# So a pair counts as INVESTIGATED when both its concepts sit in a MOC that
# carries recorded cross-domain links. That is a proxy for "someone ran the pass
# here", not proof this pair was considered - stated rather than hidden.

COVERAGE_TOPK = 4          # SEED_K + EXPAND_K, the generator's own reach


def coverage(topk: int = COVERAGE_TOPK) -> dict:
    """Attention-set coverage for kf/interconnect. Read-only."""
    import numpy as _np
    vecs = _np.load(VAULT / ".embeddings" / "shadow.npz")["vecs"]
    meta = json.loads((VAULT / ".embeddings" / "shadow_docs.json").read_text(encoding="utf-8"))
    notes_meta, chunks = meta["notes"], meta["chunks"]
    mocdir = VAULT / "20_Learning" / "22_Maps of Content"
    stems_on_disk = {p.stem for p in CONCEPTS.glob("*.md")}

    acc, cnt = {}, {}
    for i, c in enumerate(chunks):
        if not isinstance(c.get("note"), int):
            continue
        stem = notes_meta[c["note"]]["stem"]
        if stem in stems_on_disk:
            acc[stem] = acc.get(stem, 0) + vecs[i]
            cnt[stem] = cnt.get(stem, 0) + 1
    stems = sorted(acc)
    if not stems:
        return {}
    M = _np.vstack([acc[s] / cnt[s] for s in stems])
    M /= (_np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)

    mocs = {}
    for s in stems:
        fm = (CONCEPTS / f"{s}.md").read_text(encoding="utf-8-sig").split("---", 2)
        mocs[s] = set(re.findall(r"MOC_\w+", fm[1] if len(fm) > 2 else ""))

    swept = set()
    for p in mocdir.glob("*.md"):
        sec = re.search(r"(?ms)^##\s*Cross-Domain Links\s*\n(.*?)(?=^##\s|\Z)",
                        p.read_text(encoding="utf-8-sig"))
        if sec and any("[[" in l for l in sec.group(1).splitlines()):
            swept.add(p.stem)

    S = M @ M.T
    _np.fill_diagonal(S, -1)
    pairs = set()
    for i, s in enumerate(stems):
        if not mocs[s]:
            continue
        taken = 0
        for j in _np.argsort(-S[i]):
            if S[i, j] < DENSE_FLOOR or taken >= topk:
                break
            o = stems[j]
            if mocs[o] and mocs[s].isdisjoint(mocs[o]):
                pairs.add(frozenset((s, o)))
                taken += 1

    investigated = sum(1 for pr in pairs
                       if all(any(m in swept for m in mocs[x]) for x in pr))
    n = len(pairs) or 1
    return {
        "attention_pairs": len(pairs),
        "investigated": investigated,
        "uninvestigated": len(pairs) - investigated,
        "investigated_pct": round(100 * investigated / n, 1),
        "mocs_swept": len(swept),
        "floor": DENSE_FLOOR,
        "topk": topk,
    }
