---
name: extract-gems
description: Identifies vault-worthy "gems" produced during a conversation with Claude and routes each to the right destination - a new AI_Candidate, a one-line refinement of an existing note, or exclude. Use when the user asks to extract or capture gems, run the gem-capture / gem-identification process, check whether a conversation produced something vault-worthy, or formalise an insight into the vault; also offer it proactively at the end of a substantive conceptual conversation. Do NOT fire for coding tasks, drafting help, sanity checks, or short (<20-message) chats.
---

# extract-gems - post-conversation gem identification

Turns insight produced in a Claude conversation into vault artefacts, conservatively.
This skill supplies the *when* and the *routing* around the canonical prompt and
candidate template in `99_System/EXTRACT_PROMPT.md` - read that file; do not duplicate
its template here.

Conversation-scoped, not index-first: it reasons over THIS chat, verifies any vault
references by direct read, and writes at most one candidate file plus (optionally) one
one-line note patch. A stale VAULT_INDEX.json therefore does NOT block this skill - the
staleness gate exists to protect index-first retrieval, which this is not.

## When to run

Fire on an explicit request ("extract/capture gems", "run gem capture", "is this
vault-worthy", "formalise this insight"), or offer proactively after a substantive
conceptual conversation. Apply the heuristic honestly first: did the conversation
produce something the user could not have articulated at the start - genuinely new in
framing, mechanism, or connection - not a synthesis of what they already knew, and not a
nicely-worded version of an existing idea? Most conversations fail this bar; that is the
expected outcome.

Do NOT fire for: coding/drafting/sanity-check sessions; conversations where Claude only
restated the user's own input; chats under ~20 messages; or where the insight feels like
agreeableness rather than substance.

## How to run

**G-0 Heuristic gate.** Apply the bar above. If nothing clears it, output exactly:
`Nothing in this conversation rises to vault-worthy. Reasons: [brief]` and stop.

**G-1 Distill.** Write each surviving idea as a one/two-sentence decontextualized
statement in the user's voice.

**G-2 Vault dedup check.** For each candidate, name the closest existing concept note(s)
/ MOC and read them directly to confirm. This is the step that prevents
reworded-existing-idea pollution.

**G-3 Disposition and route.** Classify each candidate per the table in
`EXTRACT_PROMPT.md` -> Disposition and Routing:
- **New** - nothing covers it -> one sharpest candidate to `00_Inbox/AI_Candidates/`.
- **Refinement** - sharper/extended version of an existing concept -> one-line patch on
  that note (not a new candidate).
- **Already captured** - written into an artefact during this same conversation -> exclude.
- **Operational / tooling** - about the PKM machinery, not domain knowledge -> propose a
  `CLAUDE.md`/`SKILL.md` edit, not a vault note.

**G-4 Write.**
- *New*: file `00_Inbox/AI_Candidates/YYYY-MM-DD-{slug}.md` using the EXTRACT_PROMPT.md
  template (`status: proposed`, `source: claude-chat-YYYY-MM-DD`). `Test-Path` first;
  never overwrite. AI_Candidates is not scanned by generate_index.py - no index churn.
- *Refinement*: guarded literal patch on the concept note - add one bullet **before** the
  `**Boundary condition:**` line in `## Mechanism`, bump `updated`. Confirm the anchor
  matches exactly once before writing. **Only if `status: final` is NOT set**; for a final
  note add a `## Cross-Domain Links` entry on its MOC instead.
- *Exclude / tooling*: report only, or draft the CLAUDE.md/SKILL.md change.

**G-5 Report and stop.** List each candidate and its disposition. New candidates wait for
the user's weekly review - never promote into `21_Concepts/` here (that is process-inbox's
job, after the cooling period).

## Safety
- One sharpest New candidate only; demote the rest to Refinement or Exclude.
- Precision over recall - default to Exclude when unsure.
- Never edit a `status: final` concept note (CLAUDE.md Safety Rule 6).
- PowerShell `Set-Content -Encoding UTF8`; literal guarded patches; never full-file rewrites.
- Do not run the inbox pipeline and do not set `status: final`.
