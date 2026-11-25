# The Knowledge Factory

**Don't just store what you learn. Engineer it.**

Most AI note systems move knowledge out of your head and into a store. The Knowledge Factory is a Claude Code pipeline over an Obsidian vault with a step that moves it back in.

<a href="https://www.youtube.com/watch?v=BkIc0_dFqwE"><img src="https://i.ytimg.com/vi/BkIc0_dFqwE/maxresdefault.jpg" width="640" alt="Why You Forget What You Learn, and How to Engineer Your Memory with AI (introduction video)"></a>

▶ **[Why You Forget What You Learn, and How to Engineer Your Memory with AI](https://www.youtube.com/watch?v=BkIc0_dFqwE)**: the introduction video, about 7 minutes.

---

## Why: memory leaks

We learn a lot, but we retain little.

Memory is a system with an inflow, an outflow and a stock. When you take a course, some of it stays and raises the stock; some of it leaks out. Using an idea strengthens its pathway, and leaving it unused lets it fade (see [Active Recall](20_Learning/21_Concepts/Active_Recall.md) and [Spaced Repetition](20_Learning/21_Concepts/Spaced_Repetition.md) in the worked example). The problem is not "how do I store more". It is that more leaves than enters.

## What's different

None of the pieces are new. The trick is connecting them and pointing them at your head, not just at a folder.

| Approach | What it does | Moves knowledge back into your head? |
|---|---|---|
| **Zettelkasten** (Niklas Luhmann) | Links notes together | No |
| **Second brain** (Tiago Forte) | Captures, organises, distils and expresses notes for action | No |
| **LLM Wiki** (Andrej Karpathy) | An AI maintains your notes: checks consistency, organises, adds cross-references | No |
| **Spaced repetition** (e.g. Anki) | Brings each idea back just before you'd forget it | Yes, but only if the content was understood and connected first |
| **The Knowledge Factory** | Captures and verifies, breaks notes into one-idea concepts, connects them, turns the ones you choose into flashcards, and builds outputs from them | **Yes: the Retain step** |

The first three keep a copy outside your head, and the LLM Wiki takes the upkeep off your hands, which is a real gain. But put AI on every step and your second brain fills up beautifully while the connections in your own head never get built. So the Knowledge Factory gives the agent the admin and keeps the learning with you. The links between notes are not decoration: they are the cues that get you back to an idea.

### Who does what

- **You:** capture; approve each note in a review pass, which asks you to state its core idea from memory; review your flashcards; lead what you produce.
- **The agent:** checks captures against their sources, writes the one-idea notes, links them into maps of content, generates the flashcards, and drafts outputs from the vault.

Retain is almost all yours, because nobody can remember for you. The agent does the admin that makes it possible.

### One run, end to end

Two sources, say a book and a course. You take notes on each, yourself or with AI, and **Capture** checks them against the source. **Process** breaks the notes into concepts, one idea per note; a concept can draw on both sources, which is where ideas start to meet. **Interconnect** groups the concepts into a map of content, so nothing floats alone. **Retain** turns each concept you choose to study into a few flashcards that come back to you through spaced repetition. And when a real problem comes up, **Produce** starts from the concepts and solutions you already have, not from a blank page.

The repo ships the output of that run for one domain: see [A worked example](#a-worked-example).

### Evidence: run on its author's vault

As of 2026-11-16: 1,102 concept notes, 373 of them approved for study, and about 1,100 flashcards. 728 notes are kept as reference drafts on purpose and not yet studied.

Agent-written notes can look perfect and still be wrong. 1,060 of them were checked against the sources they cite: **779 faithful, 185 drifted, 38 fabricated, 58 unverifiable**. Capture now checks each claim against its source before it can become a note, so these defects are prevented, and nearly all the old ones have been fixed.

> This repository ships the **engine**: templates, extraction prompts, Claude Code skills, and orchestration scripts. You bring your own Obsidian vault; the system installs *over* it. The only vault content included is **one worked example** (the *Learning & Memory* MOC, its 11 concept notes and their flashcards, under `20_Learning/`), so you can see real output.

---

## 1. The Pipeline

### 1.1 Overall — the knowledge loop

Knowledge flows through five engines in a continuous loop:

![The five engines of the Knowledge Factory — Capture, Process, Interconnect, Retain, Produce. Retain, the step other systems leave out, is human-led and follows a human review with a recall test; reference-only notes skip it, and a gem-capture loop turns new insights from conversations into fresh input in the inbox.|697](5-engines.svg)

Raw material enters through **Capture**, is atomised into clean concept notes by **Process**, is related to the rest of the vault by **Interconnect**, is committed to long-term memory by **Retain** (for the notes you choose to study), and is put to work by **Produce**. Solutions and flashcards in turn surface gaps, which feed the next capture cycle.

### 1.2 The five engines

#### 🎣 Capture
Gets vault-worthy ideas out of your own notes, conversations and sources and into the inbox, without polluting the vault.
- **Your own notes** — write a note by hand as a *flying note* with just two fields, `Concept:` and `Why it matters:`. Keep it in `00_Inbox/Note Stock/` while you finish it (your space: the agent never processes it), then move it to `Note Pipe/`, and `process-inbox` turns it into a full concept note.
- **`extract-gems`** — at the end of a substantive Claude conversation, identifies the genuinely vault-worthy "gems" and routes each one: a new candidate, a one-line refinement of an existing note, or *exclude*. Conversation-scoped, so it never runs the full pipeline by accident.
- **Extraction prompts** — `EXTRACT_PROMPT.md` (after a Claude conversation) and `EXTRACT_PROMPT_NotebookLM.md` (for books/PDFs or other sources via NotebookLM) define a strict, machine-readable block format: a falsifiable claim, a named mechanism, a boundary condition, an application, and typed edges to other concepts.
- **Output:** raw structured notes land in `00_Inbox/` (Note Stock → Note Pipe → AI_Candidates), never directly in the vault.
- **`verify-capture-fidelity`** (skill: `pkm-capture-verify`) — judges each checkable claim in a capture against its frozen source before it can become a note, writing a faithful/drifted/fabricated/unverifiable verdict; a fabrication caught here costs one Note Pipe edit, not a fix to a note that is already approved and locked. Runs automatically as the first step of `process-inbox`, so a clean capture pays nothing extra for it.

#### ⚙️ Process
Turns raw inbox notes into atomic, self-contained concept notes.
- **`process-inbox`** (skill: `pkm-ingestion`) — runs a multi-phase ingestion pipeline (Phases 0–5): validates each note against a quality gate, writes one **atomic concept note** per teachable idea using the Feynman-style template, and surgically patches every relevant **Map of Content** — a concept can belong to more than one MOC (its `moc:` field is a list), so a cross-cutting idea is mapped into each domain it touches.
- Enforces hard safety rules: never overwrites a note's full content, forbids inventing facts (and checks for it, see [Evidence](#evidence-run-on-its-authors-vault)), and never edits a `status: final` note except for three whitelisted patches.
- **Output:** concept notes in `20_Learning/21_Concepts/`, MOC patches in `20_Learning/22_Maps of Content/`.

#### 🔗 Interconnect
Makes the vault more than the sum of its notes.
- **`weave-links`** — a retroactive pass that finds relationships between concepts in *different* MOCs and records each as a typed edge, from a closed vocabulary of 7 labels (`supports`, `contradicts`, `prerequisite-for`, `instance-of`, `mechanism-of`, `mitigates`, `related-to`) plus 5 optional structural ones for architecture-style MOCs (`contains`, `flows-into`, `inherits-to`, `peers-with`, `protects`). A similarity search shortlists candidate pairs first (the same search `process-inbox` uses), and the agent then judges each pair against both notes' text before writing anything. Run it with `launch-weave-links.ps1 -MocStems A B [...]`; the threshold and which pass owns which edges are in [`docs/interconnect-pipeline.md`](docs/interconnect-pipeline.md).
- **`visualise-moc {stem}`** — renders a two-tier Mermaid concept map (overview + cluster detail) for a MOC. **Fully deterministic** — `extract_diagram_candidates.ps1` builds the manifest and `build_diagrams.ps1` renders + patches the MOC; no agent is invoked.
- **`vault-health`** (skill: `pkm-review`) — surfaces *actionable* notes (final notes still awaiting flashcards), MOC coverage, orphans, flashcard coverage, and acronym/knowledge gaps. Drafts are a valid permanent state and are never nagged — the human is deliberately not the bottleneck.

#### 🧠 Retain
Locks finalised knowledge into long-term memory through spaced repetition.
- **`generate-flashcards`** (skill: `pkm-flashcards`) — generates short Anki cards from `status: final` concept notes: one idea per card, up to 6 per concept, about 9 words on the back and 18 at most, one batch file per run for safe AnkiConnect syncing.
- **Output:** flashcards in `20_Learning/23_FlashCards/`, synced to Anki. (The Capacity Model in §2 bounds how much new material enters Retain each week so the review load stays sustainable.)
- Anki rides your brain's forgetting curve — resurfacing each card the instant before it would be cleared — so every recall signals "keep this," converting short-lived facts into durable long-term memory.

#### 🚀 Produce
Puts mapped knowledge to work as real-world deliverables, built from the concepts already in the vault.
- **`pkm-solution`** — drafts a **Pattern** (a reusable, abstracted playbook) or a **Solution** (a realised deliverable, optionally with a binary companion), with automatic use-count tracking on the source Patterns.
- **Output:** artefacts in `40_Solutions/`.

### 1.3 The command surface

Claude Code dispatches on the first word of your request. Eight pipeline commands, plus one cross-cutting retrieval command:

| Command | Engine | What it does |
|---|---|---|
| `extract-gems` | Capture | Pull vault-worthy gems out of the current conversation. |
| `verify-capture-fidelity` | Capture | Judge captured claims against their frozen source before they become notes; runs automatically before every `process-inbox`. |
| `process-inbox` | Process | Ingest raw inbox notes → atomic concept notes + MOC updates. |
| `weave-links {scope}` | Interconnect | Discover & record cross-domain links between MOCs. |
| `visualise-moc {stem}` | Interconnect | Render a Mermaid concept map for one MOC. |
| `vault-health` | Interconnect | Audit coverage, gaps, and the flashcard backlog (never nags drafts). |
| `generate-flashcards` | Retain | Generate Anki flashcards from final concept notes. |
| `pkm-solution` | Produce | Draft a Pattern or Solution from the vault. |
| `vault-query {question}` | *Retrieve* | Answer an ad-hoc question with a cited, synthesised answer drawn only from the vault (or admit it has nothing). |

> `vault-query` is a **read-only, cross-cutting retrieval command**, not a sixth pipeline engine: it spans the whole vault to *use* what the five engines have crystallised (the "Usage" job in §6), and never writes a note.

---

## 2. The Capacity Model — *how much can you actually retain?*

**With about 31 flashcard reviews a day, you can commit about 36 new concepts a month to memory, roughly 9 a week.** You can capture far more than that: the budget only limits what you study, because reference notes need no flashcards.

Capturing knowledge is easy; **retaining** it is the constraint. Spaced repetition only works if the daily review load stays sustainable — so the system models intake against a fixed, honest review budget. In the leaky-bucket terms above, this is the inflow you can sustain.

The whole model reduces to one equation — the **monthly concept-retention capacity** `K`, derived directly from a sustainable daily review budget `D`:

> **K = (D · T · P) / (C · R)** — the model's monthly retention capacity.
>
> With the recommended values: **(31 × 7 × 4) / (3 × 8) = 868 / 24 ≈ 36 concepts/month**.

| Symbol | Meaning                                           | Recommended value |
| ------ | ------------------------------------------------- | ----------------- |
| **D**  | Sustainable daily review load you set (cards/day) | **31**            |
| **C**  | Cards per concept, on average (the generator allows up to 6) | **3**             |
| **R**  | Mean reviews per card over its lifetime           | **8**             |
| **T**  | Days per period                                   | **7** (one week)  |
| **P**  | Periods per month                                 | **4** (weeks)     |
| **K**  | Monthly concept-retention capacity *(the answer)* | **≈ 36 / month**  |

**How it's derived, in one breath.** The sustainable daily review load `D` is the real constraint. Each new concept spawns `C` cards, each reviewed `R` times over its life. So learning `X` concepts a week costs `(X · C · R) / T` reviews a day — set that equal to `D`, solve, and multiply by the `P` weeks in a month to get `K`.

The weekly lever falls out as `K / P` ≈ **9 new concepts/week**.

Push *learning* past the budget and the daily review load climbs above it. The model makes that trade-off explicit instead of letting the backlog grow silently — and tuning `C`, `R`, or `D` moves the capacity with it.

---

## 3. What the System Produces

### The Vault (Obsidian)

A numbered folder taxonomy keeps capture, learning, and output cleanly separated:

```
00_Inbox/            raw capture (Note Stock → Note Pipe → AI_Candidates) + generated indexes
10_Ideas/            half-formed ideas not yet atomic concepts
20_Learning/
  ├─ 21_Concepts/        atomic concept notes (the core unit of knowledge)
  ├─ 22_Maps of Content/ MOCs — clusters + typed edges + cross-domain links
  ├─ 23_FlashCards/      generated Anki decks (one file per batch)
  └─ 24_Diagrams/        rendered Mermaid concept maps
30_Sources/          source material (books, PDFs, references)
40_Solutions/        Patterns and Solutions (knowledge turned into output)
60_Admin/            vault administration
99_System/           templates, prompts, skills, and this system's scaffolding
```

### The artefacts

- **Concept note** — the atomic unit. A single teachable idea in Feynman structure: Core Idea, Mechanism (+ boundary condition), Application (when to use / when *not* to), and typed edges. Carries `status` and `flashcards` flags that gate everything downstream, plus a derived `trust` score (from `source_count`) that reflects how corroborated the claim is.
- **Map of Content (MOC)** — a living map of one domain: concept clusters, typed relationships, and a Cross-Domain Links section connecting it to other MOCs. A single concept can be mapped into several MOCs at once (its `moc:` field is a list), so cross-cutting ideas surface in every domain they touch.
- **Flashcards (+ Anki)** — short one-idea cards, up to 6 per final concept, synced to Anki via the flashcards-obsidian plugin for spaced repetition.
- **Solutions** — where knowledge becomes output:
  - **Solution doc** — a realised deliverable built from vault concepts (optionally with a `.pptx`/`.docx`/`.xlsx` companion).
  - **Pattern** — a reusable, abstracted playbook with a tracked use-count.

### The artefact lifecycle

Every knowledge artefact moves through **one consistent lifecycle**. `status` gates a
concept, a MOC, a Pattern, and a Solution alike. Only concept notes take the second
step: flashcards are generated from concept notes alone, never from a MOC, a Pattern
or a Solution.

```
MOC, Pattern, Solution:  draft  ──(human review pass)──▶  final
Concept note:            draft  ──(human review pass)──▶  final + flashcards:false  ──(generate-flashcards / opt-out)──▶  final + flashcards:true
```

- **`status: draft`** — the resting state for everything the agent writes and most of
  what you write. It is a **valid permanent state**: a reference note you never intend
  to study can live as `draft` forever. Drafts are never nagged.
- **`status: final`** — *you* promote a note to `final` in a single review pass, against
  three criteria: the core idea is statable from memory in one sentence, every wikilink
  resolves, and at least one real application is named. The agent **never** sets `final`
  on its own, and never edits a `final` note except three whitelisted patches (flashcards,
  the `updated` date bump, and the trust-score patch below).
- **`flashcards`** (concept notes only) — flips to `true` when cards are generated *or* when you deliberately
  opt a note out of studying ("reviewed, no need to study"). A note is eligible for
  `generate-flashcards` only when `status: final AND flashcards: false`.
- **`trust`** — derived from `source_count` (how many sources back the note) by
  `concept_schema_sync.ps1`, and re-checked for drift by `generate_index.py`. Descriptive,
  not a gate: it does not block promotion or flashcard generation.

The design principle: **the human is never the bottleneck.** `draft` has no review SLA,
nothing is ever flagged as "stale," and you promote only the notes you choose — the rest
rest indefinitely. See [`docs/lifecycle.md`](docs/lifecycle.md) for the full reference.

### A worked example

To show real output — not just empty templates — the repo ships one fully-built domain: the **Learning & Memory** MOC, the 11 atomic concept notes it maps, and their flashcards.

- **MOC** — `20_Learning/22_Maps of Content/MOC_Learning_and_Memory.md`: concept clusters, key tensions, cross-domain links, and the typed relationship graph.
- **Concepts** — `20_Learning/21_Concepts/`: Active Recall, Chunking, Spaced Repetition, Focused Mode, Diffuse Mode, Interleaving, Sleep and Learning, The Magical Number Seven, Cluster Processing, Information Overload Tax, Process vs Product.
- **Flashcards** — [`20_Learning/23_FlashCards/Flashcards_MOC_Learning_and_Memory.md`](20_Learning/23_FlashCards/Flashcards_MOC_Learning_and_Memory.md): the Retain step's output, 33 cards (3 per concept). *Earlier format:* they were generated in April 2026 with long answers, before the generator moved to short one-idea cards; new runs produce the short format.

> These are real notes in Obsidian format. On GitHub, `[[wikilinks]]` render as literal text (Obsidian resolves them; GitHub doesn't), and the cross-domain links point to MOCs outside this example.

---

## 4. Getting Started

### Requirements

- **Windows + PowerShell** — the launchers are PowerShell scripts; Mac and Linux are not supported today.
- **[Obsidian](https://obsidian.md/)** — the vault host.
- **[Claude Code](https://claude.com/claude-code)** — the agent that runs the pipeline.
- **Python 3** — runs `generate_index.py` to build the vault index.
- **[Anki](https://apps.ankiweb.net/) + [AnkiConnect](https://ankiweb.net/shared/info/2055492159)** — flashcard review and sync.
- **Obsidian plugins:** `flashcards-obsidian` (card sync) and `Advanced URI` (triggering sync from the launcher).
- **[Node.js](https://nodejs.org/) + `@mermaid-js/mermaid-cli` (`mmdc`)** — only needed for `visualise-moc` diagram rendering (the launcher falls back to `npx`).

> *You can ask your Claude to walk you through this section step by step — paste this README and say "help me set up the Knowledge Factory in my Obsidian vault."*

### Install

1. **Clone** this repository.
   ```powershell
   git clone https://github.com/Brunimir/Knowledge-Factory.git
   ```
2. **Copy the scaffolding into your vault**, preserving structure: place `CLAUDE.md` at your vault root, and the contents of `99_System/` into your vault's `99_System/`. To use the engines as Claude Code slash-commands, also copy `99_System/Claude/<skill>/` into your project's `.claude/skills/`.
3. **Point the scripts at your vault.** The launchers read three environment variables. Set them in your PowerShell session, or in your PowerShell profile to keep them:
   ```powershell
   $env:VAULT_ROOT     = "C:\path\to\your\obsidian\vault"           # if unset, each script uses its own folder
   $env:OBSIDIAN_VAULT = "YourVaultName"                            # optional: defaults to the vault folder's name
   $env:ANKI_EXE       = "$env:LOCALAPPDATA\Programs\Anki\anki.exe" # optional: this is the default
   ```
   No API key goes in this repo: Claude Code signs in on its own.

### Usage

The launchers handle pre-flight (index regeneration, validation) and post-flight (run summaries):

```powershell
# Process everything sitting in the inbox
.\launch-process-inbox.ps1

# Generate flashcards from final notes and sync them to Anki
.\launch-generate-flashcards.ps1

# Render the concept map for one MOC
.\launch-visualise-moc.ps1 MOC_Learning_and_Memory

# Weave cross-domain links between two or more MOCs (needs 2+ MOCs in your vault;
# the repo ships only MOC_Learning_and_Memory, so substitute your own second domain)
.\launch-weave-links.ps1 -MocStems MOC_Learning_and_Memory MOC_Your_Other_Domain
```

A typical weekly cycle: capture during the week → `process-inbox` → review and mark notes `final` → `generate-flashcards` → periodically `weave-links` and `vault-health` to keep the graph healthy → `pkm-solution` when you need to *use* what you've learned.

---

## 5. Repo Layout

```
.
├─ CLAUDE.md                       # Command interface + safety rules (place at vault root)
├─ generate_index.py              # Builds VAULT_INDEX.json from the vault
├─ kzn_paths.py                   # Resolves the vault root (VAULT_ROOT) for the Python scripts
├─ concept_schema_sync.ps1        # Maintains the source_count/trust score on concept notes
├─ launch-process-inbox.ps1       # Capture → Process launcher (incl. GATE-KF-13/14 capture-fidelity gates)
├─ gate_quote_fidelity.py         # GATE-KF-13: verbatim `quote:` fidelity check
├─ capture_fidelity.py            # GATE-KF-14: manifest for the capture-fidelity judgment gate
├─ fidelity_ledger.py             # Shared faithful/drifted/fabricated/unverifiable verdict ledger
├─ launch-generate-flashcards.ps1 # Retain (flashcards) launcher + Anki sync
├─ gate_kf05.py                   # GATE-KF-05: flashcard content checks, run before Anki sync
├─ verify_flashcard_sync.ps1      # Reconciles markdown vs. AnkiConnect (source of truth)
├─ launch-visualise-moc.ps1       # Interconnect (diagram) launcher — fully deterministic
├─ build_diagrams.ps1             # Renders the Mermaid SVGs and patches the MOC (no agent involved)
├─ launch-weave-links.ps1         # Interconnect (weave-links) launcher — builds the candidate manifest
├─ overlap_candidates.py          # Shared similarity candidate generator (process-inbox + weave-links)
├─ extract_diagram_candidates.ps1  # Pre-extracts the per-MOC diagram manifest
├─ extract_flashcard_candidates.ps1# Pre-extracts the flashcard candidate manifest
├─ requirements.txt               # Python dependencies (PyYAML/rapidfuzz/numpy core; per-skill locks for the rest)
├─ .env.example                   # Environment variable names (reference only; no script loads it)
├─ 99_System/
│  ├─ Readme.md                   # Core PKM philosophy / global rules
│  ├─ EXTRACT_PROMPT.md           # Capture: post-conversation extraction spec
│  ├─ EXTRACT_PROMPT_NotebookLM.md# Capture: NotebookLM source-extraction spec
│  ├─ *_Template.md               # Concept, MOC, Pattern, Solution, Idea, Flashcard templates
│  ├─ Annex_3_Pattern_Generator.md, Annex_4_Flashcard_Generator.md  (both superseded; kept as pointers)
│  ├─ acronym_allowlist.md, CANDIDATE_TEMPLATE.md, WEEKLY_REVIEW_CHECKLIST.md
│  └─ Claude/                     # The five engines + cross-cutting retrieval (Claude Code skills)
│     ├─ gem-extraction/SKILL.md      # Capture
│     ├─ pkm-capture-verify/SKILL.md  # Capture (verify-capture-fidelity)
│     ├─ pkm-ingestion/SKILL.md       # Process
│     ├─ pkm-review/SKILL.md          # Interconnect (vault-health)
│     ├─ vault-graph/SKILL.md         # Interconnect (similarity + graph topology)
│     ├─ pkm-flashcards/SKILL.md      # Retain (flashcards)
│     ├─ pkm-solution/SKILL.md        # Produce (solutions)
│     └─ vault-retrieval/SKILL.md     # Retrieve (vault-query: cited hybrid retrieval)
├─ docs/                          # Full phase specifications (read by CLAUDE.md)
│  ├─ inbox-pipeline.md           # process-inbox: Phases 0–5
│  ├─ visualisation-pipeline.md   # visualise-moc: Phases V-0 → V-6
│  ├─ interconnect-pipeline.md    # weave-links: Phases IC-0 → IC-6
│  ├─ flashcards-pipeline.md      # generate-flashcards: Phases GF-0 → GF-4
│  └─ lifecycle.md                # The status/flashcards/trust state machine, in full
└─ LICENSE
```

> The engine deep-dives in §1 are the high-level summary; the complete phase-by-phase specifications live in `docs/` and are loaded on demand by `CLAUDE.md` when the matching command runs.

---

## 6. Conclusion

The Knowledge Factory treats knowledge work as an engineering problem: a pipeline with clear stages, strict quality gates, and a capacity model that matches the learning load to what a human can actually retain.

It starts by breaking every source down to its **smallest common denominator — the atomic concept**: one self-contained, reusable idea. Everything downstream works only because knowledge is atomic.

From that unit, it separates four jobs that most note-taking blurs together:

- **Crystallisation** — raw input becomes atomic, interconnected, queryable concepts.
- **Learning** — a *chosen* subset is committed to long-term memory via spaced repetition.
- **Usage** — you retrieve and recombine what you've kept, on demand.
- **Production** — knowledge is turned into real-world deliverables.

You crystallise far more than you memorise. Reference concepts live in the vault, searchable whenever you need them, while the ~36-a-month budget is spent only on what you deliberately choose to learn.

Capture without crystallisation is noise; knowledge you never use stays inert. So run all five engines over an Obsidian vault, harvest new gems with every cycle, and scattered reading compounds into a body of **atomic, interconnected** knowledge that is crystallised, selectively retained, and *applied*.

It's opinionated by design, but every piece — the templates, the prompts, the skills, the capacity constants — is yours to tune.

---

## License

Licensed under the **[Apache License 2.0](LICENSE)** — © 2026 Bruno Bodson.
