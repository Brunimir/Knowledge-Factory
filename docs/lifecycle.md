# The Artefact Lifecycle

Every artefact in the Knowledge Factory — a concept note, a Map of Content, a Pattern,
a Solution — moves through **one consistent lifecycle**. There is a single state machine
to learn, governed by two frontmatter flags (plus a derived trust score for concept
notes), and it is deliberately built so the **human is never the bottleneck**.

This is the reference for that lifecycle. The README §3 has the one-paragraph summary;
this document is the full version.

---

## The two flags

| Flag | Values | Who sets it | What it gates |
|---|---|---|---|
| `status` | `draft` → `final` | agent writes `draft`; **human** promotes to `final` | whether downstream engines may treat the note as locked, citable knowledge |
| `flashcards` | `false` → `true` | `generate-flashcards`, **or** the human (opt-out) | whether spaced-repetition cards have been generated (or deliberately skipped) |

That is the whole vocabulary. The same two flags mean the same thing on every artefact
type — a Pattern is `draft` for the same reason a concept note is.

(An earlier version of this system also carried a `reviewed` flag between `status` and
`flashcards`. It was retired: `reviewed: true` never occurred without `status: final`, so
it never carried information `status` did not already carry. Legacy `reviewed:` keys are
dropped by `concept_schema_sync.ps1`.)

---

## Trust — a derived score, not a gate

Concept notes also carry `source_count` and `trust`, maintained by
`concept_schema_sync.ps1` and re-derived (and drift-checked) by `generate_index.py`:

```
source_count = number of [[wikilinks]] on the note's "- Source" line
trust        = 0.0                  if source_count == 0
               2 - 1/source_count   otherwise      (1.0, 1.5, 1.67, 1.75 … → 2.0)
               + 0.2                if status: final
```

The curve has diminishing returns and an asymptote at 2.0, so corroborating a claim with
more sources always helps but never dominates; the `status: final` bonus caps the scale
at 2.2. Trust is descriptive, not a gate — it does not block promotion or flashcard
generation. It exists so a note that rests on one source and a note corroborated by four
are visibly different, even though both can be `status: final`.

---

## The states

```
          write (agent or human)
                  │
                  ▼
            status: draft          ◀── valid PERMANENT resting state; never nagged
                  │
                  │  human review pass (the three promotion criteria below)
                  ▼
            status: final
            flashcards: false      ◀── the one "actionable" state vault-health surfaces
                  │
                  │  generate-flashcards  (or human opt-out)
                  ▼
            status: final
            flashcards: true       ◀── terminal; never regenerated, never flagged
```

### `status: draft` — the resting state

`draft` is where the agent leaves every note it writes, and where most notes you write
start. Crucially, **`draft` is a valid permanent state with no review SLA.** A reference
note you capture for searchability but never intend to memorise can live as `draft`
forever. The system never treats a draft as "stale" and never nags you to process a
backlog. As capture grows the vault, this is what keeps you off the critical path.

### `status: final` — promoted by you, in one pass

Only **you** promote a note to `final`, and only after a single review pass that confirms
all three:

1. **Retrieval test** — you can state the core idea from memory in one sentence.
2. **Links resolve** — every `[[wikilink]]` points to a real note and makes sense in context.
3. **Real application** — at least one concrete situation where the idea applies is named.

The agent **never** sets `status: final` on its own. Once a note is `final`, the agent
treats it as locked: it may make only three whitelisted patches to a final note
(`flashcards: false → true`, bumping the `updated` date when cards are generated, and the
`source_count`/`trust` patch applied only by `concept_schema_sync.ps1`) and **nothing
else** — not formatting, not restructuring, not relabelling.

### `final + flashcards: true` — terminal

A note reaches its terminal state when `flashcards` flips to `true`. That happens one of
two ways, and they are treated identically:

- `generate-flashcards` produced Anki cards from it; **or**
- you set `flashcards: true` by hand to opt the note out of studying — *"reviewed, no
  need to study."*

Either way, no cards are ever regenerated and the note is never flagged again.

---

## Why only `final + flashcards:false` is "actionable"

`vault-health` deliberately surfaces exactly one bucket: notes that are `status: final`
**and** `flashcards: false` — i.e. approved knowledge still awaiting cards. Everything
else is a valid resting state:

- a `draft` is resting (maybe permanently) — **not** surfaced;
- a `final + flashcards: true` note is done — **not** surfaced.

So the health report is a short, genuinely actionable list, not a guilt-inducing backlog.

---

## Eligibility, at a glance

```
generate-flashcards eligibility  =  status:final  AND  flashcards:false
```

Both must hold. A note missing either is not eligible — the agent skips it rather than
generating partial or speculative cards.

---

## The one principle

**The human is never the bottleneck.** `draft` is permanent and unnagged; promotion to
`final` is always a human act on the human's schedule; nothing is ever marked stale. You
crystallise as much as you like, and spend the deliberate effort of promotion and study
only on the subset you actually choose to keep.
