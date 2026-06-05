---
name: pkm-solution
description: Drafts a Phase 5 artefact — Pattern, Solution, or Decision — from vault knowledge into 40_Solutions/. Use this skill whenever the user asks to draft a pattern, write a solution, capture a decision, build a presentation/memo/strategy from the vault, document an architectural choice, abstract a recurring approach, or mentions /pkm-solution, output-bridge, or Phase 5. Always shortlist candidates from VAULT_INDEX.json before reading any concept/pattern/decision file in full.
---

# PKM Solution Skill (Phase 5 — Output Bridge)

Drafts one of three artefact types into `40_Solutions/`:

| Type | Frontmatter `type:` | Filename suffix | What it is |
|---|---|---|---|
| Pattern  | `pattern`  | `{Title} - Pattern.md`  | Reusable approach to a recurring problem — the **how** |
| Solution | `solution` | `{Title} - Solution.md` | A delivered work product (deck, memo, plan, essay) built from vault notes |
| Decision | `decision` | `{Title} - Decision.md` | A documented conscious choice — the **what** |

Full Phase 5 reference: `40_Solutions/Personal Knowledge Management System - Solution.md`.
Validation rules and templates live in `99_System/` (Pattern_Template.md, Solution_Template.md, Decision_Template.md).

---

## Inputs required before starting

- `[BRIEF]` — the user's request: what they want produced, for whom, by when, with what constraints. If absent or unclear, ask before proceeding.
- `[VAULT_INDEX]` — contents of `00_Inbox/VAULT_INDEX.json`. Reject and stop if `generated` ≠ today (CLAUDE.md staleness gate).
- `[TEMPLATES]` — `99_System/Pattern_Template.md`, `Solution_Template.md`, `Decision_Template.md`. Read only the one matching the decided type.

**Do not scan the vault.** The only files this skill opens during shortlisting are `VAULT_INDEX.json` and (after human confirmation) the specific notes on the shortlist.

---

## Phase S-0 — Staleness and intent gate

1. Read `00_Inbox/VAULT_INDEX.json`. If `index["generated"]` ≠ today's date, print:
   `⚠ Index is from {date}. Run generate_index.py first, then retry.` and stop.
2. Restate the brief in one sentence. If you cannot, ask the user to sharpen it before continuing.
3. If the brief has multiple plausible readings — different artefact
   type (Pattern vs Solution vs Decision), different Solution mode
   (doc vs composite), different scope (one deliverable vs a series),
   different audience — NAME EACH READING and ask which is meant.
   Do not collapse ambiguity by picking the most likely option.
   Mis-identifying the type is the most expensive failure mode of
   this skill: it loads the wrong template and routes the artefact
   to the wrong validation gate.

---

## Phase S-1 — Decide the type

Use the decision tree (matches the spec exactly):

```
Is the output something you delivered or will deliver?
  (a presentation, a memo, a strategy doc, a CV, an email)
    └─→  SOLUTION

Is the output an abstract reusable approach to a recurring problem?
  (a methodology, a framework, a workflow)
    └─→  PATTERN

Is the output a documented conscious choice about how things should be done?
  (a standard set or changed, or a deliberate departure from one)
    └─→  DECISION
```

If two types could fit, pick the one **closer to action**: a Solution that proves a Pattern beats a draft Pattern with no use record.

State the chosen type out loud. Do not load any other template.

### S-1b — If type is Solution, pick the mode

A Solution is always recorded as a `.md` file in `40_Solutions/`. What
varies is whether the `.md` is itself the deliverable or whether it is
the vault record for a binary deliverable that lives alongside it.

| Mode | `.md` content | Companion file | Example |
|---|---|---|---|
| **Doc**       | `## The Solution` IS the deliverable (essay, memo, plan, strategy doc written in markdown) | none | `How to Implement the PKM System - Solution.md` |
| **Composite** | `## The Solution` describes the deliverable + points to companion(s) | `.pptx` / `.docx` / `.xlsx` / `.xlsm` sharing the same base name | `Q3 Strategy Pitch - Solution.md` + `Q3 Strategy Pitch - Solution.pptx` |

Ask the user:
> Is this a doc Solution (.md only) or composite (.md + companion file)? If composite, name the companion filename(s) — they must share the base `{Title} - Solution` and live in `40_Solutions/`.

Record the mode and any companion filenames before proceeding. The
companion may already exist or be planned for later — either is valid,
but the filename must be agreed up front so the `.md` declares it.

**The skill never creates or modifies binary files.** Composite mode
writes only the `.md`. The user produces the `.pptx`/`.docx`/`.xlsx`
separately.

---

## Phase S-2 — Shortlist from the index (no file reads)

Parse the index into five working sets, all sourced from `VAULT_INDEX.json`:

| Set | Source | Used for |
|---|---|---|
| `CONCEPTS`     | `notes[]`              | Underlying mechanisms |
| `PATTERNS`     | `patterns[]`           | Reusable approaches the brief may apply |
| `DECISIONS`    | `decisions[]`          | Constraints that bind the work (live only — archived is excluded) |
| `IDEAS`        | `ideas[]`              | Pre-production hypotheses to test |
| `VALID_STEMS`  | union of all five lists + `solutions[]` | Wikilink validation set |

### Scoring (deterministic, no file reads)

For each candidate in `CONCEPTS ∪ PATTERNS ∪ DECISIONS ∪ IDEAS`, compute:

1. **Domain hit (+3)** — `domain` matches the brief's domain. If the brief is cross-domain (`multiple`), skip this filter.
2. **Tag overlap (+2 per match)** — case-insensitive token intersection of `tags[]` with brief keywords. Tokenise the brief on whitespace and punctuation; lowercase both sides.
3. **Description / aliases / title substring hit (+1 per match)** — substring match on each.
4. **Pattern bonus (+1)** — `use_count > 0` (it has demonstrated value).

Sort each set by score descending. Cut at:
- **≤ 12 concepts**
- **≤ 5 patterns**
- **≤ 5 decisions**
- **≤ 3 ideas**

If a candidate's `tags[]` is empty, **mark it `(no tags — match quality reduced)`** in the shortlist. Do not drop it, but the human should know precision is weaker on that row.

### Present the shortlist

One markdown table grouped by type. Columns: `Stem | Score | Status | Domain | One-line (description) | Notes`. Notes column carries flags: `(no tags)`, `(superseded)` — though archived decisions should never appear, `(deviating: expires YYYY-MM-DD)`, `(status: draft)`.

Then ask:
> Confirm the shortlist. Add / remove stems by name. Reply `go` to proceed with the list as-is.

**Do not read any full note yet.** Wait for the human reply.

---

## Phase S-3 — Deep read confirmed stems only

Once the human confirms, read the full content of every stem on the final shortlist — and only those. Use the dedicated PowerShell pattern from CLAUDE.md (`Get-Content … -Raw -Encoding UTF8`). Do not read anything else.

If a confirmed stem is missing from the index (typo, renamed file), stop and ask. Do not silently substitute.

---

## Phase S-4 — Load the matching template

Open exactly one file from `99_System/`:

| Decided type | Template |
|---|---|
| Pattern  | `99_System/Pattern_Template.md`  |
| Solution | `99_System/Solution_Template.md` |
| Decision | `99_System/Decision_Template.md` |

If the template file is missing, stop and report. Do not freehand the structure.

---

## Phase S-5 — Draft the artefact

Fill the template strictly from the deep-read material plus the brief. No invented facts, no plausible-sounding fill. If a section has no source content, leave it blank and flag the gap in the post-draft report — do not embellish.

### Type-specific drafting rules

**Pattern**
- `ingredients[]` is a list of **exact concept stems** from the deep-read concepts. 3–5 atomic concepts is the canonical shape; more is acceptable if each adds a distinct mechanism.
- `problem` is one sentence — the recurring problem this pattern solves.
- `problem_type` ∈ `{learning, communication, leadership, decision-making, productivity}`.
- `use_count` starts at `0`. The skill bumps it on subsequent Solutions that cite this pattern (see Phase S-7).

**Solution**
- `built_from[]` lists every concept, pattern, idea, or prior solution stem the work actually drew on. Must be non-empty.
- `constrained_by[]` lists decision stems that bound this work (if any).
- `companion[]` lists binary deliverable filenames. Empty list = doc mode (the `.md` is the deliverable). Non-empty = composite mode. Each entry must:
  - Share the base name `{Title} - Solution` with this file
  - End in a supported extension: `.pptx`, `.ppt`, `.docx`, `.doc`, `.xlsx`, `.xlsm`, `.xls`, `.pdf`
  - Live in `40_Solutions/` (existence is not required at write time — the companion may be produced after the `.md`)
- The Vault sources block at the bottom enumerates: Patterns used / Concepts applied / Ideas explored / Decisions referenced — each entry must be a real stem from the index.
- `## The Solution` section content depends on mode:
  - **Doc:** the section is the actual deliverable text (essay, memo, plan).
  - **Composite:** the section describes the companion deliverable — what it is, who it's for, key sections — and names each companion file explicitly. Do not paste binary content; do not attempt to render slide outlines as if they were the deck itself unless the brief explicitly asks for a markdown outline as the deliverable.

**Decision**
- `decision_type` ∈ `{establishing, changing, deviating}`. State explicitly in the prose ("Establish:", "Change:", or "Deviate:").
- `expires:` field — **required if and only if** `decision_type == deviating`. Must be a valid `YYYY-MM-DD` after today.
- `affected_patterns[]` lists pattern stems this Decision establishes, changes, or temporarily inactivates.
- `## Rationale` section must be substantive — at least name the strongest rejected alternative and why it was rejected. Hollow rationales fail the gate.

### Stems are immutable

**Never invent a stem.** Every entry in `ingredients`, `built_from`, `constrained_by`, `affected_patterns`, `supersedes`, `superseded_by`, and every `[[wikilink]]` in the body must exist in `VALID_STEMS`. If the brief names something not in the vault:
- Write it in plain prose, not as a wikilink, with `(not yet in vault: "...")`.
- Flag in the post-write report so the user can decide whether to capture it.

---

## Phase S-6 — Pre-write validation gate

Run before any file write. Hard fail → fix inline once → still failing → write to `00_Inbox/QUARANTINE/` and report.

```
✓ Frontmatter parses as valid YAML
✓ type ∈ {pattern, solution, decision}
✓ filename ends in " - Pattern.md" / " - Solution.md" / " - Decision.md"
  and the suffix matches the type field
✓ title, status, description, domain, created, updated all present and non-empty
✓ domain ∈ {learning, writing, presentations, biology, strategy, multiple}

  (Pattern)
✓ problem present (1 sentence)
✓ ingredients[] non-empty; every stem exists in VALID_STEMS
✓ problem_type ∈ {learning, communication, leadership, decision-making, productivity}
✓ use_count is an integer (default 0)

  (Solution)
✓ built_from[] non-empty; every stem exists in VALID_STEMS
✓ constrained_by[] (if present) every stem exists in DECISIONS
✓ companion[] (if present): each entry shares the base `{Title} - Solution`
  with this file AND ends in .pptx/.ppt/.docx/.doc/.xlsx/.xlsm/.xls/.pdf.
  Existence is checked with Test-Path; missing companion → warn (not fail),
  log in the post-write report so the user knows to produce it.

  (Decision)
✓ decision_type ∈ {establishing, changing, deviating}
✓ if decision_type == deviating: expires present, parseable, and > today
✓ affected_patterns[] (if non-empty) every stem exists in PATTERNS
✓ supersedes / superseded_by (if present) every stem exists in DECISIONS ∪ archived
✓ ## Rationale section non-trivial (≥ 1 specific alternative named or ≥ 2 sentences)

  (All types)
✓ Every [[wikilink]] in the body exists in VALID_STEMS, or is written
  in plain prose with (not yet in vault: "...")
```

---

## Phase S-7 — Write and patch

### Write the file

Path: `40_Solutions/{Title} - {Type}.md`. Use `Set-Content -Path ... -Value $content -Encoding UTF8` exactly as specified in CLAUDE.md's Windows File Operation Patterns. Confirm the chosen filename does not already exist (`Test-Path`) — never overwrite an existing artefact. If it exists, stop and ask whether to bump the title.

For composite Solutions, the `.md` is the only file this skill writes. Binary companions (`.pptx`, `.docx`, `.xlsx`, `.xlsm`, `.pdf`) are produced by the user outside this skill. The `.md`'s `companion:` field and `## The Solution` section name the expected filename(s); the user is responsible for placing the binary in `40_Solutions/` under the agreed name.

### Use-count patch (Solutions only)

For every Pattern stem listed in the new Solution's `built_from[]` or `## Vault sources → Patterns used`, increment that Pattern's `use_count` by 1 using a **targeted regex patch**:

```powershell
$file = "$env:VAULT_ROOT\40_Solutions\{Pattern stem}.md"
$content = Get-Content $file -Raw -Encoding UTF8
$content = $content -replace 'use_count: (\d+)', {
    "use_count: $([int]$_.Groups[1].Value + 1)"
}
Set-Content -Path $file -Value $content -Encoding UTF8
```

**Never rewrite the Pattern file.** Patch the single line only. If the regex fails to match (legacy file shape), log and skip — do not invent a `use_count:` line.

### What NOT to patch

- Concept notes — they are immutable past `status: final` except for the two GF-3 patches. The pkm-solution skill never touches a concept file.
- MOCs — Phase 4 owns those.
- Existing solutions — never overwrite.
- Existing decisions — never overwrite. Superseding requires a *new* Decision file whose `supersedes` field names the old one and a one-line patch to the old decision's `status: superseded` and `superseded_by:` — escalate to the user, do not do it silently.
- **Binary companion files** (`.pptx`, `.docx`, `.xlsx`, `.xlsm`, `.pdf`, etc.) — never created, opened, read, moved, renamed, or deleted by this skill. The `.md` declares them; the user owns them.

---

## Phase S-8 — Report

Two outputs.

### (a) Markdown table — transcript

| Type | Title | Path | Stems referenced | Use_count patches | Status |
|---|---|---|---|---|---|

Status values:
- `Written, validated`
- `Written, validated, 2 patterns incremented`
- `Quarantined — {reason}`
- `Not written — user declined at shortlist`

Then the gap list, if any:
```
Gaps (referenced but not in vault):
  - "Some Thing" — flagged in body as (not yet in vault: "Some Thing")
  - "Other Thing" — likewise
```

### (b) JSON results

Write `00_Inbox/PKM_SOLUTION_RUN_RESULT.json`:

```json
{
  "generated": "YYYY-MM-DD",
  "type":      "pattern | solution | decision",
  "mode":      "doc | composite | n/a",
  "stem":      "Title - Type",
  "path":      "40_Solutions/Title - Type.md",
  "companion":          [ "Title - Solution.pptx" ],
  "companion_present":  [ true ],
  "shortlist": { "concepts": N, "patterns": N, "decisions": N, "ideas": N, "confirmed": N },
  "built_from":        [...],
  "ingredients":       [...],
  "affected_patterns": [...],
  "use_count_patched": [ "Pattern_Stem_1", ... ],
  "gaps":              [ "Thing 1", "Thing 2" ],
  "validation_errors": [],
  "status":            "written | quarantined | declined"
}
```

`mode` is `"doc"` or `"composite"` for Solutions, `"n/a"` for Pattern and Decision.
`companion[]` and `companion_present[]` are aligned arrays — the second
records whether each declared companion file exists on disk at write time.
Missing companions are a warning, not a failure.

UTF-8, no BOM, sorted keys not required.

---

## Safety rules

1. **Never invent stems.** Every cross-reference must resolve in `VALID_STEMS`. Plain-prose fallback for anything missing.
2. **Never read a concept/pattern/decision/idea file until it has been confirmed on the shortlist.** Shortlisting runs against the index only.
3. **Never overwrite an existing Phase 5 file.** `Test-Path` before write; stop on collision.
4. **Never edit a concept note** — concept files are out of scope for this skill (see CLAUDE.md SAFETY RULE 6).
5. **Use_count is the only field this skill patches in an existing Phase 5 file.** Single regex-targeted replacement. No full-file rewrites.
6. **Hollow Decisions fail the gate.** A Decision with no named alternative or one-sentence rationale is quarantined, not softened.
7. **Stale index halts everything.** Phase S-0 stop is hard — fix the index, then re-invoke.

---

## What this skill is NOT for

- Capturing ideas → `10_Ideas/` directly, no skill needed (ideas are pre-production).
- Editing existing concept notes → out of scope; flag for review session.
- Generating flashcards → that's `pkm-flashcards`.
- Vault audits, expiring-decision sweeps, suffix mismatches across the existing folder → that's `pkm-review`.
- Anything in `30_Sources/`, `20_Learning/22_Maps of Content/`, or `00_Inbox/` — read-only for this skill.
