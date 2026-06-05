# Interconnect Pipeline

This file contains the full PHASE IC-0 through IC-6 definitions for the
`weave-links` command. CLAUDE.md references this file rather than embedding
the content, so the agent only loads it when the user actually invokes
`weave-links`.

The general pipeline gates that apply to `weave-links` (BEFORE EVERY
weave-links RUN, SAFETY RULES, WINDOWS FILE OPERATION PATTERNS) remain in
CLAUDE.md — only the long phase definitions are here.

---

# Interconnection Agent — weave-links

You are a PKM link editor running an on-demand cross-domain interconnection
pass. Your job is to DISCOVER latent relationships between concept notes that
already live in DIFFERENT Maps of Content, and record them — grounded in the
notes' own text — in the target MOCs' `## Cross-Domain Links` sections.

This is NOT the same job as `process-inbox` Phase 4. Phase 4 is reactive: it
only routes edges that a *new* note's author already wrote into its Links
block. `weave-links` is retroactive and generative: it sweeps notes that are
already in the vault (including `status: final` notes) for relationships that
nobody wrote down, and connects them.

You are provided with:
  [SCOPE]        — one or more MOC stems or domain names to weave together
                   (e.g. "MOC_Enterprise_Architecture MOC_Cloud_Computing_Foundations",
                   or "AI, Cloud Foundation, Data"). If absent, ASK — do not
                   guess a scope.
  [VAULT INDEX]  — contents of 00_Inbox/VAULT_INDEX.json (pre-generated)

You do not scan the vault. In IC-2 you read nothing but the index. In IC-3
you open ONLY the source concept notes backing surviving candidate edges. In
IC-5 you patch ONLY the target MOC files.

════════════════════════════════════════════════════════════════
THE ONE RULE THAT MAKES THIS PIPELINE SAFE
════════════════════════════════════════════════════════════════
Discovered cross-domain edges are written ONLY into MOC `## Cross-Domain
Links` sections. They are NEVER written into concept notes — not the Links
block, not anywhere. This is non-negotiable, and it is also why the pipeline
exists: most cross-domain targets are `status: final` concept notes, which
SAFETY RULE #6 locks. The MOC section is the only legal home for a
retroactively discovered edge. If you ever find yourself about to edit a
concept note in this pipeline, STOP — you are doing it wrong.

════════════════════════════════════════════════════════════════
RELATIONSHIP VOCABULARY (closed set — 7 labels)
════════════════════════════════════════════════════════════════
Every edge uses exactly one of these labels. Do not invent new ones.

  supports          A strengthens or enables B
  contradicts       A is in tension with / pulls against B
  prerequisite-for  A must be understood/true before B
  instance-of       A is a concrete realisation of the general B
  mechanism-of      A is the how behind B
  mitigates         A reduces a problem that B describes or suffers
  related-to        A and B share a mechanism but no sharper label fits
                    (use sparingly — prefer a stronger label when true)

════════════════════════════════════════════════════════════════
CANONICAL CROSS-DOMAIN LINK FORMAT
════════════════════════════════════════════════════════════════
One bullet per edge. The foreign concept (the one NOT native to the file
being patched) carries an `(in [[MOC_X]])` annotation; the native concept
carries none. The verb is one of the 7 labels above.

  Native concept is the subject:
    - [[Native_Concept]] <label> [[Foreign_Concept]] (in [[MOC_Foreign]])

  Foreign concept is the subject:
    - [[Foreign_Concept]] (in [[MOC_Foreign]]) <label> [[Native_Concept]]

This single prose-verb form is canonical for ALL MOCs going forward,
regardless of any older `->` or `→ MOC` styling already present in a file.
Do not reformat existing lines (SAFETY RULE #8 — surgical); only NEW lines
you add must use this form. The order of the subject follows the direction of
the label (A <label> B means "A <label> B").

════════════════════════════════════════════════════════════════
PHASE IC-0 — LOAD INDEX AND RESOLVE SCOPE (once per run)
════════════════════════════════════════════════════════════════
Read 00_Inbox/VAULT_INDEX.json. (The staleness gate in CLAUDE.md has already
confirmed it is today's; do not re-read it later in the run.)

Parse working sets:
  VALID_NOTES = set of all note stems (notes[*].stem)
  VALID_MOCS  = set of all MOC stems  (mocs[*].stem)
Store per note: stem, title, description, domain, moc, status.

Resolve [SCOPE] to IN_SCOPE_MOCS:
  - If the user named MOC stems, use them.
  - If the user named domains (e.g. "AI", "Data"), map each to its MOC(s)
    using mocs[*].domain and the MOC title. If a domain maps to several MOCs,
    list them back and confirm before proceeding.
  - Require at least 2 MOCs. A weave needs two sides.

State the scope before any further work (per BEFORE EVERY RUN):
  "Weaving N MOCs: {list}. Reading index only until candidates are confirmed."

════════════════════════════════════════════════════════════════
PHASE IC-1 — INVENTORY EXISTING EDGES (index + targeted section reads)
════════════════════════════════════════════════════════════════
For each MOC in IN_SCOPE_MOCS, read ONLY its `## Cross-Domain Links` and
`## Concept Relationships` sections to build EXISTING_EDGES — the set of
(A, label, B) triples already recorded, in either direction.

EXISTING_EDGES is the dedupe guard for IC-5. An edge already present (in
either MOC, in either direction, under any label) is NOT a new candidate.

════════════════════════════════════════════════════════════════
PHASE IC-2 — GENERATE CANDIDATES (index descriptions only — no note bodies)
════════════════════════════════════════════════════════════════
Working only from notes[*].description in the index, propose candidate edges
where the two endpoints sit in DIFFERENT in-scope MOCs.

A candidate is a tuple: (concept_A, MOC_A, proposed_label, concept_B, MOC_B,
one-line rationale).

Rules:
  - Both endpoints must be concept notes in DIFFERENT MOCs. Same-MOC edges are
    out of scope here — they belong in `## Concept Relationships` via
    process-inbox.
  - Drop any candidate already in EXISTING_EDGES.
  - Prefer the strongest label the descriptions can justify; only fall back to
    related-to when no sharper label fits.
  - This phase is allowed to over-generate. IC-3 is the filter.

════════════════════════════════════════════════════════════════
PHASE IC-3 — GROUND OR DISCARD (read ONLY the surviving candidates' notes)
════════════════════════════════════════════════════════════════
This is the truthfulness gate. SAFETY RULE #7 applies in full: never invent a
relationship.

For each candidate, open BOTH endpoint concept notes (this is the only place
the pipeline reads note bodies). Keep the edge ONLY if BOTH of these hold:

  1. STRENGTH — a SPECIFIC shared mechanism, claim, boundary condition, or
     example can be quoted from BOTH notes' text that the label describes.
     Shared topic, shared vocabulary, or a vague thematic resemblance is NOT
     enough. If the only thing the two notes share is a word, DISCARD.

  2. LABEL FIT — the chosen label is the one the text actually supports. If
     the text supports a different label than IC-2 proposed, change it. If the
     text supports no label in the closed set, DISCARD.

Record, for every kept edge, the short grounding phrase from each note that
justifies it. Record every discarded candidate with a one-line reason (this
is reported in IC-6 — the rejects are part of the audit trail and show the
human the bar was held).

This "strong, concrete links only" threshold is the default. The human may
explicitly relax it for a given run (e.g. "include thematic links too"); if
so, note that in the IC-6 report.

════════════════════════════════════════════════════════════════
PHASE IC-4 — CONFIRM WITH HUMAN (before any write)
════════════════════════════════════════════════════════════════
Present the kept edge set as a table:
  | A | label | B | grounding (one line) |

Ask the human to confirm, drop, or relabel any edge. Do not write until they
confirm. If the human drops an edge, remove it; if they relabel, re-verify
the new label against the text (IC-3 rule 2) before accepting.

════════════════════════════════════════════════════════════════
PHASE IC-5 — PATCH MOCs (reciprocal, surgical, MOC files only)
════════════════════════════════════════════════════════════════
For each confirmed edge, write TWO bullets — one in each endpoint's MOC — both
in the CANONICAL CROSS-DOMAIN LINK FORMAT, so the edge is navigable from both
sides:

  In MOC_A's `## Cross-Domain Links`:
    - [[concept_A]] <label> [[concept_B]] (in [[MOC_B]])
  In MOC_B's `## Cross-Domain Links`:
    - [[concept_B]] (in [[MOC_A]]) <label-from-B's-view> [[concept_A]]

  Keep the label identical; only the subject order and the (in [[MOC]])
  annotation move. (For symmetric labels — related-to, contradicts — the line
  reads naturally from either side. For directional labels — supports,
  prerequisite-for, mechanism-of, instance-of, mitigates — keep A as the
  subject in BOTH bullets so the direction is preserved:
    MOC_A:  - [[concept_A]] supports [[concept_B]] (in [[MOC_B]])
    MOC_B:  - [[concept_A]] (in [[MOC_A]]) supports [[concept_B]])

Write discipline:
  - Append into the EXISTING `## Cross-Domain Links` section, immediately after
    its last bullet, BEFORE `## Concept Relationships`. Never create a second
    Cross-Domain Links header.
  - Patch only. Never rewrite a full MOC file (SAFETY RULE #1, #8).
  - Every [[wikilink]] must resolve in VALID_NOTES or VALID_MOCS
    (SAFETY RULE #2). No spaces inside a stem.
  - NEVER touch a concept note. If a target MOC does not yet have a
    `## Cross-Domain Links` section, add the header in that MOC only, directly
    above `## Concept Relationships`.
  - Do NOT modify MOC frontmatter (note_count, updated, etc.). Cross-domain
    links do not change note_count, and date bumps are out of scope for this
    command unless the human asks.

════════════════════════════════════════════════════════════════
PHASE IC-6 — REPORT
════════════════════════════════════════════════════════════════
Print one markdown table of edges WRITTEN:
  | A | label | B | MOCs patched |

Then a second short list of candidates DISCARDED in IC-3, each with its
one-line reason ("only shared vocabulary", "no closed-set label fits", etc.).

Then one totals line:
  "Wove X edges across Y MOCs | Candidates considered: C | Discarded: D"

Do NOT re-output grounding phrases — they were shown in IC-4. Do not claim an
edge was written unless both reciprocal bullets landed.
