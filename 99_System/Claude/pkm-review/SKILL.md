---
name: pkm-review
description: Performs periodic vault health checks, surfaces notes needing review, audits MOC coverage, and manages the VAULT_INDEX.json. Use this skill whenever the user asks to review the vault, check which notes need attention, find stale or unreviewed notes, audit MOC completeness, update the vault index, check flashcard coverage, find orphaned notes, surface open questions across MOCs, or asks what needs to be done in the vault. Also trigger when the user asks for a vault summary, a progress report, or mentions the Delegation Diligence Loop in the context of their PKM system.
---

# PKM Vault Review Skill

Performs structured vault health checks and surfaces actionable items. Reads from `VAULT_INDEX.json` and targeted note files — does not scan the full vault on every run.

## Review types

Call the relevant section based on what the user requests. For a full health check, run all sections.

---

## Review 1 — Actionable notes

The vault has NO review SLA. `draft` is a valid, permanent
resting state with no time limit. A concept may stay `draft` forever — it
might be a reference note never meant to be studied, or content not yet chosen
for promotion. Volume is expected to be high (gem-extraction feeds the vault
faster than any human can attentively review), and the human is deliberately
NOT the throughput bottleneck. Unreviewed notes are therefore NEVER flagged as
"stale" or "needing attention" on age.

Surface ONLY genuinely actionable notes:
- `flashcards: false` AND `status: final` AND `concept_role: study` (or absent —
  `study` is the default) → approved and awaiting flashcards (run
  `generate-flashcards`). Not raised for notes the human has opted out of
  studying via `flashcards: true` (see Review 3). **Never raised for
  `concept_role: reference` or `concept_role: scaffold`** — those are kept for
  lookup or structure, not study, so `flashcards: false` on them is the correct
  terminal state, not a gap.

Output format:
```
## Actionable notes
| Title | Type | Status | Issue |
| Chunking | concept | final | Approved — flashcards not yet generated |
```

For visibility only — never as a to-do list — the summary may report how many
notes sit in each state (see the Summary section).

---

## Review 2 — MOC coverage audit

For each MOC in `VAULT_INDEX.json`:
1. Count how many concept notes list this MOC in their `moc` field
2. Flag any MOC with fewer than 4 notes (below minimum viable cluster)
3. Flag any concept note with `moc: []` (orphaned — not assigned to any MOC)
4. Check if any MOC has not been updated in 60+ days

Output format:
```
## MOC coverage
| MOC | Note count | Last updated | Flag |
| Biology of Performance | 15 | 2025-03-01 | — |
| Prose Momentum | 2 | 2024-11-12 | Below threshold (min 4) |

## Orphaned notes (no MOC assigned)
| Title | Domain | Suggested MOC |
```

---

## Review 3 — Flashcard coverage

For each finalised concept note (`status: final`) with `concept_role: study`
(or no `concept_role` — `study` is the default):
- Check `flashcards` field
- If `flashcards: false`, flag it (approved, cards still to be generated)

Skip `concept_role: reference` and `concept_role: scaffold` notes entirely —
they are not study material, so `flashcards: false` on them is correct and is
never a coverage gap.

`flashcards: true` on a final note is terminal and is NEVER flagged: it means
either the cards were generated OR the human deliberately opted the note out of
studying ("reviewed, no need to study"). Do not expect a flashcard file to
exist for such a note, and never treat its absence as a gap.

Also check `20_Learning/23_FlashCards/` for consolidated files:
- List which MOC decks exist
- Flag any MOC that has `status: final` + `flashcards: false` +
  `concept_role: study` notes but no flashcard file (a real coverage gap —
  opted-out `flashcards: true` notes and `reference`/`scaffold` notes do not
  count)

**Sync-reality check (loop A — closes the silent-fail gap).** A note can be
marked `flashcards: true` while its cards never reached Anki (the documented
AnkiConnect duplicate trap). A successfully synced flashcard file contains Anki
ID markers (`<!--ID:` or a `^NNNNNNNNNNNNN` line). So:
- For each file in `20_Learning/23_FlashCards/`, check for at least one Anki ID
  marker. **Flag any flashcard file that has ZERO ID markers** — its cards are
  not in Anki. (Cross-check `00_Inbox/FLASHCARD_RUN_RESULT.json` →
  `sync_verification[]` if present: any `synced: false` entry is a confirmed
  silent-fail to re-sync.)
- This is a committed-artefact gap (cards were written but not landed), so it IS
  surfaced — distinct from the never-nagged draft backlog.

Output format:
```
## Flashcard coverage
| MOC | Final notes | Flashcard file exists | Notes without cards |

## Flashcard sync gaps (loop A)
| Flashcard file | Anki IDs present? | Action |
| Flashcards_Threat_Protection - Batch 2.md | NO | Re-sync; check dev console for duplicate errors |
```

---

## Review 4 — Open questions surface

Scan each MOC file's `## Open Questions` section.
Collect all open questions across all MOCs.
Group by domain and sort by MOC.

Output format:
```
## Open questions across vault
### {MOC name}
- {Question 1}
- {Question 2}
```

Use this to identify where new source material or concept notes would have the highest impact.

---

## Review 5 — MOC candidate detection

Scan concept notes with `moc: []` or notes in `SATELLITE` status.
If 3 or more unassigned notes share a domain, flag as a MOC candidate.

Output format:
```
## MOC candidates
| Cluster | Notes | Suggested title |
| Personal Positioning | Prime Real Estate, Dialect Mirroring, The Presentation Halo Effect, AMR Framework | MOC_Personal_Positioning |
```

---

## Review 6 — Vault gap scan (acronyms + missing concepts)

Surface acronyms and technical terms used in `status:final` concept notes that have no matching vault concept and no inline expansion. Catches gaps that escaped the ingestion-time audit (e.g. acronyms in Mechanism or Application sections from older runs, or terms the agent silently treated as "general knowledge").

**Never edits any concept note** — Rule 6 makes final notes immutable except for the two GF-3 patches. This review only writes the report.

### Inputs

- `00_Inbox/VAULT_INDEX.json` — `notes[]`, `patterns[]`, `decisions[]`, `solutions[]`, `ideas[]` (for matching against vault terms; staleness gate applies)
- `99_System/acronym_allowlist.md` — the `allowlist:` YAML list (skipped from flagging)
- Concept note files at `20_Learning/21_Concepts/*.md` where `status: final`

### Procedure

1. **Build `VALID_TERMS`** — union of every `stem`, `title`, and entry from `aliases[]` across `notes`, `patterns`, `decisions`, `solutions`, `ideas`. Lowercase for comparison.

2. **Load `ALLOWLIST`** — parse the `allowlist:` field from `99_System/acronym_allowlist.md` frontmatter. Lowercase entries.

3. **For each `status: final` concept note**:
   a. Read the file. Strip frontmatter (`--- … ---`). Strip fenced code blocks (` ``` … ``` `) and inline backtick spans — they hold protocols, identifiers, etc. that are not jargon to flag.
   b. Extract every `\b[A-Z]{2,}\b` token from the remaining body prose.
   c. Classify each token:

   | Result | Condition |
   |---|---|
   | SKIP — allowlisted | lowercased token ∈ `ALLOWLIST` |
   | SKIP — in vault | lowercased token ∈ `VALID_TERMS` (including the note's own title/aliases) |
   | SKIP — expanded inline | within 80 chars before or after the acronym, a parenthetical expansion exists whose word initials spell the acronym, e.g. `Network File System (NFS)` or `NFS (Network File System)` |
   | GAP | none of the above |

4. **Aggregate**:
   - Count occurrences per gap acronym across all final notes.
   - Capture the first surrounding sentence (≤ 200 chars) as context per occurrence.
   - Compute per-note gap density.

5. **Write `00_Inbox/VAULT_GAPS_REPORT.md`** (UTF-8, no BOM):

```markdown
# Vault Gaps Report
Generated: YYYY-MM-DD
Final notes scanned: N
Distinct acronyms flagged: N
Total gap occurrences: N

## Top priority — acronyms used ≥ 3 times with no vault concept
| Acronym | Count | Best-guess expansion | Sample notes |
|---|---|---|---|
| SMB | 7 | (not found in any context) | Azure_Files_Storage, Azure_NetApp_Files, ... |

## All flagged acronyms
| Acronym | Count | First context |
|---|---|---|
| SMB | 7 | "supports both SMB and NFS protocols" (Azure_Files_Storage) |

## Notes with highest gap density
| Note | Gap count | Acronyms |
|---|---|---|
| Azure_NetApp_Files | 4 | SMB, NFS, AD, LDAP |

## Resolution menu (human decides per acronym)
- **Add concept** — write a new concept note for the term so future ingestion resolves the reference. Best for terms used ≥ 3 times.
- **Add to allowlist** — append to `99_System/acronym_allowlist.md` if the term is truly atomic and not worth its own concept.
- **Patch source note** — only valid if the note is NOT yet `status: final`. Final notes are immutable (Rule 6).
- **Accept** — acknowledge the gap; it will reappear on the next scan until one of the above is done.
```

### Safety

- Reads concept files only. Never writes to `20_Learning/21_Concepts/`.
- Code-fence and inline-backtick stripping prevents false positives on identifiers like `SELECT`, `HTTP/2`, `JSON`.
- Self-reference is excluded (a note titled "RBAC" using `RBAC` in its own body is not a gap).
- If `99_System/acronym_allowlist.md` is missing or malformed, log a warning and proceed with an empty allowlist (Review 6 still runs but flags more aggressively).
- If `VAULT_INDEX.json` is stale (`generated` ≠ today), STOP — the false-positive rate on freshly-added vault concepts would be too high.

---

## Review 7 — Cluster health

Note counts say nothing about whether the *clustering* is good. A MOC can have
plenty of notes but clusters that are oversized (concepts dropped at render),
fragmented into singletons, or incoherent (a concept's relationships pull into a
different cluster). Run the cluster-health gate:

```
powershell -ExecutionPolicy Bypass -File cluster_health.ps1
```

It parses every MOC's `## Concept Landscape` clusters and `## Concept
Relationships` edges and flags, per cluster:

- **OVERSIZED (> 9 concepts)** — the diagram silently drops the overflow; the
  cluster is doing too much. Split it: `recluster.ps1 -MocStem {stem}` drafts a
  split by token + edge similarity for the human to confirm.
- **singleton (1 concept)** — boundary too fine; merge into the nearest sibling
  (recluster.ps1 proposes the merge).
- **list-only (0 structural edges)** — no learnable backbone; run
  `connect_clusters.ps1 -MocStem {stem}` to draft structural edges.
- **orphans** — notes that claim the MOC in `moc:` but sit in no cluster (place
  them).
- **misplaced** — a concept whose typed edges mostly pull into another cluster
  (consider moving it, or the two clusters should merge).

**Structural-debt routing (loop D).** The diagram pipeline already computes rich
quality signals that otherwise die in console output — route them into this
report:
- Read the latest `00_Inbox/DIAGRAM_RENDER_PLAN.json` (written by
  `build_diagrams.ps1`). Surface any cluster where the diagram dropped concepts
  at render (`selected < total`) — these are oversized clusters actively losing
  information.
- Optionally fold in `vault-graph topology` output (orphans, dead wikilinks,
  centrality) as the graph-metric backend — same orphan/dead-link signals,
  computed over the whole wikilink graph. (See
  `99_System/Claude/vault-graph/SKILL.md`.)
Track unresolved items run-over-run so structural debt has somewhere to live
instead of being recomputed and forgotten each week.

**Never auto-fix** — re-clustering is a human judgment call. Report the flagged
MOCs and worst offenders, and point the user at `recluster.ps1` /
`connect_clusters.ps1` for the drafts. These two helpers write review worksheets
to `00_Inbox/` and never edit a MOC themselves.

Output format:
```
## Cluster health
| MOC | Oversized clusters | Singletons | List-only | Orphans | Misplaced | Render-dropped |
| MOC_Threat_Protection | Attack Landscape (20), Copilot Ops (10) | — | 7/7 | — | — | 11 concepts |
| MOC_Enterprise_Architecture | Architecture as Thinking (17), Org Dynamics (13) | — | 6/6 | 1 | 3 | 8 concepts |
```
Lead the Priority actions with the worst oversized clusters — they actively
lose information at render time.

---

## Review 8 — Quarantine surfacing (loop B)

`validate_note()` failures land in `00_Inbox/Quarantine/` and in the index's
`validation_errors[]`, but nothing recurringly surfaces them — a quarantined
note is invisible to every downstream forever. Because a quarantined note is a
*committed artefact that failed*, surfacing it does NOT violate the no-nag
principle (unlike draft).

- Read `validation_errors[]` from `VAULT_INDEX.json` (already computed — one
  read, zero extra scan). Cross-check the file list in `00_Inbox/Quarantine/`.
- Report the count and each stem with its first validation error.

Output format:
```
## Quarantine (loop B)
Quarantined notes: N
| Stem | First validation error |
| Foo_Bar | invalid domain: 'security' — must be one of [...] |
```

---

## Review 9 — AI_Candidates cooling (loop E)

`extract-gems` writes proposed candidates to `00_Inbox/AI_Candidates/` with a
cooling period before the weekly promote/merge/discard decision. This is the ONE
backlog that SHOULD be surfaced — a proposed-but-undecided artefact, distinct
from the intentionally un-nagged draft notes.

- List entries in `00_Inbox/AI_Candidates/` older than **N = 14 days** (by file
  mtime or the candidate's `extracted:` field), so nothing sits indefinitely
  without a decision.

Output format:
```
## AI_Candidates cooling (loop E)
Candidates awaiting weekly review: N (M older than 14 days)
| Candidate | Age (days) | Suggested type |
```

---

## Review 10 — Frontmatter well-formedness (loop F)

`generate_index.py` parses only the **first** `---...---` block in a file. A note
can therefore be structurally broken yet still parse "successfully" into a WRONG
record — and never raise a missing-field error — so the defect is invisible to
every other review (which all trust the index). This is exactly how a whole MOC's
notes were silently mis-indexed: a `concept_role:` mini-block had been prepended
*above* the real frontmatter, so the index read `{concept_role: study}` as the
entire frontmatter and defaulted `title`→stem, `status`→draft, `moc`→[],
`flashcards`→false for ~100 notes. Reviews 1–3 saw "valid" records and flagged
nothing.

Because the index cannot be trusted to surface this class of defect, this review
reads the note **files directly** via a deterministic script:

```
powershell -ExecutionPolicy Bypass -File frontmatter_health.ps1
```

It scans `21_Concepts`, `22_Maps of Content`, `40_Solutions`, `10_Ideas` and
flags, per file:

- **DOUBLE_FM** — more than one frontmatter block at the top (the index reads
  only the first; the real one is stranded in the body). The classic signature is
  a `concept_role:` (or any) mini-block prepended above the real frontmatter.
- **MIDFILE_BOM** — a UTF-8 BOM (U+FEFF) at any offset > 0. A *leading* BOM is
  tolerated; one mid-file means content was prepended in front of the original
  BOM (a botched batch edit) — the reliable fingerprint of DOUBLE_FM.
- **UNCLOSED_FM** — opens with `---` but the block is never closed.
- **NO_FM** — a concept note with no frontmatter at all.

This is a committed-artefact defect (a malformed file that silently corrupts the
index), so it IS surfaced — distinct from the never-nagged draft
backlog. **Never auto-fix in a routine review** — report the offenders and their
flags. A fix re-shapes the frontmatter (merging blocks, stripping the stray BOM),
which is a structural edit; on `status: final` notes it requires explicit user
authorisation (Safety Rule #6), so it is a separate, deliberate action — not part
of the read-only health pass. When fixing, back up the originals to `60_Admin/`
first, transform only files matching an exact malformation signature, then
**re-run `generate_index.py`** so the corrected frontmatter reaches the index.

Run this review **first** in a full health check: if it FAILs, note in the report
that all index-derived sections (Reviews 1–3, 6) may be based on wrong records
until the malformed files are repaired.

Output format:
```
## Frontmatter health (loop F)
Malformed files: N
| Flags | File |
| DOUBLE_FM, MIDFILE_BOM | Global_Region_Resource_Allocation.md |
```

---

## Index management — regenerate VAULT_INDEX.json

Run when the user adds notes outside the agent pipeline or requests a manual index refresh.

```python
# generate_index.py — run from vault root
import os, json
from pathlib import Path

VAULT = Path(__file__).parent
INDEX = VAULT / "00_Inbox" / "VAULT_INDEX.json"

SKIP_DIRS = {
    "00_Inbox", "30_Sources", "40_Solutions", "99_System",
    ".obsidian", ".trash", "Templates", "Assets"
}

notes, mocs = [], []
for root, dirs, files in os.walk(VAULT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
    for fname in files:
        if not fname.endswith(".md"): continue
        title = fname[:-3]
        if fname.startswith("MOC_"): mocs.append(title)
        else: notes.append(title)

with open(INDEX, "w") as f:
    json.dump({"notes": sorted(notes), "mocs": sorted(mocs)}, f, indent=2)

print(f"Index: {len(notes)} notes, {len(mocs)} MOCs")
```

**Run sequence (any cadence):**
```powershell
.\launch-process-inbox.ps1     # regenerates the index automatically, then runs process-inbox
```
Every launcher regenerates `VAULT_INDEX.json` before the agent starts; run
`python generate_index.py` by hand only after editing notes out of band.

---

## Token budget reference

| Operation | Cost |
|---|---|
| Load VAULT_INDEX.json (100-note vault) | ~800 tokens |
| CLAUDE.md instructions | ~1,500 tokens |
| Per note processed | ~1,100 tokens |
| Report output | ~150 tokens |
| **Sustainable batch size** | **40-60 mixed notes/week** |
| Hard context limit (Sonnet) | ~160 notes |

---

## Full health check report format

Run all review sections (1–9) and output:

```
## Vault health check — {date}

### Frontmatter health (run FIRST — Review 10, loop F)
{Review 10 output. If it FAILs, prepend a banner: index-derived sections below
may reflect wrong records until the malformed files are repaired.}

### Summary
Notes total: N | Final: N | Draft: N | Needs review: N
MOCs: N | Orphaned notes: N | Open questions: N
Quarantined: N | Flashcard sync gaps: N | AI_Candidates awaiting review: N
Malformed frontmatter: N   ← if > 0, index-derived sections may be unreliable

### Priority actions (ordered by urgency)
1. {Most urgent item}
2. {Second item}
...

### Actionable notes
{Review 1 table}

### MOC coverage
{Review 2 table}

### Flashcard coverage
{Review 3 tables — incl. Flashcard sync gaps (loop A)}

### Open questions
{Review 4 output}

### MOC candidates
{Review 5 output}

### Cluster health
{Review 7 output — incl. structural-debt routing (loop D)}

### Quarantine
{Review 8 output (loop B)}

### AI_Candidates cooling
{Review 9 output (loop E)}
```

---

## Metadata fields this skill depends on

The following YAML fields must be present on concept notes for this skill to work correctly:

```yaml
type: concept | moc | pattern | idea | solution
status: draft | final
domain: learning | writing | presentations | biology | strategy | multiple | enterprise-architecture | ai-systems | data-engineering | cybersecurity
source_type: book | course | article | notebooklm | shower-thought
created: YYYY-MM-DD
updated: YYYY-MM-DD
moc: [MOC title]
reviewed: true | false
flashcards: true | false
concept_role: study | reference | scaffold   # optional; absent ⇒ study. Gates flashcard/review nagging (Reviews 1 & 3): reference/scaffold notes are never flagged for missing cards.
```

If these fields are missing from older notes, flag them in the report as `METADATA INCOMPLETE` rather than failing silently.

**Note:** missing-field detection relies on the index, which only parses the
first frontmatter block. A note with a *structurally* broken frontmatter (a
second block, a stray mid-file BOM) can parse into a wrong record without any
missing-field error — that class of defect is caught by **Review 10**, which
reads the files directly. Run Review 10 first so this section's signals are
trustworthy.
