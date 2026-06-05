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

The vault has NO review SLA. `draft` and `needs-review` are valid, permanent
resting states with no time limit. A concept may stay `draft` forever — it
might be a reference note never meant to be studied, or content not yet chosen
for promotion. Volume is expected to be high (gem-extraction feeds the vault
faster than any human can attentively review), and the human is deliberately
NOT the throughput bottleneck. Unreviewed notes are therefore NEVER flagged as
"stale" or "needing attention" on age.

Surface ONLY genuinely actionable notes:
- `flashcards: false` AND `status: final` → approved and awaiting flashcards
  (run `generate-flashcards`). Not raised for notes the human has opted out of
  studying via `flashcards: true` (see Review 3).

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

For each finalised concept note (`status: final`):
- Check `flashcards` field
- If `flashcards: false`, flag it (approved, cards still to be generated)

`flashcards: true` on a final note is terminal and is NEVER flagged: it means
either the cards were generated OR the human deliberately opted the note out of
studying ("reviewed, no need to study"). Do not expect a flashcard file to
exist for such a note, and never treat its absence as a gap.

Also check `20_Learning/23_FlashCards/` for consolidated files:
- List which MOC decks exist
- Flag any MOC that has `status: final` + `flashcards: false` notes but no
  flashcard file (a real coverage gap — opted-out `flashcards: true` notes do
  not count)

Output format:
```
## Flashcard coverage
| MOC | Final notes | Flashcard file exists | Notes without cards |
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

- Reads concept files only. Never writes to `21_Concepts/`.
- Code-fence and inline-backtick stripping prevents false positives on identifiers like `SELECT`, `HTTP/2`, `JSON`.
- Self-reference is excluded (a note titled "RBAC" using `RBAC` in its own body is not a gap).
- If `99_System/acronym_allowlist.md` is missing or malformed, log a warning and proceed with an empty allowlist (Review 6 still runs but flags more aggressively).
- If `VAULT_INDEX.json` is stale (`generated` ≠ today), STOP — the false-positive rate on freshly-added vault concepts would be too high.

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

**Sunday run sequence:**
```bash
python3 generate_index.py      # 2 seconds, 0 agent tokens
claude process-inbox           # agent reads index, never scans
```

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

Run all 5 review sections and output:

```
## Vault health check — {date}

### Summary
Notes total: N | Final: N | Draft: N | Needs review: N
MOCs: N | Orphaned notes: N | Open questions: N

### Priority actions (ordered by urgency)
1. {Most urgent item}
2. {Second item}
...

### Actionable notes
{Review 1 table}

### MOC coverage
{Review 2 table}

### Flashcard coverage
{Review 3 table}

### Open questions
{Review 4 output}

### MOC candidates
{Review 5 output}
```

---

## Metadata fields this skill depends on

The following YAML fields must be present on concept notes for this skill to work correctly:

```yaml
type: concept | moc | pattern | idea | solution
status: draft | needs-review | final
domain: learning | writing | presentations | biology | strategy | multiple | enterprise-architecture
source_type: book | course | article | notebooklm | shower-thought
created: YYYY-MM-DD
updated: YYYY-MM-DD
moc: [MOC title]
reviewed: true | false
review_date: YYYY-MM-DD
flashcards: true | false
```

If these fields are missing from older notes, flag them in the report as `METADATA INCOMPLETE` rather than failing silently.
