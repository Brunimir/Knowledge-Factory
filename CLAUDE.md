# PKM Agent — Claude Code Command Interface
# Place this file at the root of your Obsidian vault (your VAULT_ROOT).
# Claude Code reads it automatically at the start of every session.

---

## ENVIRONMENT

VAULT_ROOT : <set via $env:VAULT_ROOT or edit the launcher scripts>
PLATFORM   : Windows — use PowerShell for all file operations.
             Never use /mnt/c/ paths. Never use bash or sh.
INDEX_FILE : <VAULT_ROOT>\00_Inbox\VAULT_INDEX.json

All file reads and writes go through PowerShell tools (Read-Content,
Set-Content, New-Item, Get-ChildItem). If your vault lives on
cloud-synced storage, do not use file locking operations.

---

## COMMANDS

Claude Code is invoked with one of these subcommands.
Read the first word of the user's message to dispatch:

  process-inbox          → run the PKM ingestion pipeline (Phases 0–5)
                           reads from: 00_Inbox\Note Pipe\
                           writes to:  21_Concepts\, 22_Maps_of_Content\
                           note: a concept's `moc:` field is a LIST — a note may be
                                 mapped into several MOCs; patch every relevant one.

  verify-capture-fidelity → judge each unjudged CHECKABLE block in
                           00_Inbox\CAPTURE_FIDELITY.json against its frozen
                           source in 30_Sources\, writing a
                           faithful/drifted/fabricated/unverifiable verdict.
                           While both sides are open it also reviews that
                           block's Example/Metaphor — adds one if missing,
                           proposes a stronger one (from the source) if the
                           captured one is weak — patched into the Note Pipe
                           file itself, since process-inbox reads that file,
                           never the JSON.
                           Runs AUTOMATICALLY as the first agent action of
                           launch-process-inbox.ps1, before process-inbox
                           itself starts, whenever the manifest has an
                           unjudged block. Also runnable standalone to clear
                           the queue ahead of a batch, or to re-check after
                           editing a Note Pipe file.
                           reads from: 00_Inbox\CAPTURE_FIDELITY.json,
                                       30_Sources\, 00_Inbox\Note Pipe\
                           writes to:  00_Inbox\CAPTURE_FIDELITY.json
                                       (verdict field only, per block);
                                       00_Inbox\Note Pipe\*.md (Example/
                                       Metaphor line only, per block changed)
                           see skill: 99_System\Claude\pkm-capture-verify\SKILL.md

  generate-flashcards    → generate Anki flashcards from status:final concept notes
                           reads from: 20_Learning\21_Concepts\ (status:final AND flashcards:false)
                           writes to:  20_Learning\23_FlashCards\  (Flashcards_{moc_stem}.md)
                           format: flashcards-obsidian plugin (`- Question :: Answer`, up to 6 per note)

  pkm-solution           → draft a Phase 5 artefact (Pattern or Solution)
                           reads from: 00_Inbox\VAULT_INDEX.json → 21_Concepts\,
                                       10_Ideas\, 40_Solutions\ (selective; index-first)
                           writes to:  40_Solutions\
                           see skill: 99_System\Claude\pkm-solution\SKILL.md

  vault-health           → audit wikilinks, orphans, used_in counts,
                           vault gaps (acronyms), and MOC coverage.
                           See pkm-review skill.
                           reads from: VAULT_INDEX.json + targeted note reads
                           writes to:  00_Inbox\VAULT_HEALTH_REPORT.md
                                       00_Inbox\VAULT_GAPS_REPORT.md
                           see skill: 99_System\Claude\pkm-review\SKILL.md

  visualise-moc {stem}   → render the Mermaid concept-map for one MOC
                           (two tiers: overview + cluster detail).
                           reads from: VAULT_INDEX.json + the per-MOC
                                       manifest at 00_Inbox\DIAGRAM_CANDIDATES_{stem}.json
                                       (pre-extracted by extract_diagram_candidates.ps1)
                           writes to:  20_Learning\24_Diagrams\Diagram_{stem}.md
                                       (full overwrite, idempotent)
                                       + surgical patch to the MOC's ### Cluster Map subsection
                           see spec: docs\visualisation-pipeline.md

  weave-links {scope}    → discover and record cross-domain relationships
                           between concept notes that live in different MOCs
                           (a retroactive interconnection pass, distinct from
                           process-inbox Phase 4, which only routes new notes)
                           scope: one or more MOC stems (run via
                                  launch-weave-links.ps1 -MocStems A B [...],
                                  which pre-builds the candidate manifest at
                                  the same 0.70 dense-cosine floor
                                  process-inbox uses — see PHASE IC-2)
                           reads from: VAULT_INDEX.json,
                                       00_Inbox\WEAVE_CANDIDATES.json + the
                                       source concept notes backing surviving
                                       candidate edges
                           writes to:  the `## Cross-Domain Links` section of
                                       the in-scope MOCs ONLY — never concept
                                       notes (status:final notes are locked)
                           see spec: docs\interconnect-pipeline.md

  extract-gems           → identify vault-worthy "gems" from THIS conversation
                           and route each: new candidate / one-line refinement /
                           exclude. Conversation-scoped (not index-first), so the
                           index staleness gate does not apply.
                           writes to:  00_Inbox\AI_Candidates\  (new candidates)
                                       or a one-line bullet on an existing concept
                           see skill: 99_System\Claude\gem-extraction\SKILL.md

  vault-query {question} → answer an ad-hoc vault question with a CITED,
                           synthesised answer, or admit the vault has nothing on
                           it. Hybrid retrieval (dense bge-micro-v2 + sparse BM25,
                           fused with RRF) over a gitignored, rebuildable shadow
                           index. READ-ONLY — never writes a vault note. Cites
                           every claim as [[stem]] and never fabricates.
                           corpus: 21_Concepts, 22_Maps_of_Content, 40_Solutions,
                                   10_Ideas (Note Pipe excluded)
                           see skill: 99_System\Claude\vault-retrieval\SKILL.md

If no subcommand is recognised, ask the user which command they meant.
Do not guess. Do not run the ingestion pipeline by default.

---

## MODEL DISPATCH

Each command below is intended to run on a specific model, chosen to trade
capability against cost for that command's blast radius:

  | Command                 | Model  | Why                                          |
  | process-inbox           | opus   | high blast radius: autonomous concept writes |
  | verify-capture-fidelity | sonnet | constrained per-block judgment; invention forbidden |
  | generate-flashcards     | sonnet | constrained compression; invention forbidden |
  | pkm-solution             | opus   | open synthesis; the output IS the product    |
  | weave-links              | sonnet | human confirms every edge before write       |
  | vault-health (pkm-review)| haiku | triage/narration of script-computed signals  |
  | visualise-moc            | —     | fully deterministic; no agent invoked        |

The `Skill`/slash-command invocation does NOT switch the model — it loads the
instructions and tool allowlist but runs on whatever model the current session
uses, silently ignoring a skill's `model:` frontmatter. To honour the intended
model, invoke the command on a session already running that model, or dispatch
it explicitly on that model (an `Agent`-style tool with a `model:` parameter,
or `claude --model <name>` from a launcher script).

---

## BEFORE EVERY RUN

State briefly: which command, how many notes/files in scope, which MOCs will be affected.
If anything is ambiguous (unknown subcommand, missing files, unclear intent), ask — do not guess or proceed with defaults.

If the request has multiple plausible interpretations, NAME EACH ONE
and ask which is meant. Do not pick silently. Example: "build me a
deck on X" could mean (a) a composite Solution with a .pptx companion,
(b) a doc Solution with a markdown outline, (c) a Pattern abstracting
the slide-building approach. State all three and let the human pick.

---

## BEFORE EVERY process-inbox RUN

Confirm that VAULT_INDEX.json was generated today:
  Read the "generated" field from VAULT_INDEX.json.
  If it is not today's date, print:
    "⚠ Index is from {date}. Run generate_index.py first, then retry."
  and stop. Do not proceed with a stale index.

---

## BEFORE EVERY verify-capture-fidelity RUN

verify-capture-fidelity does NOT use the staleness gate above: it never reads
VAULT_INDEX.json, only 00_Inbox\CAPTURE_FIDELITY.json and 30_Sources\. No
pre-run step — read the manifest, judge only the unjudged CHECKABLE blocks,
write verdicts. See 99_System\Claude\pkm-capture-verify\SKILL.md.

This step has no "STOP and wait for human" branch: judge, optionally improve
a teaching aid, report — never ask a question mid-task. If a block's fidelity
genuinely can't be judged, its verdict is `unverifiable` — that IS the
"I need a human" signal.

---

## BEFORE EVERY pkm-solution RUN

Same staleness gate as process-inbox: read the "generated" field from
VAULT_INDEX.json. If it is not today's date, print:
  "⚠ Index is from {date}. Run generate_index.py first, then retry."
and stop. Phase 5 retrieval is index-first — a stale index will surface
deleted notes and miss new ones.

Then restate the user's brief in one sentence and name the chosen artefact
type (Pattern or Solution) before any file read. If the brief
is unclear or the type ambiguous, ask — do not guess.

---

## BEFORE EVERY visualise-moc RUN

Same staleness gate: read the "generated" field from VAULT_INDEX.json.
If it is not today's date, print:
  "⚠ Index is from {date}. Run generate_index.py first, then retry."
and stop.

Then check the per-MOC diagram manifest at
00_Inbox\DIAGRAM_CANDIDATES_{stem}.json. If missing OR its `generated`
field is not today, print:
  "⚠ Manifest stale or missing. Re-run launch-visualise-moc.ps1
   (it will rebuild the manifest before invoking the agent)."
and stop.

Then check 00_Inbox\MMDC_MODE.txt — it must contain "global" or "npx".
If absent, the launcher's mmdc doctor check did not run. Print:
  "⚠ MMDC_MODE.txt missing. Run launch-visualise-moc.ps1, not the
   agent directly."
and stop. The agent uses this sentinel to know whether to call `mmdc`
or `npx -y @mermaid-js/mermaid-cli` for the V-4 validation loop.

---

## BEFORE EVERY weave-links RUN

weave-links should be invoked via `launch-weave-links.ps1 -MocStems A B [...]`,
not by asking the agent directly. The launcher regenerates the index, validates
every MOC stem, requires at least two, and builds
00_Inbox\WEAVE_CANDIDATES.json (`overlap_candidates.py weave` — the same
dense-cosine 0.70 floor `generate()` uses for process-inbox) BEFORE the agent
starts. If a human asks the agent to run weave-links directly with domain names
instead, resolve each domain to its MOC stem(s), list them back, and tell the
human to run the launcher with those stems — do not fall back to generating
candidates yourself (PHASE IC-2 in docs/interconnect-pipeline.md depends on the
manifest existing for this exact scope).

Then restate the scope in one sentence — which MOCs the manifest covers, and
how many cross-MOC candidates it surfaced — before any file read beyond the
index and the manifest.

weave-links NEVER writes to a concept note. Every discovered edge lands in a
MOC's ## Cross-Domain Links section — Safety Rule #6 stands, because most
cross-domain targets are status:final concept notes.

---

## WINDOWS FILE OPERATION PATTERNS

Use these exact PowerShell patterns. Do not improvise alternatives.

READ a file:
  Get-Content "$env:VAULT_ROOT\path\to\file.md" -Raw -Encoding UTF8

LIST files in a folder:
  Get-ChildItem "$env:VAULT_ROOT\00_Inbox\Note Pipe" -Filter "*.md"

WRITE a new file (concept note):
  $content = @'
  {full file content here}
  '@
  Set-Content -Path "$env:VAULT_ROOT\21_Concepts\Stem_Name.md" `
              -Value $content -Encoding UTF8

APPEND to an existing file (MOC patch):
  $patch = @'
  {patch content here}
  '@
  Add-Content -Path "$env:VAULT_ROOT\22_Maps_of_Content\MOC_Name.md" `
              -Value $patch -Encoding UTF8

PATCH a specific section (replace a line in an existing file):
  $file = "$env:VAULT_ROOT\22_Maps_of_Content\MOC_Name.md"
  $content = Get-Content $file -Raw -Encoding UTF8
  $content = $content -replace 'note_count: \d+', 'note_count: {new_value}'
  Set-Content -Path $file -Value $content -Encoding UTF8

MOVE a file to QUARANTINE:
  Move-Item -Path "$env:VAULT_ROOT\00_Inbox\Note Pipe\file.md" `
            -Destination "$env:VAULT_ROOT\00_Inbox\QUARANTINE\file.md"

MOVE a fully processed file to Z_Note bin (after final batch):
  Move-Item -Path "$env:VAULT_ROOT\00_Inbox\Note Pipe\file.md" `
            -Destination "$env:VAULT_ROOT\00_Inbox\Z_Note bin\file.md"

CHECK if file exists:
  Test-Path "$env:VAULT_ROOT\path\to\file.md"

---

## FINAL CRITERIA GATE (used by process-inbox and generate-flashcards)

A note is eligible for status:final when the human has confirmed
all three in a single review pass:
  1. Core idea statable from memory in one sentence (retrieval test)
  2. All wikilinks resolve and make sense in context
  3. At least one real situation named in Application where it applies

The agent NEVER sets status:final automatically.
The agent leaves new notes at status:draft after successful write.
The human sets status:final after their review pass.
generate-flashcards only processes status:final notes.

CONCEPT RESTING STATES (no review SLA — the human is not a bottleneck):
  • draft        — the agent-written AND human-drafted resting state, and a
                   valid PERMANENT one: no time limit. A concept may stay draft
                   forever (a reference note, or content never chosen for study),
                   or rest as an agent-written note awaiting an OPTIONAL human
                   pass. Never treated as stale or nagged. The human promotes the
                   notes they choose; the rest rest indefinitely.
  • final + flashcards:false — approved; flashcards pending generation.
  • final + flashcards:true  — terminal. Either the cards were generated, OR
                   the human set flashcards:true by hand to opt the note out
                   of studying ("reviewed, no need to study"). Either way no
                   flashcards are (re)generated and it is never flagged.
  vault-health surfaces only actionable notes (final + flashcards:false); it
  never nags about a draft backlog. As gem-extraction grows vault volume, this
  keeps the human off the critical path. (There is no needs-review status —
  any legacy needs-review notes map to draft.)

See docs/lifecycle.md for the full artefact-lifecycle reference.

---
## PROCESS-INBOX PIPELINE — see docs/inbox-pipeline.md

The full PHASE 0–5 definitions for the `process-inbox` command live in:
  docs/inbox-pipeline.md

When the user invokes `process-inbox`, READ that file first, then
execute the phases as defined there. Do NOT load it for any other
command (process-inbox is the only consumer). The shared gates above
(BEFORE EVERY process-inbox RUN, FINAL CRITERIA GATE) still apply
and remain in this file.

## VISUALISE-MOC PIPELINE — see docs/visualisation-pipeline.md

The full PHASE V-0 → V-6 definitions for the `visualise-moc` command
live in:
  docs/visualisation-pipeline.md

When the user invokes `visualise-moc {MOC_stem}`, READ that file first,
then execute the phases as defined there. Do NOT load it for any other
command. The shared gates above (BEFORE EVERY visualise-moc RUN, SAFETY
RULES, WINDOWS FILE OPERATION PATTERNS) still apply and remain in this
file.

The diagram file at 20_Learning\24_Diagrams\Diagram_{stem}.md is the ONE
place in the system where a full-file overwrite is correct on every run
— the file is fully derivable from the manifest and is regenerated
idempotently. Concept notes and MOCs are still patched surgically;
Safety Rule #6 stands for status:final concept notes.

## PKM-SOLUTION PIPELINE — see 99_System\Claude\pkm-solution\SKILL.md

The full Phase 5 (Output Bridge) definitions for the `pkm-solution`
command live in:
  99_System\Claude\pkm-solution\SKILL.md

When the user invokes `pkm-solution` (or `/pkm-solution`), READ that
file first, then execute the phases as defined there. Do NOT load it
for any other command. The shared gates above (BEFORE EVERY
pkm-solution RUN, SAFETY RULES, WINDOWS FILE OPERATION PATTERNS) still
apply and remain in this file.

Reference for the Phase 5 process as a whole (artefact types, templates,
validation rules) is the human-readable spec at:
  40_Solutions\Personal Knowledge Management System - Solution.md

The skill file is the authoritative agent spec; the spec doc is the
human reference. (The spec doc lives in 40_Solutions/ as a Solution
because it IS the realised PKM system, not merely a hypothesis.)

## WEAVE-LINKS PIPELINE — see docs/interconnect-pipeline.md

The full PHASE IC-0 → IC-6 definitions for the `weave-links` command live
in:
  docs/interconnect-pipeline.md

When the user invokes `weave-links` (with a scope of MOC stems or domains),
READ that file first, then execute the phases as defined there. Do NOT load
it for any other command. The shared gates above (BEFORE EVERY weave-links
RUN, SAFETY RULES, WINDOWS FILE OPERATION PATTERNS) still apply and remain in
this file.

weave-links is the only command that retroactively connects notes already in
the vault. Its discovered edges live exclusively in MOC ## Cross-Domain Links
sections, in the canonical prose-verb format
([[A]] <label> [[B]] (in [[MOC_X]])) using the closed 7-label vocabulary.
Safety Rule #6 stands: concept notes are never edited by this pipeline.

════════════════════════════════════════════════════════════════
SAFETY RULES (enforced at every write operation)
════════════════════════════════════════════════════════════════
1. Never overwrite a vault file's full content. Patch only the
   specific section being changed.

2. A wikilink is valid only if the exact text exists in
   VALID_NOTES, VALID_MOCS, or VALID_EXTERNAL_MOCS.

3. When processing a batch, check each new note's title against
   all other new titles in the same batch — not just the index.
   A note written in this batch is a valid wikilink target for
   other notes in the same batch.

4. Never delete an inbox file. Move fully processed files to
   00_Inbox\Z_Note bin\ only — do not delete them.

5. Never write a note that would create a broken wikilink in an
   existing MOC. If the MOC references a title that does not yet
   exist in VALID_NOTES, add it to the MOC as plain text with
   (not yet in vault: "Title") — do not write [[Title]].

6. NEVER modify a concept note that has status:final unless the
   user explicitly asks for that specific change. The ONLY edits
   allowed to a status:final note during any pipeline are:
     a. flashcards: false → flashcards: true   (PHASE GF-3 patch)
     b. updated: <prior date> → updated: <today>   (PHASE GF-3 patch)
     c. source_count: / trust: — the trust patch, applied ONLY by
        concept_schema_sync.ps1 (source_count = number of [[wikilinks]]
        on the note's "- Source" line; trust is derived from it — see
        the script's own docstring for the formula).
   No other change is permitted — not formatting, not structure,
   not "fixing" labels, not adding/removing sections, not
   prepending frontmatter, NOTHING. If a status:final note is
   structurally malformed (missing fields, legacy labels), SKIP
   it and report the issue. Do not silently auto-correct.

   When patching, use targeted regex replacements that match the
   exact line being changed. Never use file rewrites or full-file
   templating that could re-emit the file in a different shape.
   Always Test-Path the original to confirm shape before writing.

7. NEVER MAKE INFORMATION UP. ALWAYS REFER TO THE EXISTING INFO.
   When generating any derivative content from vault notes -
   flashcards, summaries, MOC entries, cross-domain links, reports
   - every factual claim, metaphor, boundary condition, example,
   and "when to use" recommendation MUST originate from the source
   note. Do not embellish, do not interpolate, do not "fill gaps"
   with plausible-sounding content. If a field is empty in the
   source, either omit the corresponding part of the output or
   skip the item entirely. Hallucinated content that ends up in a
   flashcard or MOC is worse than missing content because the user
   then learns and references something false.

8. SURGICAL CHANGES ONLY. Every changed line must trace directly to
   the user's request. Do not "fix" adjacent code, comments,
   formatting, or unrelated files while doing other work. If you
   notice something unrelated that needs fixing, mention it - do
   not silently change it. When patching an existing file, prefer
   targeted edits over full-file rewrites even if both produce the
   same end state: the diff itself is part of the audit trail, and
   a smaller diff is easier to review, revert, and trust. Also do
   not expand scope beyond what was asked - if the user said "add
   X", do not also add Y because Y "would be nice"; ask first.

## GENERATE-FLASHCARDS PIPELINE — see docs/flashcards-pipeline.md

The full PHASE GF-0 → GF-4 definitions for the `generate-flashcards`
command live in:
  docs\flashcards-pipeline.md

When the user invokes `generate-flashcards`, READ that file first, then
execute the phases as defined there. Do NOT load it for any other
command. The card-writing rules are in
99_System\Claude\pkm-flashcards\SKILL.md.
