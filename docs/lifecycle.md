# The Artefact Lifecycle

Every artefact in the Knowledge Factory — a concept note, a Map of Content, a Pattern,
a Solution — moves through **one consistent lifecycle**. There is a single state machine
to learn, governed by three frontmatter flags, and it is deliberately built so the
**human is never the bottleneck**.

This is the reference for that lifecycle. The README §3 has the one-paragraph summary;
this document is the full version.

---

## The three flags

| Flag | Values | Who sets it | What it gates |
|---|---|---|---|
| `status` | `draft` → `final` | agent writes `draft`; **human** promotes to `final` | whether downstream engines may treat the note as locked, citable knowledge |
| `reviewed` | `false` → `true` | **human** | records that you have read the note through and approved it |
| `flashcards` | `false` → `true` | `generate-flashcards`, **or** the human (opt-out) | whether spaced-repetition cards have been generated (or deliberately skipped) |

That is the whole vocabulary. The same three flags mean the same thing on every artefact
type — a Pattern is `draft` for the same reason a concept note is.

---

## The states

```
          write (agent or human)
                  │
                  ▼
            status: draft          ◀── valid PERMANENT resting state; never nagged
            reviewed: false
                  │
                  │  human review pass (the three promotion criteria below)
                  ▼
            status: final
            reviewed: true
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
treats it as locked: it may make only two whitelisted patches to a final note
(`flashcards: false → true` and bumping the `updated` date when cards are generated) and
**nothing else** — not formatting, not restructuring, not relabelling.

### `final + flashcards: true` — terminal

A note reaches its terminal state when `flashcards` flips to `true`. That happens one of
two ways, and they are treated identically:

- `generate-flashcards` produced Anki cards from it; **or**
- you set `flashcards: true` by hand to opt the note out of studying — *"reviewed, no
  need to study."*

Either way, no cards are ever regenerated and the note is never flagged again.

---

## Why only `final + reviewed + flashcards:false` is "actionable"

`vault-health` deliberately surfaces exactly one bucket: notes that are `status: final`
**and** `reviewed: true` **and** `flashcards: false` — i.e. approved knowledge still
awaiting cards. Everything else is a valid resting state:

- a `draft` is resting (maybe permanently) — **not** surfaced;
- a `final + flashcards: true` note is done — **not** surfaced.

So the health report is a short, genuinely actionable list, not a guilt-inducing backlog.

---

## Eligibility, at a glance

```
generate-flashcards eligibility  =  status:final  AND  reviewed:true  AND  flashcards:false
```

All three must hold. A note missing any one is not eligible — the agent skips it rather
than generating partial or speculative cards.

---

## The one principle

**The human is never the bottleneck.** `draft` is permanent and unnagged; promotion to
`final` is always a human act on the human's schedule; nothing is ever marked stale. You
crystallise as much as you like, and spend the deliberate effort of promotion and study
only on the subset you actually choose to keep.
