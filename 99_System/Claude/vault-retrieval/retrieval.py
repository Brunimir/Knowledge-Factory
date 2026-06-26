#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
retrieval.py — hybrid (dense + sparse + RRF) retrieval over the vault Markdown.

The read path for the `vault-query` command. The Markdown is the single source
of truth; this builds a DISPOSABLE, REBUILDABLE shadow index (gitignored under
.embeddings/) and never writes a vault note.

  CHUNK  : notes are split into overlapping, paragraph-aware chunks (~300 words,
           ~15% overlap) so long notes are embedded in full, not truncated at the
           512-token cap (technique mined from tobi/qmd, kept pure-Python — no
           new dependency). Dense + sparse score every chunk; each note takes its
           best chunk (score + snippet).
  DENSE  : bge-micro-v2 (TaylorAI) via onnxruntime, mean-pooled + L2-normalised.
           Same model the vault's Smart Connections plugin uses. We self-embed
           the chunks (not the plugin cache) so the index is self-contained and
           regenerable. Query is embedded with the same model -> same space.
  SPARSE : BM25 over tokenised chunks (pure numpy/Python, no deps).
  FUSE   : Reciprocal Rank Fusion (RRF, k=60) over the dense and sparse chunk
           rankings (and over every multi-query expansion phrasing, see expand=).
           Cross-encoder reranking is intentionally NOT a separate model: the
           vault-query agent reads the top notes during synthesis, which is the
           rerank step (keeps the dependency tree lean).

Incremental like generate_index.py: each note is keyed by whole-file SHA-256, so
`build` only re-embeds changed notes. Graceful degradation: if onnxruntime /
tokenizers / the model are unavailable, dense is skipped and retrieval falls
through to BM25-only (with a warning) — nothing crashes.

CLI:
  python retrieval.py build              # build/refresh the shadow index
  python retrieval.py query "question"   # ranked, cited results (JSON or text)
  python retrieval.py status             # index health

The cited-answer behaviour and multi-query expansion are layered on top by the
`vault-query` skill (see SKILL.md), which calls search().
"""

import os
import re
import json
import math
import hashlib
from pathlib import Path

import numpy as np

# ── PATHS / CONFIG ────────────────────────────────────────────────────────────

# This file lives at <VAULT>/99_System/Claude/vault-retrieval/retrieval.py
VAULT = Path(__file__).resolve().parents[3]

# Corpus = the curated knowledge dirs the index sees (concepts, MOCs, Phase-5
# artefacts, ideas). Note Pipe (raw, unprocessed inbox) is intentionally excluded
# from answer retrieval. These mirror generate_index.py's scan set minus Note Pipe.
RETRIEVAL_DIRS = [
    Path("20_Learning") / "21_Concepts",
    Path("20_Learning") / "22_Maps of Content",
    Path("40_Solutions"),
    Path("10_Ideas"),
]

EMB_DIR     = VAULT / ".embeddings"                 # gitignored, derived
MODEL_DIR   = EMB_DIR / "bge-micro-v2"
SHADOW_VECS = EMB_DIR / "shadow.npz"                # float32 [N, 384]
SHADOW_DOCS = EMB_DIR / "shadow_docs.json"          # aligned doc metadata + body
MODEL_NAME  = "TaylorAI/bge-micro-v2"
EMB_DIM     = 384
MAX_TOKENS  = 512

RRF_K = 60
BM25_K1 = 1.5
BM25_B  = 0.75

# Chunking (mined from tobi/qmd, Python/dependency-free). Notes are split into
# overlapping, paragraph-aware chunks so long notes (MOCs, Solutions) are
# embedded in full instead of truncated at the model's 512-token cap. ~300 words
# stays safely under 512 bge tokens; ~15% overlap preserves cross-boundary context.
CHUNK_WORDS = 300
CHUNK_OVERLAP_WORDS = 45

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WORD_RE  = re.compile(r"[A-Za-z0-9]+")


# ── MARKDOWN LOADING ──────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("﻿"):
        text = text[1:]
    return text


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    try:
        end = text.index("---", 3)
    except ValueError:
        return "", text
    return text[3:end], text[end + 3:]


def _title_of(frontmatter: str, stem: str) -> str:
    m = re.search(r"^title:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    return m.group(1).strip().strip("'\"") if m else stem


def load_corpus() -> list:
    """Return [{stem, path, title, hash, body}] over RETRIEVAL_DIRS. body is the
    note text with frontmatter stripped; title is prepended for embedding/BM25."""
    docs, seen = [], set()
    for rel in RETRIEVAL_DIRS:
        target = VAULT / rel
        if not target.exists():
            continue
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in sorted(files):
                if not fname.endswith(".md"):
                    continue
                stem = fname[:-3]
                if stem in seen:
                    continue
                seen.add(stem)
                p = Path(root) / fname
                raw = p.read_bytes()
                text = raw.decode("utf-8", errors="replace")
                if text.startswith("﻿"):
                    text = text[1:]
                fm, body = _split_frontmatter(text)
                docs.append({
                    "stem":  stem,
                    "path":  p.relative_to(VAULT).as_posix(),
                    "title": _title_of(fm, stem),
                    "hash":  hashlib.sha256(raw).hexdigest(),
                    "body":  body.strip(),
                })
    docs.sort(key=lambda d: d["stem"])
    return docs


def chunk_note(body: str) -> list:
    """Split a note body into overlapping, paragraph-aware chunks that fit
    bge-micro-v2's 512-token cap. Packs blank-line-separated blocks up to
    CHUNK_WORDS, hard-splitting any oversized block, carrying CHUNK_OVERLAP_WORDS
    between chunks. Deterministic from the body, so unchanged notes re-chunk
    identically (the incremental cache reuses their vectors)."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP_WORDS)
    units = []
    for b in blocks:
        words = b.split()
        if len(words) <= CHUNK_WORDS:
            units.append(b)
        else:
            for i in range(0, len(words), step):
                units.append(" ".join(words[i:i + CHUNK_WORDS]))
    chunks, cur = [], ""
    for u in units:
        if cur and len((cur + " " + u).split()) > CHUNK_WORDS:
            chunks.append(cur)
            tail = " ".join(cur.split()[-CHUNK_OVERLAP_WORDS:])
            cur = (tail + " " + u).strip()
        else:
            cur = (cur + " " + u).strip()
    if cur.strip():
        chunks.append(cur.strip())
    return chunks or [""]


def _chunk_embed_text(title: str, chunk: str) -> str:
    """Title carries strong signal; prepend it to each chunk for embed + BM25."""
    return (title + ".\n" + chunk).strip()


# ── DENSE EMBEDDER (bge-micro-v2 via onnxruntime) ─────────────────────────────

class Embedder:
    """Lazy bge-micro-v2 embedder. Raises RuntimeError if the runtime/model is
    unavailable; callers catch this to fall through to BM25-only."""
    def __init__(self):
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            raise RuntimeError(f"dense embedder unavailable (missing dep: {e.name})")
        tok_path = MODEL_DIR / "tokenizer.json"
        mdl_path = MODEL_DIR / "model.onnx"
        if not tok_path.exists() or not mdl_path.exists():
            raise RuntimeError(f"dense embedder unavailable (model not found in {MODEL_DIR})")
        self.tok = Tokenizer.from_file(str(tok_path))
        self.tok.enable_truncation(max_length=MAX_TOKENS)
        self.tok.enable_padding()
        self.sess = ort.InferenceSession(str(mdl_path), providers=["CPUExecutionProvider"])

    def encode(self, texts: list, batch: int = 32) -> np.ndarray:
        out = np.zeros((len(texts), EMB_DIM), dtype=np.float32)
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            encs = self.tok.encode_batch(chunk)
            ids  = np.array([e.ids for e in encs], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
            tt   = np.zeros_like(ids)
            hidden = self.sess.run(None, {"input_ids": ids, "attention_mask": mask,
                                          "token_type_ids": tt})[0]      # [b, seq, 384]
            m = mask[..., None].astype(np.float32)
            pooled = (hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None)  # mean pool
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            out[i:i + len(chunk)] = pooled / np.clip(norms, 1e-9, None)   # L2 normalise
        return out


# ── BM25 (sparse) ─────────────────────────────────────────────────────────────

class BM25:
    def __init__(self, corpus_tokens: list, k1: float = BM25_K1, b: float = BM25_B):
        self.k1, self.b = k1, b
        self.docs = corpus_tokens
        self.N = len(corpus_tokens)
        self.dl = np.array([len(t) for t in corpus_tokens], dtype=np.float32)
        self.avgdl = float(self.dl.mean()) if self.N else 0.0
        df = {}
        self.tf = []
        for toks in corpus_tokens:
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query_tokens: list) -> np.ndarray:
        sc = np.zeros(self.N, dtype=np.float32)
        for t in set(query_tokens):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, counts in enumerate(self.tf):
                f = counts.get(t)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avgdl or 1))
                sc[i] += idf * (f * (self.k1 + 1)) / denom
        return sc


def _tokenize(text: str) -> list:
    return _TOKEN_RE.findall(text.lower())


# ── SHADOW INDEX BUILD / LOAD ─────────────────────────────────────────────────

def build_index(verbose: bool = True) -> dict:
    """Build/refresh the CHUNKED dense shadow index incrementally: re-chunk and
    re-embed only notes whose SHA-256 changed. Writes .embeddings/shadow.npz
    (one row per chunk) + shadow_docs.json (note table + aligned chunk table).
    Read-only on the vault."""
    EMB_DIR.mkdir(exist_ok=True)
    notes = load_corpus()

    # Cache: note hash -> (chunk_texts, chunk_vectors) from the previous build.
    old_by_hash = {}
    if SHADOW_VECS.exists() and SHADOW_DOCS.exists():
        try:
            ov = np.load(SHADOW_VECS)["vecs"]
            om = json.loads(SHADOW_DOCS.read_text(encoding="utf-8"))
            row = 0
            for note in om.get("notes", []):
                nc = note["n_chunks"]
                texts = [c["text"] for c in om["chunks"][row:row + nc]]
                old_by_hash[note["hash"]] = (texts, ov[row:row + nc])
                row += nc
        except Exception:
            old_by_hash = {}

    try:
        embedder = Embedder()
        dense_ok = True
    except RuntimeError as e:
        embedder = None
        dense_ok = False
        if verbose:
            print(f"  [warn] {e} — building SPARSE-ONLY index (no dense vectors).")

    note_recs, chunk_recs, vec_blocks = [], [], []
    reused = embedded = 0
    for note in notes:
        chunks = chunk_note(note["body"])
        cached = old_by_hash.get(note["hash"]) if dense_ok else None
        if cached is not None and cached[0] == chunks:
            vecs_n = cached[1]
            reused += 1
        elif dense_ok:
            vecs_n = embedder.encode([_chunk_embed_text(note["title"], c) for c in chunks])
            embedded += 1
        else:
            vecs_n = np.zeros((len(chunks), EMB_DIM), dtype=np.float32)
        ni = len(note_recs)
        note_recs.append({"stem": note["stem"], "path": note["path"], "title": note["title"],
                          "hash": note["hash"], "n_chunks": len(chunks)})
        chunk_recs.extend({"note": ni, "text": c} for c in chunks)
        vec_blocks.append(vecs_n)

    vecs = np.vstack(vec_blocks) if vec_blocks else np.zeros((0, EMB_DIM), np.float32)
    np.savez_compressed(SHADOW_VECS, vecs=vecs if dense_ok else np.zeros((0, EMB_DIM), np.float32))
    SHADOW_DOCS.write_text(json.dumps({
        "model": MODEL_NAME if dense_ok else None, "dim": EMB_DIM,
        "count": len(note_recs), "chunks_total": len(chunk_recs), "dense": dense_ok,
        "notes": note_recs, "chunks": chunk_recs,
    }, ensure_ascii=False), encoding="utf-8")

    stats = {"notes": len(note_recs), "chunks": len(chunk_recs),
             "notes_embedded": embedded, "notes_reused": reused, "dense": dense_ok}
    if verbose:
        print(f"  [ok] shadow index: {len(note_recs)} notes / {len(chunk_recs)} chunks, "
              f"{embedded} notes embedded, {reused} reused, dense={dense_ok}")
    return stats


def load_index() -> dict:
    if not SHADOW_DOCS.exists():
        raise FileNotFoundError("shadow index missing — run: python retrieval.py build")
    meta = json.loads(SHADOW_DOCS.read_text(encoding="utf-8"))
    notes, chunks = meta["notes"], meta["chunks"]
    vecs = np.load(SHADOW_VECS)["vecs"] if (meta.get("dense") and SHADOW_VECS.exists()) else None
    chunk_note_idx = np.array([c["note"] for c in chunks], dtype=np.int64)
    # BM25 over chunks; prepend each chunk's note title so title terms score too.
    corpus_tokens = [_tokenize(notes[c["note"]]["title"] + " " + c["text"]) for c in chunks]
    return {"meta": meta, "notes": notes, "chunks": chunks,
            "chunk_note": chunk_note_idx, "vecs": vecs, "bm25": BM25(corpus_tokens)}


# ── SEARCH (dense + sparse + RRF, with optional multi-query expansion) ─────────

def _rrf(rankings: list, n: int) -> np.ndarray:
    """Reciprocal Rank Fusion over a list of score arrays. Returns fused score
    per doc. Each ranking contributes 1/(k + rank) for its ranked docs."""
    fused = np.zeros(n, dtype=np.float32)
    for scores in rankings:
        if scores is None:
            continue
        order = np.argsort(-scores)
        for rank, idx in enumerate(order):
            if scores[idx] <= 0:
                continue
            fused[idx] += 1.0 / (RRF_K + rank)
    return fused


def search(query: str, top_k: int = 8, expansions: list = None,
           index: dict = None) -> dict:
    """Hybrid CHUNK-level search aggregated to notes. `expansions`: extra
    query phrasings, each fused via RRF. Dense + BM25 score every chunk; RRF fuses
    them; each note takes its best chunk (score + snippet). Returns
    {results:[{stem,path,title,snippet,dense_cos,bm25,rrf}], dense, max_cos,
    low_confidence}. Degrades to BM25-only if no dense vectors."""
    idx = index or load_index()
    notes, chunks, cn = idx["notes"], idx["chunks"], idx["chunk_note"]
    vecs, bm25 = idx["vecs"], idx["bm25"]
    n_notes, n_chunks = len(notes), len(chunks)
    queries = [query] + list(expansions or [])

    rankings, chunk_cos = [], np.zeros(n_chunks, dtype=np.float32)
    dense_on = vecs is not None and len(vecs) == n_chunks
    if dense_on:
        try:
            qv = Embedder().encode(queries)              # [q, 384] normalised
            sims = vecs @ qv.T                            # [n_chunks, q] cosine
            chunk_cos = sims.max(axis=1)                 # best phrasing per chunk
            for qi in range(sims.shape[1]):
                rankings.append(sims[:, qi].copy())
        except RuntimeError:
            dense_on = False

    chunk_bm25 = np.zeros(n_chunks, dtype=np.float32)
    for q in queries:
        s = bm25.scores(_tokenize(q))
        chunk_bm25 = np.maximum(chunk_bm25, s)
        rankings.append(s)

    fused_chunk = _rrf(rankings, n_chunks)

    # Aggregate chunk -> note: a note scores as its single best chunk.
    note_rrf = np.zeros(n_notes, dtype=np.float32)
    note_cos = np.zeros(n_notes, dtype=np.float32)
    note_bm25 = np.zeros(n_notes, dtype=np.float32)
    note_best = np.full(n_notes, -1, dtype=np.int64)
    for ci in range(n_chunks):
        ni = int(cn[ci])
        if fused_chunk[ci] > note_rrf[ni]:
            note_rrf[ni] = fused_chunk[ci]
            note_best[ni] = ci
        if chunk_cos[ci] > note_cos[ni]:
            note_cos[ni] = chunk_cos[ci]
        if chunk_bm25[ci] > note_bm25[ni]:
            note_bm25[ni] = chunk_bm25[ci]

    order = np.argsort(-note_rrf)[:top_k]
    results = []
    for ni in order:
        if note_rrf[ni] <= 0:
            continue
        bc = int(note_best[ni])
        results.append({
            "stem": notes[ni]["stem"],
            "path": notes[ni]["path"],
            "title": notes[ni]["title"],
            "snippet": _snippet(chunks[bc]["text"]) if bc >= 0 else "",
            "dense_cos": round(float(note_cos[ni]), 4) if dense_on else None,
            "bm25": round(float(note_bm25[ni]), 4),
            "rrf": round(float(note_rrf[ni]), 5),
        })

    max_cos = float(note_cos.max()) if dense_on and n_notes else 0.0
    max_bm25 = float(note_bm25.max()) if n_notes else 0.0
    # Low confidence => the cited-answer command should admit a gap.
    # Semantic similarity is the authority: a strong in-vault match scores cos
    # ~0.70+, while unrelated questions top out ~0.50, so 0.60 cleanly separates.
    # A spurious BM25 keyword hit must NOT override semantic irrelevance. BM25 is
    # the fallback signal only when the dense path is unavailable.
    low_conf = (not results) or (dense_on and max_cos < 0.60) \
               or (not dense_on and max_bm25 < 5.0)
    return {"query": query, "expansions": list(expansions or []), "dense": dense_on,
            "max_cos": round(max_cos, 4), "max_bm25": round(max_bm25, 4),
            "low_confidence": bool(low_conf), "results": results}


def _snippet(body: str, n: int = 240) -> str:
    s = re.sub(r"\s+", " ", body).strip()
    return s[:n] + ("…" if len(s) > n else "")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cmd_query(query: str, as_json: bool, top_k: int, expansions: list = None) -> None:
    res = search(query, top_k=top_k, expansions=expansions)
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    mode = "dense+sparse+RRF" if res["dense"] else "SPARSE-ONLY (dense unavailable)"
    print(f"== vault-query [{mode}] ==  max_cos={res['max_cos']} max_bm25={res['max_bm25']}"
          f"  {'LOW-CONFIDENCE' if res['low_confidence'] else ''}\n")
    if not res["results"]:
        print("  (nothing in the vault matched this query)")
        return
    for r in res["results"]:
        dc = "-" if r["dense_cos"] is None else r["dense_cos"]
        print(f"  rrf={r['rrf']:<7} cos={dc:<7} bm25={r['bm25']:<7} [[{r['stem']}]]")
        print(f"      {r['title']} — {r['snippet'][:140]}")


def main(argv: list) -> int:
    if not argv:
        print("usage: retrieval.py {build|query <text> [--json] [--top N]|status}")
        return 2
    cmd = argv[0]
    if cmd == "build":
        build_index(verbose=True)
    elif cmd == "status":
        try:
            idx = load_index()
            m = idx["meta"]
            print(f"shadow index: {m['count']} docs, dense={m.get('dense')}, model={m.get('model')}")
        except FileNotFoundError as e:
            print(e); return 1
    elif cmd == "query":
        rest = argv[1:]
        as_json = "--json" in rest
        top_k = 8
        expansions = []                               # --expand "phrasing" (repeatable)
        skip = set()                                  # indices consumed by flags
        for i, a in enumerate(rest):
            if a == "--top" and i + 1 < len(rest):
                top_k = int(rest[i + 1]); skip.add(i); skip.add(i + 1)
            elif a == "--expand" and i + 1 < len(rest):
                expansions.append(rest[i + 1]); skip.add(i); skip.add(i + 1)
            elif a == "--json":
                skip.add(i)
        query = " ".join(a for i, a in enumerate(rest) if i not in skip)
        if not query.strip():
            print("usage: retrieval.py query <text> [--json] [--top N] [--expand \"phrasing\" ...]")
            return 2
        _cmd_query(query, as_json, top_k, expansions)
    else:
        print(f"unknown command: {cmd}"); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
