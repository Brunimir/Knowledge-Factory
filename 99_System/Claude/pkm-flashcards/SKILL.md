---
name: pkm-flashcards
description: Generates Anki-ready flashcard files from finalised Obsidian concept notes. Use this skill whenever the user asks to generate flashcards, create Anki cards, process final concept notes into cards, or mentions Annex 4, the flashcard pipeline, or spaced repetition export. Also trigger when the user marks a note as final and asks what happens next, or when the user provides a set of concept notes and asks for retention materials. This skill produces one consolidated .md file per MOC routed to the correct Anki deck via card-deck frontmatter.
---

# PKM Flashcard Generation Skill

Generates 3 Anki flashcards per finalised concept note (Definition, Mechanism, Application) and writes them into a single consolidated `.md` file per MOC. The file is placed in `20_Learning/23_FlashCards/` and syncs to Anki via the Flashcards plugin.

## Trigger condition

A concept note is eligible for flashcard generation when:
- `status: final` in its YAML frontmatter
- `flashcards: false` (not yet generated)

Notes with `status: draft` or `status: needs-review` are skipped and logged —
both are valid permanent resting states, not errors. A note with `status: final`
and `flashcards: true` is also skipped: `flashcards: true` means the cards
already exist OR the human opted the note out of studying (reviewed, no cards
needed). Never generate cards for it.

---

## Input

One or more concept notes. Read the following fields from each:
- `title` — used for card questions and filename
- `moc` — used to derive the Anki deck name
- Core Idea (Summary) — source for Definition card
- Mechanism (Key details) — source for Mechanism card
- Application (When to use / When NOT to use) — source for Application card

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

**If `20_Learning/23_FlashCards/{MOC name}.md` already exists:**
Append the new cards to the end of the existing file. Do not overwrite.

**If the file does not exist:**
Create it with the frontmatter block and the new cards.

---

## Output format — consolidated file per MOC

```markdown
---
card-deck: {MOC name derived above}
---

#card
{Question 1} :: {Answer 1}

#card
{Question 2} :: {Answer 2}
```

### Critical structural rules

| Rule | Why it matters |
|---|---|
| Opening `---` before `card-deck:` | Tells Obsidian this is metadata, not card content |
| Closing `---` after `card-deck:` | Closes the metadata block |
| `#card` alone on its own line | Tag is the trigger — must not be inline with the question |
| Question and answer on one continuous line | Plugin splits on `::` within a single line; hard line breaks end the card |
| One blank line between cards | Separates card blocks without breaking the parser |
| No em-dashes (—) in card content | Use regular hyphen with spaces ( - ) instead |

---

## Three card templates

### Card 1 — Definition
**Question format:** `What is {Concept Name}?`
**Answer format:** Core claim in 1-2 sentences. Bold labels for inline structure.

```
#card
What is {Concept}? :: {Core claim}. **Metaphor:** {metaphor if applicable}. **Boundary condition:** {when it breaks down}.
```

### Card 2 — Mechanism
**Question format:** `How does {Concept Name} work?`
**Answer format:** The causal chain. Must include boundary condition.

```
#card
How does {Concept} work? :: {Causal chain or key mechanics}. **Key mechanic:** {most important detail}. **Boundary condition:** {when the mechanism breaks down or reverses}.
```

### Card 3 — Application
**Question format:** `When and why would you use {Concept Name}?`
**Answer format:** When to use then When NOT to use. Both must be specific.

```
#card
When and why would you use {Concept}? :: **When to use:** {specific context}. **When NOT to use:** {specific counter-case — name the situation explicitly}.
```

---

## Answer quality rules

1. The answer must be self-contained — the reader should not need to open the concept note to understand it.
2. Boundary condition is mandatory in the Mechanism card. A card without it creates an incomplete mental model.
3. Do not copy the Core Idea verbatim as the Definition answer — paraphrase so the brain must reconstruct, not recognise.
4. `When NOT to use` must name a specific context, not a vague qualifier. Bad: "when it doesn't apply." Good: "when the environment is chronically stressful and the structural cause hasn't been addressed."
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
```
