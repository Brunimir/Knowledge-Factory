# The Knowledge Factory

**An agentic Personal Knowledge Management (PKM) system that turns raw, multi-disciplinary input into durable, interconnected, retrievable knowledge — and tells you exactly how much you can learn without falling behind.**

Most note-taking solutions are where information goes to die: you capture more than you ever revisit, connections never form, and nothing reaches long-term memory.

This system fixes that. It treats knowledge as a *production pipeline*, run by Claude Code over an Obsidian vault — where raw information is broken down into atomic concepts, woven into maps of related ideas, optionally drilled into memory as spaced-repetition flashcards, and composed into reusable solutions.

A built-in capacity model keeps the *learning* load honest. Because concepts can also be captured for reference only — without ever being studied — the vault grows at a pace you can actually retain, and you never become its bottleneck.

> This repository ships the **engine** — templates, extraction prompts, Claude Code skills, and orchestration scripts. You bring your own Obsidian vault; the system installs *over* it. The only vault content included is **one worked example** (the *Learning & Memory* MOC and its 11 concept notes under `20_Learning/`), so you can see real output.

*If you're a student, researcher, or professional trying to learn faster and retain more — the Knowledge Factory is for you.*

---

## 1. The Pipeline

### 1.1 Overall — the knowledge loop

Knowledge flows through five engines in a continuous loop:

![The five engines of the Knowledge Factory — Capture, Process, Interconnect, Retain (optional), Produce. Human verification is optional, Retain can be skipped for reference-only notes, and a gem-capture loop turns new insights from conversations into fresh input in the inbox.|697](5-engines.svg)

Raw material enters through **Capture**, is atomised into clean concept notes by **Process**, is related to the rest of the vault by **Interconnect**, is *optionally* committed to long-term memory by **Retain**, and is put to work by **Produce**. Solutions and flashcards in turn surface gaps, which feed the next capture cycle(Note to claude, to clarify)

### 1.2 The five engines

#### 🎣 Capture
Gets vault-worthy ideas out of conversations and sources and into the inbox, without polluting the vault.
- **`extract-gems`** — at the end of a substantive Claude conversation, identifies the genuinely vault-worthy "gems" and routes each one: a new candidate, a one-line refinement of an existing note, or *exclude*. Conversation-scoped, so it never runs the full pipeline by accident.
- **Extraction prompts** — `EXTRACT_PROMPT.md` (after a Claude conversation) and `EXTRACT_PROMPT_NotebookLM.md` (for books/PDFs or other soucres via NotebookLM) define a strict, machine-readable block format: a falsifiable claim, a named mechanism, a boundary condition, an application, and typed edges to other concepts.
- **Output:** raw structured notes land in `00_Inbox/` (Note Stock → Note Pipe → AI_Candidates), never directly in the vault.

#### ⚙️ Process
Turns raw inbox notes into atomic, self-contained concept notes.
- **`process-inbox`** (skill: `pkm-ingestion`) — runs a multi-phase ingestion pipeline (Phases 0–5): validates each note against a quality gate, writes one **atomic concept note** per teachable idea using the Feynman-style template, and surgically patches the relevant **Map of Content**.
- Enforces hard safety rules: never overwrites a note's full content, never invents facts, and never edits a `status: final` note except for two whitelisted patches.
- **Output:** concept notes in `20_Learning/21_Concepts/`, MOC patches in `20_Learning/22_Maps of Content/`.

#### 🔗 Interconnect
Makes the vault more than the sum of its notes.
- **`weave-links`** — a retroactive pass that discovers cross-domain relationships between concepts living in *different* MOCs, recording each edge in the canonical prose-verb format using a closed 7-label vocabulary (`supports`, `contradicts`, `prerequisite-for`, `instance-of`, `mechanism-of`, `mitigates`, `related-to`).
- **`visualise-moc {stem}`** — renders a two-tier Mermaid concept map (overview + cluster detail) for a MOC, fully derived from a pre-extracted manifest and regenerated idempotently.
- **`vault-health`** (skill: `pkm-review`) — surfaces *actionable* notes (final notes still awaiting flashcards), MOC coverage, orphans, flashcard coverage, expiring decisions, and acronym/knowledge gaps. Drafts and unreviewed notes are valid permanent states and are never nagged — the human is deliberately not the bottleneck.

#### 🧠 Retain
Locks finalised knowledge into long-term memory through spaced repetition.
- **`generate-flashcards`** (skill: `pkm-flashcards`) — generates dense Anki cards from `status: final` concept notes: three cards per concept (WHAT / HOW / WHEN), one batch file per run for safe AnkiConnect syncing.
- **Output:** flashcards in `20_Learning/23_FlashCards/`, synced to Anki. (The Capacity Model in §2 bounds how much new material enters Retain each week so the review load stays sustainable.)
- Anki rides your brain's forgetting curve — resurfacing each card the instant before it would be cleared — so every recall signals "keep this," converting short-lived facts into durable long-term memory.

#### 🚀 Produce (Output Bridge)
Puts mapped knowledge to work as real-world deliverables. (Canonically the **Output Bridge** / **Phase 5** in `CLAUDE.md` and the `pkm-solution` skill.)
- **`pkm-solution`** — the Phase 5 "Output Bridge": drafts a **Pattern** (reusable playbook), a **Solution** (a realised deliverable, optionally with a binary companion), or a **Decision** (a time-boxed decision record), with automatic use-count tracking on the source Patterns.
- **Output:** artefacts in `40_Solutions/`.

### 1.3 The command surface

Claude Code dispatches on the first word of your request. Seven commands:

| Command | Engine | What it does |
|---|---|---|
| `extract-gems` | Capture | Pull vault-worthy gems out of the current conversation. |
| `process-inbox` | Process | Ingest raw inbox notes → atomic concept notes + MOC updates. |
| `weave-links {scope}` | Interconnect | Discover & record cross-domain links between MOCs. |
| `visualise-moc {stem}` | Interconnect | Render a Mermaid concept map for one MOC. |
| `vault-health` | Interconnect | Audit coverage, gaps, and the flashcard backlog (never nags drafts). |
| `generate-flashcards` | Retain | Generate Anki flashcards from final concept notes. |
| `pkm-solution` | Produce | Draft a Pattern, Solution, or Decision from the vault. |

---

## 2. The Capacity Model — *how much can you actually retain?*

Capturing knowledge is easy; **retaining** it is the constraint. Spaced repetition only works if the daily review load stays sustainable — so the system models intake against a fixed, honest review budget.

The whole model reduces to one equation — the **monthly concept-retention capacity** `K`, derived directly from a sustainable daily review budget `D`:

> **K = (D · T · P) / (C · R)** — the model's monthly retention capacity.
>
> With the recommended values: **(31 × 7 × 4) / (3 × 8) = 868 / 24 ≈ 36 concepts/month**.

| Symbol | Meaning                                           | Recommended value |
| ------ | ------------------------------------------------- | ----------------- |
| **D**  | Sustainable daily review load you set (cards/day) | **31**            |
| **C**  | Cards generated per concept                       | **3**             |
| **R**  | Mean reviews per card over its lifetime           | **8**             |
| **T**  | Days per period                                   | **7** (one week)  |
| **P**  | Periods per month                                 | **4** (weeks)     |
| **K**  | Monthly concept-retention capacity *(the answer)* | **≈ 36 / month**  |

**How it's derived, in one breath.** The sustainable daily review load `D` is the real constraint. Each new concept spawns `C` cards, each reviewed `R` times over its life. So learning `X` concepts a week costs `(X · C · R) / T` reviews a day — set that equal to `D`, solve, and multiply by the `P` weeks in a month to get `K`.

The weekly lever falls out as `K / P` ≈ **9 new concepts/week**.

**This budget bounds *learning*, not crystallisation.** You can capture and crystallise far more than 36 concepts a month — reference notes need no flashcards. The budget governs only what you commit to memory.

Push *learning* past it and the daily review load climbs above budget. The model makes that trade-off explicit instead of letting the backlog grow silently — and tuning `C`, `R`, or `D` moves the capacity with it.

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
40_Solutions/        Patterns, Solutions, and Decisions
50_Admin/            vault administration
99_System/           templates, prompts, skills, and this system's scaffolding
```

### The artefacts

- **Concept note** — the atomic unit. A single teachable idea in Feynman structure: Core Idea, Mechanism (+ boundary condition), Application (when to use / when *not* to), and typed edges. Carries `status`, `reviewed`, and `flashcards` flags that gate everything downstream.
- **Map of Content (MOC)** — a living map of one domain: concept clusters, typed relationships, and a Cross-Domain Links section connecting it to other MOCs.
  - **Flashcards (+ Anki)** — three dense cards per final concept (WHAT / HOW / WHEN), synced to Anki via the flashcards-obsidian plugin for spaced repetition.
- **Solutions** — where knowledge becomes output:
  - **Solution doc** — a realised deliverable built from vault concepts (optionally with a `.pptx`/`.docx`/`.xlsx` companion).
  - **Pattern** — a reusable, abstracted playbook with a tracked use-count.
  - **Decision** — a time-boxed decision record with an expiry/review date.

### A worked example

To show real output — not just empty templates — the repo ships one fully-built domain: the **Learning & Memory** MOC and the 11 atomic concept notes it maps.

- **MOC** — `20_Learning/22_Maps of Content/MOC_Learning_and_Memory.md`: concept clusters, key tensions, cross-domain links, an embedded SVG concept-map, and the typed relationship graph.
- **Concepts** — `20_Learning/21_Concepts/`: Active Recall, Chunking, Spaced Repetition, Focused Mode, Diffuse Mode, Interleaving, Sleep and Learning, The Magical Number Seven, Cluster Processing, Information Overload Tax, Process vs Product.

> These are real notes in Obsidian format. On GitHub, `[[wikilinks]]` render as literal text (Obsidian resolves them; GitHub doesn't), and the cross-domain links point to MOCs outside this example.

---

## 4. Getting Started

### Requirements

- **[Obsidian](https://obsidian.md/)** — the vault host.
- **[Claude Code](https://claude.com/claude-code)** — the agent that runs the pipeline.
- **Python 3** — runs `generate_index.py` to build the vault index.
- **[Anki](https://apps.ankiweb.net/) + [AnkiConnect](https://ankiweb.net/shared/info/2055492159)** — flashcard review and sync.
- **Obsidian plugins:** `flashcards-obsidian` (card sync) and `Advanced URI` (triggering sync from the launcher).
- **[Node.js](https://nodejs.org/) + `@mermaid-js/mermaid-cli` (`mmdc`)** — only needed for `visualise-moc` diagram rendering (the launcher falls back to `npx`).

> *You can ask your Claude to walk you through this section step by step — paste this README and say "help me set up the Knowledge Factory in my Obsidian vault."*

### Install

1. **Clone** this repository.
   ```bash
   git clone https://github.com/Brunimir/knowledge-factory.git
   ```
2. **Copy the scaffolding into your vault**, preserving structure: place `CLAUDE.md` at your vault root, and the contents of `99_System/` into your vault's `99_System/`. To use the engines as Claude Code slash-commands, also copy `99_System/Claude/<skill>/` into your project's `.claude/skills/`.
3. **Configure your environment.** Copy the template and fill it in:
   ```bash
   cp .env.example .env
   ```
   ```ini
   ANTHROPIC_API_KEY=sk-ant-...
   VAULT_ROOT=C:\path\to\your\obsidian\vault
   OBSIDIAN_VAULT=YourVaultName
   ANKI_EXE=%LOCALAPPDATA%\Programs\Anki\anki.exe
   ```
   Alternatively, set `VAULT_ROOT` in your shell — every script falls back to its own directory if it's unset.

### Usage

The launchers handle pre-flight (index regeneration, validation) and post-flight (run summaries):

```powershell
# Process everything sitting in the inbox
.\launch-process-inbox.ps1

# Generate flashcards from final notes and sync them to Anki
.\launch-generate-flashcards.ps1

# Render the concept map for one MOC
.\launch-visualise-moc.ps1 MOC_Learning_and_Memory
```

A typical weekly cycle: capture during the week → `process-inbox` → review and mark notes `final` → `generate-flashcards` → periodically `weave-links` and `vault-health` to keep the graph healthy → `pkm-solution` when you need to *use* what you've learned.

---

## 5. Repo Layout

```
.
├─ CLAUDE.md                       # Command interface + safety rules (place at vault root)
├─ generate_index.py              # Builds VAULT_INDEX.json from the vault
├─ launch-process-inbox.ps1       # Capture → Process launcher
├─ launch-generate-flashcards.ps1 # Retain (flashcards) launcher + Anki sync
├─ launch-visualise-moc.ps1       # Interconnect (diagram) launcher
├─ extract_diagram_candidates.ps1  # Pre-extracts the per-MOC diagram manifest
├─ extract_flashcard_candidates.ps1# Pre-extracts the flashcard candidate manifest
├─ .env.example                   # Environment template (copy to .env)
├─ 99_System/
│  ├─ Readme.md                   # Core PKM philosophy / global rules
│  ├─ EXTRACT_PROMPT.md           # Capture: post-conversation extraction spec
│  ├─ EXTRACT_PROMPT_NotebookLM.md# Capture: NotebookLM source-extraction spec
│  ├─ *_Template.md               # Concept, MOC, Pattern, Solution, Decision, Idea, Flashcard templates
│  ├─ Annex_3_Pattern_Generator.md, Annex_4_Flashcard_Generator.md
│  ├─ acronym_allowlist.md, CANDIDATE_TEMPLATE.md, WEEKLY_REVIEW_CHECKLIST.md
│  └─ Claude/                     # The five engines (Claude Code skills)
│     ├─ gem-extraction/SKILL.md  # Capture
│     ├─ pkm-ingestion/SKILL.md   # Process
│     ├─ pkm-review/SKILL.md      # Interconnect (vault-health)
│     ├─ pkm-flashcards/SKILL.md  # Retain (flashcards)
│     └─ pkm-solution/SKILL.md    # Produce (solutions)
├─ docs/                          # Full phase specifications (read by CLAUDE.md)
│  ├─ inbox-pipeline.md           # process-inbox: Phases 0–5
│  ├─ visualisation-pipeline.md   # visualise-moc: Phases V-0 → V-6
│  └─ interconnect-pipeline.md    # weave-links: Phases IC-0 → IC-6
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
