# Skill: vault-query
**Role:** Retrieve — a read-only, cross-cutting retrieval command over the whole
vault (the "Usage" job), not one of the five pipeline engines.
**Requires:** the local module `99_System/Claude/vault-retrieval/retrieval.py`
(`onnxruntime` + `tokenizers` + `numpy`). Install hash-locked:
`pip install --require-hashes -r 99_System/Claude/vault-retrieval/requirements.lock`

> **Dependency note.** Dense embeddings run `TaylorAI/bge-micro-v2` — the *same*
> model the vault's Smart Connections plugin uses — on CPU via `onnxruntime` (no
> torch). Sparse (BM25) and RRF fusion are pure numpy. The ONNX model +
> tokenizer download once into `.embeddings/` (gitignored, derived, rebuildable)
> and are not a pip dependency. Markdown stays the single source of truth; the
> shadow index is a disposable, regenerable cache.

## Purpose
Answer an ad-hoc question about the vault with a **cited, synthesised** answer —
or honestly admit the vault has nothing on it. Retrieval is **hybrid**: notes are
split into overlapping chunks, then dense semantic recall (bge-micro-v2) + sparse
keyword (BM25) score every chunk and fuse via Reciprocal Rank Fusion, with each
note taking its best chunk — so a question phrased differently from the target,
or answered deep inside a long note, still finds it. Your **Q-4 read of the top
notes is the reranker** — no separate cross-encoder model is needed, which keeps
the dependency tree lean.

## Command
`vault-query {question}` — synthesises a cited answer from the vault.
**Read-only.** Never writes a vault note. The corpus is concepts, MOCs,
40_Solutions and 10_Ideas (Note Pipe / raw inbox is excluded).

---

## Pipeline (the agent IS in this loop)

**Q-0 — Refresh the shadow index (incremental, cheap).**
Run once at the start of the command:
```
python 99_System/Claude/vault-retrieval/retrieval.py build
```
This re-chunks and re-embeds only notes whose SHA-256 changed (seconds when
nothing changed; ~85 s only on the very first build). Skip if you just built it
this session.

**Q-1 — Expand the query (opportunistic).**
Generate 2–4 alternative phrasings of the question (synonyms, the domain term,
a plain-language restatement). You are the model, so this is free. Pass them as
`--expand` flags. Each phrasing is fused in via RRF, widening recall. If you
have no good rewrites, pass none — retrieval degrades cleanly to the single
query (and to BM25-only if the embedder is ever unavailable).

**Q-2 — Retrieve.**
```
python 99_System/Claude/vault-retrieval/retrieval.py query "{question}" \
    --expand "{phrasing 1}" --expand "{phrasing 2}" --json --top 8
```
Read the JSON: `results[]` (each with `stem`, `path`, `title`, `snippet`,
`dense_cos`, `bm25`, `rrf`), `max_cos`, and `low_confidence`.

**Q-3 — Gate: admit gaps, never fabricate.**
If `low_confidence` is true, OR the top results plainly do not address the
question (read the snippets — semantic score can be a false positive), respond:
> "Nothing in the vault addresses this."
You may name the closest tangential note as a pointer, but do NOT invent an
answer. This is Safety Rule #7: every claim must originate from a source note.

**Q-4 — Synthesise with citations.**
Otherwise, read the top relevant notes from their `path`s (index + notes only —
no outside knowledge), then write a concise answer where **every factual claim
cites its source note** as a clickable `[[stem]]` wikilink. Prefer 2–5 sources;
do not pad with weakly-related notes. Close with a "Sources:" list of the
`[[stem]]`s actually used. If sources disagree, say so and cite both.

---

## Examples
- `vault-query how do I stop password-reuse attacks?`
  → cites `[[Credential_Stuffing]]`, `[[Multi-Factor_Authentication]]`,
    `[[Credential_Proliferation_Mitigation_(SSO)]]`.
- `vault-query what's the best recipe for sourdough?`
  → "Nothing in the vault addresses this." (low_confidence; no fabrication.)

## Safety rules
- **Read-only.** Never creates, edits, or deletes a vault file.
- **No fabrication.** Synthesis draws only from retrieved notes; cite every
  claim; admit gaps rather than guess (Safety Rule #7).
- The shadow index and model under `.embeddings/` are derived and gitignored;
  deleting them and re-running `build` reproduces the index and changes no note.
