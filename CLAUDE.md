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

  generate-flashcards    → generate Anki flashcards from status:final concept notes
                           reads from: 20_Learning\21_Concepts\ (status:final AND flashcards:false)
                           writes to:  20_Learning\23_FlashCards\  (FC_{stem}.md)
                           format: flashcards-obsidian plugin (4 #card headings per note)

  pkm-solution           → draft a Phase 5 artefact (Pattern, Solution, or Decision)
                           reads from: 00_Inbox\VAULT_INDEX.json → 21_Concepts\,
                                       10_Ideas\, 40_Solutions\ (selective; index-first)
                           writes to:  40_Solutions\
                           see skill: 99_System\Claude\pkm-solution\SKILL.md

  vault-health           → audit wikilinks, orphans, used_in counts,
                           expiring decisions, vault gaps (acronyms),
                           and MOC coverage. See pkm-review skill.
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
                           scope: one or more MOC stems or domain names
                           reads from: VAULT_INDEX.json + the source concept
                                       notes backing surviving candidate edges
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

If no subcommand is recognised, ask the user which command they meant.
Do not guess. Do not run the ingestion pipeline by default.

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

## BEFORE EVERY pkm-solution RUN

Same staleness gate as process-inbox: read the "generated" field from
VAULT_INDEX.json. If it is not today's date, print:
  "⚠ Index is from {date}. Run generate_index.py first, then retry."
and stop. Phase 5 retrieval is index-first — a stale index will surface
deleted notes and miss new ones.

Then restate the user's brief in one sentence and name the chosen artefact
type (Pattern, Solution, or Decision) before any file read. If the brief
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

Same staleness gate: read the "generated" field from VAULT_INDEX.json.
If it is not today's date, print:
  "⚠ Index is from {date}. Run generate_index.py first, then retry."
and stop. Cross-domain discovery is index-first — a stale index will
surface deleted notes and miss new ones.

Then restate the scope in one sentence — which MOCs (or domains) will be
woven together — before any file read beyond the index. If the scope is
missing, or a named domain maps to several MOCs, ASK; do not guess. A weave
needs at least two MOCs.

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
The agent sets status:needs-review after successful write.
The human sets status:final after their review pass.
generate-flashcards only processes status:final notes.

CONCEPT RESTING STATES (no review SLA — the human is not a bottleneck):
  • draft        — valid PERMANENT state, no time limit. A concept may stay
                   draft forever (a reference note, or content never chosen
                   for study). Never treated as stale.
  • needs-review — agent-written, awaiting an OPTIONAL human pass. Also no
                   time limit and never nagged. The human promotes the notes
                   they choose; the rest rest indefinitely.
  • final + flashcards:false — approved; flashcards pending generation.
  • final + flashcards:true  — terminal. Either the cards were generated, OR
                   the human set flashcards:true by hand to opt the note out
                   of studying ("reviewed, no need to study"). Either way no
                   flashcards are (re)generated and it is never flagged.
  vault-health surfaces only actionable notes (final + flashcards:false); it
  never nags about a draft or needs-review backlog. As gem-extraction grows
  vault volume, this keeps the human off the critical path.

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

════════════════════════════════════════════════════════════════
GENERATE-FLASHCARDS PIPELINE
════════════════════════════════════════════════════════════════

DESIGN
  Output is per-MOC per batch. The first run for an MOC writes
  Flashcards_{moc_stem}.md; every subsequent run writes a NEW
  file named "Flashcards_{moc_stem} - Batch {N}.md" (N = 2, 3, ...).
  Never append to, rewrite, or reorder cards in a previously
  written flashcard file. The flashcards-obsidian plugin inserts
  <!--ID:nnn--> markers after each card on first Anki sync;
  appending to a file that has already been synced (or that the
  plugin thinks it has synced) triggers the AnkiConnect silent-
  fail duplicate trap, which leaves new cards out of Anki without
  surfacing an error. One file per batch isolates each sync.
  Folder-based deck routing keeps every batch file in the same
  Anki sub-deck regardless of filename.

  Cards use the inline format with the :: separator (matches the
  plugin's inlineSeparator setting). Three dense cards per concept:
  WHAT (definition + metaphor + boundary), HOW (mechanism + key
  insight), WHEN (when to use + when NOT to use).

────────────────────────────────────────────────────────────────
PHASE GF-0 — LOAD INDEX AND IDENTIFY CANDIDATES (once per run)

  Read VAULT_INDEX.json.
  Parse VALID_NOTES as normal.

  CANDIDATES = notes where:
    status     == "final"     AND
    reviewed   == true         AND
    flashcards == false

  All three flags must be set. status:final means the note structure
  is locked; reviewed:true means the human has read it through and
  approved it for downstream use; flashcards:false means a card has
  not yet been generated. Any note missing one of the three is not
  eligible.

  If CANDIDATES is empty:
    Print: "No final reviewed notes need flashcards - nothing to process."
    Stop.

  Print: "Generating flashcards for {N} concept(s) across {M} MOCs."

────────────────────────────────────────────────────────────────
PHASE GF-1 — LOAD CANDIDATE MANIFEST (one file read, not N)

  Read the pre-extracted manifest:
    00_Inbox\FLASHCARD_CANDIDATES.json

  This file is generated by extract_flashcard_candidates.ps1 (run by
  the launch script before the agent starts). It contains every
  eligible candidate with these fields already parsed:

    stem          - filename stem (no .md)
    title         - frontmatter title
    moc_stem      - first entry in moc: list
    humanized_moc - "Learning and Memory" form (for the file header)
    description   - frontmatter description
    core          - lead prose of ## Core Idea (Summary), without the
                    **Metaphor:**/**Example:** sub-blocks
    metaphor      - extracted **Metaphor:** value, multi-line capable,
                    or null if not present (do NOT invent one)
    mechanism     - full ## Mechanism (Key details) section text
                    (includes bullets and the boundary line - the
                    boundary is also provided separately)
    boundary      - extracted **Boundary condition:** value, or null
    when_to       - extracted **When to use:** value, or null
                    (legacy fallback to **Strengths:** applied)
    when_not      - extracted **When NOT to use:** value, or null
                    (legacy fallback to **Opportunities:** /
                    **Limitations:** applied)
    is_stub       - true if the note appears to be a navigation stub
                    (core says "has been split into", description
                    matches /stub/, etc.) - the agent must ASK the
                    user before processing flagged stubs
    stub_reason   - human-readable reason the note was flagged
    has_required  - true if the minimum required fields are present:
                    title AND moc_stem AND core AND
                    (when_to OR when_not)

  DO NOT open the source .md files. Reading from the manifest is the
  entire point - it cuts ~50% of extraction-phase tokens by avoiding
  N round trips.

  If the manifest is missing or its `generated` date is not today,
  run the extraction script first:
    powershell -ExecutionPolicy Bypass -File `
      "$env:VAULT_ROOT\extract_flashcard_candidates.ps1"
  Then read the freshly written manifest.

  Eligibility recap:
    Per GF-0, a note is eligible if status:final AND reviewed:true AND
    flashcards:false. The extraction script enforces this filter.

  STUB HANDLING (interactive):
    If any candidate has is_stub == true, ASK the user before
    processing those candidates:
      "{N} note(s) flagged as navigation stubs: {list}.
       Skip these, or generate stub-cards anyway?"
    Wait for response. Default if unclear: skip.

  REQUIRED-FIELDS GATE (silent):
    For every candidate where has_required == false, log:
      "⚠ {stem}: missing {fields} - skipping."
    and skip. Do not write partial cards.

  TRUTHFULNESS RULE (applies to ALL card generation):
    NEVER make information up. NEVER add facts, examples, metaphors,
    boundaries, or claims that are not in the source manifest fields.
    If a field is null, the corresponding card content must come from
    a different field that IS populated, or the card section must be
    omitted entirely. Hallucinated content in flashcards is worse
    than missing content - it teaches the user something false.

────────────────────────────────────────────────────────────────
PHASE GF-2 — GROUP BY MOC AND WRITE BATCH FILE

  Target folder : 20_Learning\23_FlashCards\
  Target file   : a NEW file per run, named by batch number:
                    Batch 1  → Flashcards_{moc_stem}.md
                    Batch N (N≥2) → "Flashcards_{moc_stem} - Batch {N}.md"

  Determine N before writing:
    base = "Flashcards_{moc_stem}.md"
    pattern = "Flashcards_{moc_stem} - Batch *.md"
    If neither base nor any pattern match exists → N = 1, file = base
    Else N = (highest existing batch number for this MOC) + 1, where
      base counts as batch 1 and each "- Batch K.md" contributes K.
      File = "Flashcards_{moc_stem} - Batch {N}.md".
    Never overwrite an existing flashcard file. If the chosen filename
    already exists, abort with an error - do not silently bump N
    further, as that hides a prior failed run.

  Group successfully-extracted candidates by moc_stem.

  For each MOC group:

    Create the batch file fresh with this header (and a single blank
    line, no cards yet). The title carries the batch suffix only when
    N ≥ 2; for batch 1 the title is plain "Flashcards - {humanized moc_stem}".

        ---
        title: Flashcards - {humanized moc_stem}
        type: flashcard-batch
        moc: [{moc_stem}]
        created: {today}
        tags:
          - card
        ---

        # Flashcards - {humanized moc_stem}


      Where humanized moc_stem strips the leading "MOC_" and replaces
      underscores with spaces. Example: MOC_Learning_and_Memory →
      "Learning and Memory".

    For each candidate in this group, write adaptive card blocks
    after the header (in encounter order). Each card is structured as:
      `#card` on its own line, then `Question :: Answer` on the next
      line, then a blank line before the next card.

    Three cards per concept maximum. Question phrasing adapts to the
    concept's grammar (singular/plural, action verb fits the concept):

      Card 1 - WHAT (always emitted if the concept is eligible):
        #card
        What is/are {Title}? :: {dense prose definition that names what
        it is, weaves in metaphor naturally if present, names the key
        behaviour or property, and ends with the boundary condition
        woven into the prose. 3-5 sentences. Use plain prose - NO
        bold labels like **Metaphor:** or **Boundary condition:**.}

      Card 2 - HOW (emit only if mechanism is non-empty):
        #card
        How does/do {Title} work? :: {dense prose mechanism explaining
        the chain of cause and effect, with the most important insight
        woven in. May use inline "Key insight:" or "Boundary condition:"
        WITHOUT bold formatting. 3-5 sentences. No bullets.}

      Card 3 - WHEN (emit if when_to OR when_not is present; phrasing
      adapts to the concept):
        - Both when_to AND when_not present:
            #card
            When and why would you use/apply/act on {Title}{ deliberately|
            in practice | knowledge}? :: {Action recommendation in prose}.
            Do NOT {counter-action in prose}. {Goal or principle
            clarification.} 2-4 sentences.
        - Only when_to present:
            #card
            When should you use {Title}? :: {Action recommendation in
            prose - 1-2 sentences.}
        - Only when_not present:
            #card
            When should you avoid {Title}? :: Do NOT {counter-action
            in prose - 1-2 sentences.}

  Question phrasing rules:
    - Concept name appears BARE in the question - no quotes around it
    - "What is" for singular nouns, "What are" for plural (Endorphins)
    - "How does" for singular, "How do" for plural
    - Card 3 verb adapts: "use ... deliberately" for hormones/tools,
      "act on ... knowledge" for diagnostic concepts, "apply" for
      frameworks - pick the verb that reads naturally for the concept

  Card body rules:
    - Plain prose paragraphs. NO markdown bold labels like
      **When to use:** or **Metaphor:** or **Boundary condition:**.
    - Inline lowercase labels are fine when natural ("Boundary
      condition: ...", "Critical boundary condition: ...", "Key
      insight: ...") but use sparingly - prefer woven prose.
    - Use "Do NOT" in caps for the counter-case in Card 3.
    - Replace em-dashes (—) with " - " (space hyphen space).
    - No bullet points, no headings, no wikilinks inside card bodies.
    - Each card body: 3-5 dense sentences. Compress without losing
      the core mechanism, metaphor, or boundary.

  Reference example - Cortisol (Biology of Performance MOC):

    #card
    What is Cortisol? :: Cortisol is a temporary survival mechanism
    that prepares the body for fight-or-flight - it increases heart
    rate and mobilises resources for immediate threat response. It
    becomes highly destructive when chronic: it suppresses the immune
    system, completely blocks oxytocin release, and makes empathy
    biologically impossible. It is also highly contagious - a single
    panicked leader can cascade cortisol through an entire team
    within minutes.

    #card
    How does Cortisol work? :: Cortisol spreads through a team via
    visible panic - a single dysregulated leader activates the
    stress response in everyone around them. The reverse is equally
    true: a calm, grounded leader actively suppresses cortisol
    spread, making emotional self-regulation a structural team-safety
    function, not merely a personal virtue. Chronic cortisol blocks
    oxytocin and destroys team empathy. Acute cortisol - short and
    bounded - is adaptive and sharpens focus.

    #card
    When and why would you act on Cortisol knowledge? :: Recognise
    when cortisol is spreading and de-escalate: eliminate chronic,
    unnecessary stressors - your team will biologically lose the
    ability to trust one another under sustained exposure. Do NOT
    attempt to eliminate all stress - acute, short-duration cortisol
    (a deadline, a high-stakes pitch) is adaptive and healthy. The
    goal is to prevent chronic elevation, not create a zero-stress
    environment, which removes the performance benefit of
    appropriate arousal.

  Minimum 1 card per concept (the WHAT card). Maximum 3.
  If the concept yielded only the WHAT card, log:
    "ⓘ {stem}: 1 card only (no mechanism, no when_to/when_not)."
  ...even though that case shouldn't pass the GF-1 eligibility gate
  (which requires at least one of when_to/when_not).

  WRITE DISCIPLINE — critical for Anki ID stability:
    1. Always create a NEW file with Set-Content -Encoding UTF8.
       Never read, append to, or rewrite a pre-existing flashcard
       file - not even to "fix" formatting.
    2. Confirm the chosen filename does not already exist before
       writing (Test-Path). If it does, abort with an error.
    3. Once the plugin syncs the file and writes back <!--ID:nnn-->
       markers, treat that file as immutable. The next generation
       run produces a separate batch file.

  GF-2 RUN TABLE — output at the end of GF-2, before moving to GF-3.
  This is the at-a-glance audit of what was just written. The user
  scans this table to verify each concept's three cards landed in the
  expected MOC file with the expected status.

  Format:
  | MOC | Concept | What | How | When | Status & comment |

  Column rules:
    MOC      — humanized MOC name (e.g. "Learning and Memory")
    Concept  — concept stem (e.g. "Active_Recall")
    What     — ✓ written | — skipped | ⚠ flagged
    How      — ✓ written | — skipped | ⚠ flagged
                (— if mechanism manifest field was null)
    When     — ✓ written | — skipped | ⚠ flagged
                (— if both when_to and when_not were null)
    Status   — short comment per row, e.g.:
                "All 3 cards written"
                "2/3 - HOW skipped (no mechanism in source)"
                "Skipped - missing required fields: when_to_or_not"
                "Skipped - flagged stub, user declined"
                "Skipped - flagged stub, user accepted (3 stub cards)"

  One row per ELIGIBLE candidate (from GF-1), including those that
  were skipped at GF-1 or GF-2. Group rows by MOC for readability.

  After the table, also print a one-line totals summary:
    "Generated: X concepts (Y cards) | Skipped: Z | MOC files touched: M"

────────────────────────────────────────────────────────────────
PHASE GF-3 — PATCH SOURCE NOTES  (flashcards: false → true)

  For each candidate whose 3 cards were successfully appended:
    Patch 20_Learning\21_Concepts\{stem}.md:
      $content = $content -replace 'flashcards: false', 'flashcards: true'
      $content = $content -replace 'updated: \d{4}-\d{2}-\d{2}', "updated: $today"

  Patch only sources whose cards were actually written this run.
  Never patch a source that was skipped.

────────────────────────────────────────────────────────────────
PHASE GF-4 — REPORT

  Two outputs: a markdown table in the agent transcript (for log
  history) and a JSON results file the launch script renders as a
  console-aligned table (for at-a-glance terminal review).

  (a) MARKDOWN TABLE — print to the transcript using the canonical
  GF-2 columns, augmented with post-patch status:
      | MOC | Concept | What | How | When | Status & comment |

  Status & comment reflects the FINAL state after GF-3:
    "All 3 cards written, source patched"
    "2/3 cards written, source patched - HOW skipped (no mechanism)"
    "Skipped - missing required fields (source NOT patched)"
    "Skipped - stub declined by user (source NOT patched)"
    "Cards written but source patch FAILED - manual review required"

  Group rows by MOC. After the table, print one totals line:
    "Generated: X concepts (Y cards) | Sources patched: P |
     Skipped: Z | MOC files touched: M"

  (b) JSON RESULTS FILE — write to:
      00_Inbox/FLASHCARD_RUN_RESULT.json

  Schema:
    {
      "generated": "YYYY-MM-DD",
      "rows": [
        {
          "moc":     "Learning and Memory",
          "concept": "Active_Recall",
          "what":    "✓",   // ✓ written | — skipped | ⚠ flagged
          "how":     "✓",
          "when":    "✓",
          "status":  "All 3 cards written, source patched"
        },
        ...
      ],
      "totals": {
        "concepts_generated":  N,
        "cards_total":         3*N approx,
        "sources_patched":     P,
        "skipped":             Z,
        "moc_files_touched":   M
      }
    }

  Sort `rows` by moc then concept. Use UTF-8 encoding (no BOM).
  The launch script reads this and renders a console-aligned table
  after Claude returns, so the user can scan results without scrolling
  back through the transcript.

  DO NOT re-output card content - it is already in the MOC files.

────────────────────────────────────────────────────────────────
FLASHCARD FORMAT NOTES (flashcards-obsidian plugin)
  - Each card uses the two-line block format:
        #card
        Question? :: Answer text.
    The standalone "#card" line tags the next line as a flashcard;
    the plugin parses the front/back via the :: separator.
  - inlineSeparator is :: (configured in plugin data.json).
  - flashcardsTag is "card" (configured in plugin data.json).
  - folderBasedDeck is ON — files in 20_Learning/23_FlashCards/ land
    in the "20_Learning::23_FlashCards" Anki sub-deck.
  - On first sync the plugin appends ^NNNNNNNNNNNNN (13-digit Anki
    note ID) on the line below each card. On re-sync it matches by
    ID, updating Anki when the markdown changes. NEVER edit, reorder,
    or remove these IDs or their cards become orphaned.
  - SILENT-FAIL TRAP: AnkiConnect rejects "duplicates" (notes whose
    front field matches an existing card in any deck under the same
    note model). When this happens the plugin shows ONLY "Nothing to
    do, everything is up to date" - the duplicate errors appear in
    the dev console (Ctrl+Shift+I), not the UI. If sync produces no
    IDs in the file after a successful-looking run, check the
    console for "cannot create note because it is a duplicate" and
    delete the orphan Anki cards via Browse before re-syncing.
