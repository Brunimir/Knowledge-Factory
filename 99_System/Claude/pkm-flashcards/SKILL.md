---
name: pkm-flashcards
description: Generates Anki-ready flashcard files from finalised Obsidian concept notes. Use this skill whenever the user asks to generate flashcards, create Anki cards, process final concept notes into cards, or mentions Annex 4, the flashcard pipeline, or spaced repetition export. Also trigger when the user marks a note as final and asks what happens next, or when the user provides a set of concept notes and asks for retention materials. This skill produces one consolidated .md file per MOC routed to the correct Anki deck via card-deck frontmatter.
---

# PKM Flashcard Generation Skill

Generates Anki flashcards from finalised concept notes and writes them into a new batch `.md` file per MOC. The file is placed in `20_Learning/23_FlashCards/` and syncs to Anki via the Flashcards plugin.

**Hard cap: MAXIMUM 6 CARDS PER CONCEPT NOTE.** It is a ceiling, not a target: stop when the ideas the note treats as central run out.

Cards are **short, crisp, worded to stick and compliant with the concept**: one idea per card, about 9 words on the back and 18 at most, under the **Fidelity Contract** (a card may only say what the note says). The note stays the reference document, so a card does not try to carry it. Existing cards are never rewritten.

## Before This Command Runs

**Pre-run setup:**

This skill is manifest-driven: the launcher (`launch-generate-flashcards.ps1`) pre-extracts
every eligible candidate (status:final AND flashcards:false) into `00_Inbox/FLASHCARD_CANDIDATES.json`.

1. **Launcher regenerates the index** — The launcher runs `generate_index.py` and builds
   the manifest before the agent starts. You do not manually check staleness.

2. **Read the manifest only** — Open `00_Inbox/FLASHCARD_CANDIDATES.json` and process
   only the notes listed there. Do not scan the full vault.

3. **Confirm scope** — State briefly: "Generating cards for {N} notes across {M} MOCs.
   Files will be written to 20_Learning/23_FlashCards/."

**Do not proceed unless the manifest exists and is not empty.**

---

## Trigger condition

A concept note is eligible for flashcard generation when:
- `status: final` in its YAML frontmatter
- `flashcards: false` (not yet generated)

Notes with `status: draft` are skipped and logged —
it is a valid permanent resting state, not an error. A note with `status: final`
and `flashcards: true` is also skipped: `flashcards: true` means the cards
already exist OR the human opted the note out of studying (reviewed, no cards
needed). Never generate cards for it.

---

## Input

One or more concept notes. Read the following fields from each:
- `title` — used for card questions and filename
- `moc` — used to derive the Anki deck name
- Core Idea (Summary), including any metaphor
- Mechanism (Key details), including any boundary condition
- Application (When to use / When NOT to use)

---

## Deck name derivation

Derive the Anki deck name from the note's `moc` YAML field:
1. Take the first MOC listed
2. Strip the `MOC_` prefix
3. Replace underscores with spaces

Examples:
- `MOC_Biology_of_Performance` → `Biology of Performance`
- `MOC_Learning_and_Memory` → `Learning and Memory`
- `MOC_Presentations_That_Drive_Action` → `Presentations That Drive Action`

---

## File behaviour

**Always write a NEW batch file; never append to or overwrite an existing one.**
Appending to a synced file triggers the Anki duplicate trap. Naming and the batch
number are in `flashcards-pipeline.md`, phase GF-2.

---

## Output format — consolidated file per MOC

```markdown
---
card-deck: {MOC name derived above}
---

- {Question 1} :: {Answer 1}

- {Question 2} :: {Answer 2}
```

### Critical structural rules

| Rule | Why it matters |
|---|---|
| Opening `---` before `card-deck:` | Tells Obsidian this is metadata, not card content |
| Closing `---` after `card-deck:` | Closes the metadata block |
| Each card is one list item: `- Question :: Answer` | flashcards-obsidian v2 reads `::` only inside a list item |
| NO `#card` line | v2 treats a standalone `#card` as "the previous heading is the question", so the card syncs with the file title as its front and the whole `Q :: A` line as its back (found 2026-10-28) |
| Question and answer on one continuous line | Plugin splits on `::` within a single line; hard line breaks end the card |
| One blank line between cards | Separates card blocks without breaking the parser |
| Leave any trailing `^id` anchor alone | The plugin adds `^q-xxxx` after the first sync; never write or change one |
| No em-dashes (—) in card content | Use regular hyphen with spaces ( - ) instead |

---

## Writing a card

**One card per idea the note treats as central:** its core mechanism, its boundary
condition, its practical consequence. Up to 6 per note. An empty section yields no
card, and a one-idea note yields one correct card.

### The question

- **Names the concept**, bare and without quotes. It gives the card its context when
  reviewed alone, and GATE-KF-05 assigns a card to its note by finding at least 60% of
  the title's content words in the question. A question that does not name it is refused.
- **Precise:** only one answer fits, and it comes out the same each review.
- **Does not give away the answer.** Avoid either/or questions, which test recognition.
- **Never refers to the document** ("in the note's picture").
- **Under the same Fidelity Contract as the answer.** It states and implies nothing the
  note does not say: asking why something is "hard to trace", when the note says only
  "disconnected", is an invention.
- **Shaped to the idea** (cause, contrast, consequence, when, when not), not a fixed template.

### The answer

- **One idea, 9 words or fewer,** in one sentence or a fragment. Count them. Go over 9
  only when the idea cannot be said shorter and stay true. 18 is the absolute limit.
- **No semicolons, and no second clause adding another idea.** Give it its own card.
  Do not add a contrast or consequence the note does not state.
- **Worded to stick, from the note:** use its metaphor, its concrete example or its own
  vivid phrase. Where it has none, write a plain card. Never invent an image.
- **A qualifier is never dropped to save words.** Split the card or leave the idea out.

### Acronyms (question and answer)

Write every acronym with its spelled-out form in brackets, every time it appears on a
card: `ISS (International Space Station)`. **The whole form counts as one word.**
GATE-KF-05 counts it that way when the brackets spell out the acronym.

The spelled-out form comes from the note, under the Fidelity Contract. If the note does
not spell the acronym out, keep it as the note writes it and list it in the report.

```
- What is the compost heap picture of Saving String? :: Scraps sit until they become rich soil nourishing a large harvest.

- In Saving String, what does collecting without producing become without a harvest phase? :: Information hoarding.

- For what kind of work is Saving String not useful? :: Tight-deadline work, where collection time does not exist.
```

---

## THE FIDELITY CONTRACT (overrides every other rule here)

**A card may only say what the concept note says.** Safety Rule #7 applies at
full force: every claim, metaphor, example, number, named study and boundary
condition on a card MUST originate in the source note. A hallucinated flashcard
is worse than a missing one, because the human then *learns* something false and
rehearses it to permanence.

**Permitted transformations — surface only:**

| Transformation | Example |
|---|---|
| Compress (drop filler) | "It is important to note that X occurs" → "X occurs" |
| Reorder | move the key term to the front of the answer |
| Re-syntax | turn a bullet fragment into a full sentence |
| De-link | strip `[[ ]]` from wikilinks, keep the words |
| Split | one source sentence → two cards, each carrying part |
| Omit | leave a fact off the cards entirely |

**Forbidden transformations — any of these is a defect, not a style choice:**

- Adding a fact, example, metaphor, number or study **not present in the note**
- **Strengthening or weakening** a claim: `can` → `does`, `often` → `always`,
  `suggests` → `proves`, `may reduce` → `reduces`
- **Dropping a scope qualifier** so a bounded claim reads as universal
  (`in sedentary adults` → *removed*)
- **Inferring** a consequence, cause or recommendation the note does not state
- Merging content from another note, another card, or your own knowledge
- "Filling in" a gap where the note is silent — if the source field is empty,
  **emit no card for it**

**The test, applied per card before writing it:** point at the exact sentence or
bullet in the note that each clause came from. If you cannot, delete the clause.
If that empties the card, do not emit the card.

**Empty fields are not a problem to solve.** A note with no metaphor gets no
metaphor. A note with no `When NOT to use` gets no counter-case. Fewer, true
cards beat more, invented ones.

---

## One idea per card

A card holding several facts is failed whenever any one of them is forgotten, and the
review gives no signal about *which*.

**What counts as an idea:** one independently forgettable assertion — something
you could get right or wrong on its own. Elaborations of the *same* assertion
count once: "increases heart rate and mobilises resources for immediate threat
response" both elaborate "prepares the body for fight-or-flight", so that is
**one** idea, not three.

Rules:

1. **Split or omit, never compress.** Do not squeeze two ideas into one ambiguous
   clause to fit the limit. That hides content rather than removing it, and the
   result is a sentence the note does not support.
2. **Keep what the note leads with.** Choose the concept's core mechanism, its
   boundary condition and its practical consequence; shed peripheral elaboration and
   restated detail. Fidelity to the note's *emphasis* is the goal.
3. **Maximum 6 cards per note.** Stop earlier when the central ideas run out: fewer
   true cards beat more.

Anything left out remains in the concept note, which stays the reference document
and is one click away.

---

## Answer quality rules

1. **Self-contained.** The card must make sense without the note open, which is
   why the question names the concept. What it leaves out stays in the note.
2. Boundary conditions matter: an unbounded mechanism is a *false* mental model,
   not merely an incomplete one. Include the note's boundary when it states one;
   omit it when the note does not — never manufacture one to complete the
   pattern.
3. **Difficulty comes from the question, not from rewording the answer.**
   Recognition is not recall — but the fix is a question that forces
   reconstruction, *never* a paraphrase that drifts from the note. Where a
   faithful answer is close to the note's own wording, that is correct and
   expected. Reword only the surface (see the Fidelity Contract); never re-scope
   to manufacture difficulty.
4. `When NOT to use` must name the specific context **the note names**. Bad:
   "when it doesn't apply." Good: whatever counter-case the note actually
   states. If the note gives none, emit no WHEN-not card.
5. Every answer stays on one continuous line — no hard line breaks inside the answer.
6. No em-dashes anywhere in card content.

---

## Post-generation step

After writing the cards, update the source concept note's YAML:
```yaml
flashcards: true
updated: {today's date}
```

---

## Report

```
## Flashcards generated
| Note | Deck | Cards added | File |

## Skipped
| Note | Reason |

## Acronyms the note does not spell out
| Note | Acronym |
```
