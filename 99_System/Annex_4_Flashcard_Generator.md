# Annex 4 — Flashcard Generator
# Folder: reference (keep alongside CLAUDE.md)
#
# WHEN FLASHCARDS ARE GENERATED
# Claude Code watches for status changes in 21_Concepts.
# When a note's status field changes from "draft" to "final",
# three flashcard files are automatically generated and saved
# to 20_Learning/23_FlashCards/ as individual .md files.
#
# Each file is also appended to flashcards_export.csv for Anki import.
#
# MANUAL TRIGGER
# Feed a final concept note to Claude with the prompt:
#   "Generate the three Annex 4 flashcards for this concept note."

════════════════════════════════════════════════════════════════
THREE CARD TYPES — one per concept note
════════════════════════════════════════════════════════════════

Every concept note at #status/final gets exactly these three cards.
The question and answer are separated by "::" (Anki standard).
The #card tag must appear as a visible line in the file body —
it is the trigger for Anki extraction via the Obsidian Anki plugin.

────────────────────────────────────────────────────────────────
CARD TYPE 1 — Definition
────────────────────────────────────────────────────────────────
Purpose : Anchor the concept's identity. What is it?
Best for : Frameworks, mental models, named techniques, terminology.
Template :

---
topic: "[[{Note Title}]]"
---
#card #definition

What is {Concept Name}? :: {Core Idea in 1–2 sentences. Include
the key distinguishing feature and the boundary condition if short
enough. Do not pad. Do not add examples — those belong in the
Mechanism card.}

────────────────────────────────────────────────────────────────
CARD TYPE 2 — Mechanism
────────────────────────────────────────────────────────────────
Purpose : Test understanding of how and why. Knowing what without
          knowing how produces the illusion of competence.
Best for : Processes, causality, systems, feedback loops.
Template :

---
topic: "[[{Note Title}]]"
---
#card #mechanism

How does {Concept Name} work? :: {The causal chain or key mechanics
in 2–4 sentences. Must include the boundary condition — when the
mechanism breaks down or reverses. This is the highest-retention
part of the note.}

────────────────────────────────────────────────────────────────
CARD TYPE 3 — Application
────────────────────────────────────────────────────────────────
Purpose : Force transfer to real contexts. The highest-value card
          type because it tests whether you can actually use the
          concept, not just recall it.
Best for : Any concept with a When to use / When NOT to use section.
Template :

---
topic: "[[{Note Title}]]"
---
#card #application

When and why would you use {Concept Name}? :: {When to use in 1
sentence. Then "Do NOT use when..." in 1 sentence. Keep both
actionable and specific — avoid generic advice.}

════════════════════════════════════════════════════════════════
FILE NAMING CONVENTION
════════════════════════════════════════════════════════════════

  {Note Title} - Definition.md
  {Note Title} - Mechanism.md
  {Note Title} - Application.md

Examples:
  Dopamine - Reward and Risk - Definition.md
  Dopamine - Reward and Risk - Mechanism.md
  Dopamine - Reward and Risk - Application.md

Filename rules: same safe character set as concept notes.
No em-dashes, no accented characters, no underscores.

════════════════════════════════════════════════════════════════
ANKI EXPORT FORMAT (flashcards_export.csv)
════════════════════════════════════════════════════════════════

Each card is also appended to 20_Learning/23_FlashCards/flashcards_export.csv
in Anki's Basic note type format:

  Front,Back,Tags
  "What is Dopamine?","Dopamine is the hormone of...","definition biology"
  "How does Dopamine work?","Dopamine peaks during...","mechanism biology"
  "When would you use Dopamine deliberately?","Engineer dopamine loops...","application biology"

Import into Anki:
  File → Import → flashcards_export.csv
  Note type: Basic
  Fields: Front / Back / Tags
  Allow HTML: No (unless you add formatting)

════════════════════════════════════════════════════════════════
AUTOMATION SPEC (Claude Code file-watcher)
════════════════════════════════════════════════════════════════

The following logic should be implemented as a Claude Code hook
watching the 21_Concepts folder for file save events.

Trigger condition:
  A .md file in 21_Concepts/ is saved AND
  its YAML frontmatter contains: status: final

On trigger:
  1. Read the note.
  2. Extract: title, core idea, mechanism (all bullets), application
     (when to use + when not to use).
  3. Generate the three card files using the templates above.
  4. Write them to 20_Learning/23_FlashCards/ using the naming convention.
  5. Append three rows to 20_Learning/23_FlashCards/flashcards_export.csv.
  6. Log: "✓ 3 flashcards generated for: {Note Title}"

Guard condition:
  If flashcard files for this note already exist in 20_Learning/23_FlashCards/,
  do not overwrite — log a warning and skip.

════════════════════════════════════════════════════════════════
QUALITY RULES FOR CARD CONTENT
════════════════════════════════════════════════════════════════

1. The answer must be self-contained. The reader should not need
   to open the concept note to understand the answer.

2. Boundary condition is mandatory in the Mechanism card. A card
   without it creates a dangerously incomplete mental model.

3. Do NOT use the note's exact Feynman summary as the Definition
   answer — paraphrase it slightly so the brain has to reconstruct,
   not recognise.

4. "Do NOT use when" in the Application card must name a specific
   context, not a vague qualifier. Bad: "when it doesn't apply."
   Good: "when the environment is chronically stressful and the
   structural problem hasn't been addressed."

5. No em-dashes (—) anywhere in card content. Use a regular hyphen
   with spaces ( - ) instead. Anki's plain text importer handles
   hyphens but can misparse em-dashes depending on encoding.

════════════════════════════════════════════════════════════════
EXAMPLE — COMPLETE SET (Dopamine - Reward and Risk)
════════════════════════════════════════════════════════════════

File: Dopamine - Reward and Risk - Definition.md
───────────────────────────────────────────────
---
topic: "[[Dopamine - Reward and Risk]]"
---
#card #definition

What is Dopamine? :: Dopamine is the hormone of reward anticipation
and goal achievement - internally generated, requiring no social
context. Its danger is that the same pathway rewarding genuine
achievement also drives addiction, compulsive checking, and
performance addiction. The brain cannot distinguish between a
completed task and a slot machine pull.


File: Dopamine - Reward and Risk - Mechanism.md
───────────────────────────────────────────────
---
topic: "[[Dopamine - Reward and Risk]]"
---
#card #mechanism

How does Dopamine work? :: Dopamine peaks during the anticipation
of reward, not at receipt. Writing goals down and physically
checking them off amplifies the signal. The pathway is
indiscriminate - notifications, gambling, and KPIs activate the
same circuit as genuine achievement. Boundary condition: the
pathway cannot distinguish value from frequency, so high-frequency
shallow tasks systematically out-compete deep, slow-return work
for motivational priority.


File: Dopamine - Reward and Risk - Application.md
──────────────────────────────────────────────────
---
topic: "[[Dopamine - Reward and Risk]]"
---
#card #application

When and why would you use Dopamine deliberately? :: Engineer
dopamine loops for genuinely important work: write tasks down, set
visible milestones, and celebrate completion moments to exploit the
anticipation effect. Do NOT use dopamine-triggering tools
(notifications, streaks, progress bars) to sustain engagement with
low-value activity - the hit sustains the behaviour regardless of
its actual worth.
