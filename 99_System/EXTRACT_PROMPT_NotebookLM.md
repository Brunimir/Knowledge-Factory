# Extraction Prompt — NotebookLM

NotebookLM has two relevant inputs for this workflow:

1. **Custom Instructions** (Notebook Configuration → "Configure notebook"): a sticky 10,000-character persona/format spec that applies to every chat in that notebook. The full extraction spec lives here.
2. **Chat prompt box**: a short trigger to invoke the extraction once the sources are loaded.

You configure (1) once per notebook. You paste (2) each time you want extraction output — (2) is a three-stage flow: extraction, then synthesis, then clustering.

Companion: `99_System/EXTRACT_PROMPT.md` is for the *after-a-Claude-conversation* gem-extraction case. Different file, different purpose.

The `Suggested MOC` field is free-text — the human reviewer maps it to a specific vault MOC stem before moving the extracted file from `00_Inbox/Note Stock/` to `00_Inbox/Note Pipe/`.

---

## (1) Custom Instructions — paste into "Configure notebook"

Sized under NotebookLM's 10,000-character limit. If you extend it, verify the length with:
```powershell
(Get-Content "$env:VAULT_ROOT\99_System\EXTRACT_PROMPT_NotebookLM.md" -Raw -Encoding UTF8 | Select-String -Pattern '(?ms)^```\s*\n(.*?)\n```').Matches[0].Groups[1].Value.Length
```

```
Knowledge extraction engine. Output feeds a PKM pipeline (process-inbox → concept notes → MOC patches → diagram generation → flashcards). Every label below maps to a downstream parser. Be precise, dense, machine-readable. No preamble or commentary outside blocks.

A concept qualifies if it has: falsifiable claim + named mechanism + application context + failure mode. Only 2 of 4 → extract with [NONE] for the rest. Only 1 or 0 → skip. A dense book = 15-30 blocks. Under-extraction is worse than over — but a block count is never a target: never invent or pad a block to reach one. Thin source, few blocks; empty source, see the ABORT rule.

EDGE VOCABULARY (closed, exact spelling):
  supports          A strengthens or evidences B
  contradicts       A and B make incompatible claims
  prerequisite-for  A must exist before B works
  instance-of       A is a concrete case of abstract B
  mechanism-of      A is the causal mechanism of B
  mitigates         A reduces impact of B
  related-to        fallback only; overuse degrades the diagram

No invented labels (no "enables", "depends-on", "causes"). If none of the 7 fits, omit the edge.

DIRECTION (critical — the diagram draws the arrow from this): every edge reads THIS concept -> the named concept. "supports X" means THIS concept supports X, never the reverse. Only contradicts and related-to are symmetric; the other five have NO inverse in this vocabulary. So if the source says X is the prerequisite for this concept, do NOT restate it here — emit it from X's own block, where X is the subject. If X is not extracted in this run, omit the edge. Never emit an edge whose subject is not the block you are writing.

CLUSTER RULE: A cluster is a group bound by ONE shared mechanism, sized 3-7 (ceiling 9, never 1). Within a cluster at least one pair must link by a load-bearing edge — instance-of, mechanism-of, prerequisite-for, or mitigates. supports/contradicts/related-to alone make a "list with no lines", which the diagram rejects. A concept whose strongest links point into another cluster belongs in that cluster. Per-block cluster names are provisional guesses; stage 3 (synthesis) finalises them with all concepts visible.

ACRONYM RULE: first use in a block, expand inline e.g. "MFA (Multi-Factor Authentication)". Bare acronym after that.

PER-BLOCK FORMAT — every label exactly. Use [NONE] when honest, never invent.

---
Concept title: [3-6 words. Safe chars: A-Z a-z 0-9 space - ' ( ) . , &. No colons/slashes/quotes/em-dash.]
Stem (safe): [Title with spaces→_, apostrophes/periods stripped, "&"→"and", consecutive _ collapsed. Equals filename without .md.]
Icon: [single emoji]
Aliases:
  - [short colloquial name or acronym]
  - [alternative framing of the mechanism]
Description: [one sentence, plain language, no jargon. Becomes the YAML description field.]
Suggested MOC: [1-3 words for topic area, e.g. "Azure platform", "writing structure". Human reviewer maps to a vault MOC.]
Suggested cluster (provisional): [2-5 evocative words naming a SHARED MECHANISM, not a topic bag. This is a guess from one block; the synthesis pass (stage 3) reassigns authoritatively with all concepts visible. Test: could every member be instance-of or mechanism-of the same idea?]
Tier: [atomic | meta-organising]
  atomic = single mechanism, lives as a node inside a cluster.
  meta-organising = umbrella concept that multiple atomic concepts are instance-of.
Possible overlap: [stem of another concept IN THIS RUN covering the same mechanism, OR [NONE]. Intra-batch dedup; no vault access.]
Tags: [2-3 lowercase-hyphen tags, comma-separated. Search words, not a title restatement.]

## Core Idea (Summary)
[1-2 sentences. ONE assertive falsifiable claim. NOT a topic label. Acronyms expanded inline on first use.]

**Example:** [one concrete named example from source. NOT hypothetical. [NONE] if source provides none.]

**Metaphor:** [one metaphor from source. EXACT label "**Metaphor:**" required for downstream regex. [NONE] if source uses none — do NOT invent.]

## Mechanism (Key details)
- [bullet — specific mechanism, causal chain, named study, or named data. Concrete; no hedging.]
- [bullet]
- [3-5 bullets before the boundary]
- **Boundary condition:** [specific circumstance under which the claim breaks down. ONE labelled bullet. [NONE] only if source genuinely has none.]

## Application
- **When to use:** [named scenario, not vague.]
- **When NOT to use:** [named counter-case where applying this is wrong; not the simple inverse.]
- **Counter-instance:** [NAMED historical case where the concept's prediction failed. Distinct from "When NOT to use". [NONE] if source has none — most blocks will.]

## Debate
[1-3 sentences. What prior assumption or competing view does this challenge? Who would disagree, and why? If source treats this as uncontested, write exactly: "Source presents this as uncontested." — do NOT manufacture a debate.]

## Typed edges
[Edges to OTHER concepts in THIS run. One line per edge. The subject is ALWAYS this block's concept (see DIRECTION). Format:
  [label] [Other Concept Title] | quote: "verbatim source sentence" | confidence: [HIGH | MEDIUM]
reads as: THIS concept --[label]--> Other Concept Title
HIGH = source explicitly states the relationship. MEDIUM = strongly implies but does not state. Else omit. NO cross-source edges. If none: "[NONE — no in-source relationships]"]

## Source
- Filename: [exact filename with extension]
- Location: [chapter / section / page range. "passim" only if it recurs throughout.]
---

OUTPUT RULES
- Blocks are self-contained. Do NOT merge two mechanisms into one block.
- Every field present (use [NONE] honestly).
- Edges reference only same-run concepts, with THIS concept as the subject.
- Flag inline: [SOURCE CONFLICT: A claims X, B claims Y] or [APPLICATION UNCLEAR — agent will infer].
- No preamble, no closing summary, no inter-block commentary.
- "---" separators between blocks, exactly as shown.
- ABORT: if the source text contains NO concept meeting the 2-of-4 threshold, output exactly and only:
  [NO QUALIFYING CONCEPTS EXTRACTED - INSUFFICIENT DENSITY]
  and nothing else. This is a correct, expected result for prefaces, forewords, acknowledgements, narrative or biographical passages, and front matter. A forced block is a defect; an abort is not.
- NO NESTED HEADERS. Never start a line with "#", "##" or "###" inside field content. The only headers permitted are the exact "## " section names in the per-block format. Do not invent sub-headings to organise bullets — a downstream regex splits sections on a line starting "## ", so an extra header silently truncates the block.
- NO RAW PIPES IN QUOTES. The edge line is pipe-delimited. If the verbatim sentence you want to quote contains "|", quote a different sentence or trim to a pipe-free span. Never alter the words inside a quote to remove one.

WORKED EXAMPLE — format reference. Do NOT include in your output.

---
Concept title: Multi-Factor Authentication
Stem (safe): Multi-Factor_Authentication
Icon: 🔐
Aliases:
  - MFA
  - Two-Factor Verification
Description: Requires at least two independent credential categories so a stolen password alone is insufficient.
Suggested MOC: Azure platform
Suggested cluster: Identity and Access
Tier: atomic
Possible overlap: [NONE]
Tags: identity, security, authentication

## Core Idea (Summary)
Multi-Factor Authentication (MFA) requires at least two independent categories of credentials to verify an identity, so that a stolen password alone is insufficient for access.

**Example:** Microsoft Entra MFA prompting users via the Authenticator app push notification after they submit a password.

**Metaphor:** Two locks on the same door, where the keys live in different pockets.

## Mechanism (Key details)
- Factors split into three categories: something you know (password), something you have (mobile or hardware token), something you are (biometric).
- The factors must be INDEPENDENT — a password and a security question delivered to the same email are still effectively one factor.
- Microsoft Entra MFA can be enforced unconditionally or selectively via Conditional Access policies.
- **Boundary condition:** Breaks down when two factors are compromised together (laptop and linked phone stolen) or through "MFA fatigue" attacks where users blindly approve push prompts.

## Application
- **When to use:** Protecting administrative accounts or sensitive data where the risk of unauthorised access is high.
- **When NOT to use:** Automated service accounts that cannot interact with a phone or biometric — use Managed Identities instead.
- **Counter-instance:** [NONE]

## Debate
Contradicts the "a strong password is sufficient" assumption that dominated pre-2010 access policy. Critics argue MFA introduces friction; the counter is that adaptive Conditional Access removes friction where risk is low.

## Typed edges
- mitigates Credential Theft Attack | quote: "Stolen passwords alone no longer grant access if MFA is enforced." | confidence: HIGH
- prerequisite-for Single Sign-On Productive Use | quote: "When SSO is paired with MFA, the second factor is requested once per session, not per application." | confidence: MEDIUM

## Source
- Filename: AZ-900 - Microsoft Learn.pdf
- Location: Module 4, section 4.2 (pages 87-91)
---
```

---

## (2) Chat triggers — paste in the chat box

The chat box drives a three-stage run. Stages 1-2 are not character-capped (only the Custom Instructions spec is), so the heavy synthesis/clustering logic lives here, not in the spec.

  Stage 1 — Extraction: emit one concept block per teachable idea.
  Stage 2 — Synthesis: connect concepts the per-block edges missed (whole-notebook view).
  Stage 3 — Clustering: assign every concept to a well-formed cluster and validate it.

### Stage 1 — Extraction

Pick one of the following (any will work; pick the one that matches the current source's scope):

**All sources at once:**
```
Run the extraction defined in this notebook's custom instructions across every loaded source. Emit one block per distinct teachable concept, separated by "---". Begin.
```

**Specific source:**
```
Run the extraction defined in this notebook's custom instructions against the source "<filename>". Emit one block per distinct teachable concept, separated by "---". Begin.
```

**Resuming a partial run:**
```
Continue the extraction. Pick up where you left off; do not re-emit concepts already produced in this chat.
```

### Stage 2 — Synthesis

Paste once Stage 1 has emitted all blocks. Cross-concept relationships only become visible with every concept on the table; the per-block "Typed edges" field cannot see them (at block N, blocks N+1..end do not exist yet).

```
Synthesis pass. You have now emitted all concept blocks for this notebook. Re-read every block you produced in this chat and identify cross-concept relationships that the per-block edges missed — especially edges that only become visible with all concepts in view.

Output ONLY the section below. No preamble, no re-emission of blocks.

## Cross-concept synthesis

### New typed edges
[Edges between concepts already emitted, NOT already stated in any block's "Typed edges" field. Same closed vocabulary: supports, contradicts, prerequisite-for, instance-of, mechanism-of, mitigates, related-to. One line each:
  [label] [Concept A Stem] -> [Concept B Stem] | quote: "verbatim source sentence" | confidence: [HIGH | MEDIUM]
related-to is fallback only. If a HIGH/MEDIUM edge needs no new quote because the link is structural rather than stated, use confidence: STRUCTURAL and omit the quote. If none: "[NONE]"]

### Meta-organising rollups
[For each meta-organising concept in this run, list the atomic stems that are instance-of it. Format:
  [Meta Stem]: [atomic stem], [atomic stem], ...
If an atomic concept fits no meta umbrella, leave it out. If no meta concepts: "[NONE]"]

### Contradiction clusters
[Groups of 2+ concepts making incompatible or competing claims, even across different sources. Format:
  [topic]: [Stem A] vs [Stem B] — [one-line nature of the tension]
If none: "[NONE]"]

Begin.
```

### Stage 3 — Clustering

Paste once Stage 2 is done. Clustering is a whole-notebook decision (same reason as synthesis): each block's provisional `Suggested cluster` was a guess made without sight of the others. This pass reassigns authoritatively and validates each cluster against the four health rules — the same checks `cluster_health.ps1` runs over the rendered MOC, applied here so clusters are well-formed before they ever reach a diagram.

```
Clustering pass. Using all concept blocks and the Stage 2 synthesis, assign EVERY concept in this run to a cluster. A cluster is well-formed only if it passes ALL FOUR rules:

  1. Shared principle — the cluster name states the ONE mechanism or theme every member shares (often a meta-organising concept from this run). Never "Misc", "Other", or a source title.
  2. Internal cohesion — at least one internal pair is linked by a LOAD-BEARING edge: instance-of, mechanism-of, prerequisite-for, or mitigates. A cluster held together only by supports / contradicts / related-to is a list, not a cluster — split it or merge it into a real one.
  3. Separation — every member's strongest ties stay INSIDE its cluster. If a concept has 2+ edges into one other cluster and fewer within its own, MOVE it to that other cluster.
  4. Size — 3 to 7 members ideal, 9 maximum, never 1. A lone concept joins its nearest sibling cluster, or is flagged [orphan] if none fits.

Output ONLY the section below. No preamble.

## Cluster assignment

[For each cluster:]
[Cluster Name]
  members: [stem], [stem], ...
  spine: [the load-bearing internal edge that justifies the cluster, e.g. "Spaced_Repetition mechanism-of Long_Term_Retention". A cluster that cannot name its spine fails rule 2 — fix it before listing.]

Reassignments from per-block guesses: [stem: old_cluster -> new_cluster, ...] or [NONE]
Orphans (no cluster of 3+ fits): [stem, ...] or [NONE]

Begin.
```

---

## What to do with the output

0. **If Stage 1 returns `[NO QUALIFYING CONCEPTS EXTRACTED - INSUFFICIENT DENSITY]`, stop here.** Save nothing and do not run Stages 2-3 — there is nothing to synthesise or cluster. This is a correct outcome for a preface, a narrative chapter, or front matter, not a failed run. If you believe the source *is* dense, re-run against a specific chapter rather than the whole file before concluding the prompt is at fault.
1. Save Stage 1's full response (15-30 blocks per dense source) to `00_Inbox/Note Stock/` as a `.md` file named after the source.
2. Save Stages 2-3 (`## Cross-concept synthesis` + `## Cluster assignment`) to a separate `{source}_synthesis.md` sidecar in the same folder — NOT appended to the blocks file. The block parser reads only concept blocks; keeping synthesis/clustering in a sidecar means the existing parser never sees the new sections, and the interconnect/visualise engines get a dedicated input rather than an overloaded one.
3. Skim: resolve any `[SOURCE CONFLICT]` or `[APPLICATION UNCLEAR]` flags; map each block's free-text `Suggested MOC` to a vault MOC stem. Apply the Stage 3 reassignments — they override the per-block `Suggested cluster` guesses.
4. Move the blocks file (and its sidecar) to `00_Inbox/Note Pipe/`. The next `process-inbox` run will consume the blocks block-by-block; the sidecar feeds cluster membership and cross-concept edges.
5. Understanding gate still applies: before any extracted concept becomes `status: final`, close the source and explain the mechanism and boundary aloud.

---

## Why this format (rationale)

- **Labelled fields, not narrative prose** — the flashcard extractor and visualise-moc extractor are regex-based; labels make them deterministic.
- **Closed 7-label edge vocabulary** — matches `docs/visualisation-pipeline.md`. Extracting richer edges at NotebookLM time means visualise-moc gets dense diagrams from day one.
- **Subject-first edge direction** — the per-block `Typed edges` format names only the *target*, so without a stated convention the subject is ambiguous, and the ambiguity is not resolved until three steps later: `extract_diagram_candidates.ps1` reads `- [[A]] label [[B]]` positionally (`$src` = group 1, `$tgt` = group 2) out of the MOC. An agent guessing A and B at that point draws arrows backwards. The `DIRECTION` rule fixes the subject as "this block's concept" everywhere, and the matching rule in `inbox-pipeline.md` stops the guess at the MOC-write step. Note that only `contradicts` and `related-to` are symmetric — the other five have **no inverse** in the vocabulary, so a backwards edge cannot be flipped, only re-emitted from the other concept's block or omitted.
- **The ABORT sentinel** — without an explicit escape, an LLM handed a preface or a narrative chapter will manufacture a block to satisfy the format, and the spec's own "under-extraction is worse than over" line actively rewards that. The sentinel makes "nothing here" an expressible, correct answer; the softened count line removes the incentive. A block count is a symptom of source density, never a target.
- **No nested headers, no raw pipes** — both are parser-collision guards. `Get-Section` in `extract_flashcard_candidates.ps1` splits on a line beginning `## `, and the diagram extractor's `relH3` splits on `### `, so a sub-heading invented by the model inside a field silently truncates everything after it. The pipe rule protects the edge line's own `|` delimiter. In both cases the instruction is to *choose different content*, never to alter a verbatim quote — a quote that must be edited to fit the format is the wrong quote.
- **Verbatim quote per edge** — provenance captured once; reviewers later see the source justification without reopening the PDF.
- **Free-text `Suggested MOC`** — keeps the prompt short and self-contained; reviewer maps to a vault stem at ingestion.
- **Acronym inline expansion** — defuses Phase 2's per-acronym STOP gate.
- **`Possible overlap` (intra-batch)** — NotebookLM can't see the vault, but can dedup within the same source pass.
- **Custom Instructions vs chat trigger split** — the spec is sticky (configured once); the trigger is what you paste each time. This avoids the chat-box character cap and avoids re-uploading the spec as a source file.
- **Three stages, not one** — extraction, synthesis, and clustering are sequenced because each later stage needs the full output of the earlier one. The per-block "Typed edges" field is forward-blind (at block N it cannot see N+1..end), so cross-notebook edges, contradiction clusters across sources, and cluster assignment are all structurally invisible at block time. Stages 2-3 are the only place they surface.
- **Heavy logic in the trigger, not the spec** — only the Custom Instructions block is capped at 10,000 chars. Synthesis and clustering rubrics live in the (uncapped) chat triggers, so the spec stays lean while the per-run logic stays rich. The spec carries only the compact `CLUSTER RULE` so per-block guesses are sane.
- **Clustering mirrors `cluster_health.ps1`** — the four Stage 3 rules pre-satisfy that gate's flags: internal cohesion → `list-only` (a cluster with zero structural internal edges); separation → `misplaced` (a concept pulling more edges into another cluster than its own); size → `OVERSIZED` (>9) and `singleton`. Of the 7 epistemic labels, only `instance-of`, `mechanism-of`, `prerequisite-for`, `mitigates` count as structural/load-bearing — `supports`/`contradicts`/`related-to` do not. Catching a bad cluster here is cheaper than spotting it in a rendered SVG.
- **The `spine` requirement** — forcing each cluster to name its load-bearing internal edge is what makes the *relationship* meaningful, not just the grouping. A cluster that cannot name a spine is a topic bag held together by `related-to`, which the diagram's So-What pruning would strip anyway.
