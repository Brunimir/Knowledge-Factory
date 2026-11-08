#!/usr/bin/env python3
import sys
# ENV-33: mutate the wrapper in place. Rebinding it dropped the last reference to
# the caller's own wrapper, whose __del__ closed the shared buffer - so any script
# that rebound sys.stdout and then imported this module died on its next print.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""
generate_index.py — PKM Vault Index Generator
Place this file at the root of your Obsidian vault.

PURPOSE
    Pre-generates VAULT_INDEX.json before each Sunday agent run.
    The agent reads this file instead of scanning the vault,
    eliminating the single largest token cost per batch (~20,000
    tokens saved on a 100-note vault).

    The index uses filename STEMS (not titles) as primary keys,
    matching exactly what Obsidian uses to resolve [[wikilinks]].
    This is the single source of truth for wikilink validation.

USAGE
    python3 generate_index.py

RUN SEQUENCE
    1. python3 generate_index.py     # 2 seconds, 0 agent tokens
    2. claude process-inbox          # weekly ingestion
       claude /pkm-solution {brief}  # Phase 5 — index-first shortlist

AFTER EACH RUN
    Re-run this script after adding or removing notes outside
    the agent pipeline. VAULT_INDEX.json is always regenerated
    fresh — never edit it manually.

OUTPUT
    Writes 00_Inbox/VAULT_INDEX.json with type-segregated slim views:

    {
      "generated": "YYYY-MM-DD",
      "notes":               [ {concept record}  ],
      "mocs":                [ {MOC record}      ],
      "patterns":            [ {pattern record}  ],
      "solutions":           [ {solution record} ],
      "decisions":           [ {decision record} ],   # live only
      "decisions_archived":  [ {decision record} ],   # superseded / expired / past-expiry deviating
      "ideas":               [ {idea record}     ],
      "validation_errors":   [ {stem, errors[]}  ]
    }

    Each record exposes only the frontmatter fields the agent needs
    to filter, rank, and validate cross-references for that type.

    Decision live/archived split:
      A decision goes to decisions_archived when ANY of these hold:
        - status == "superseded"
        - status == "expired"
        - decision_type == "deviating" AND parsed(expires) <= today
      Everything else stays in decisions[].

    Concept (notes[]) fields:
      stem, title, type, status, description, domain, source_type,
      moc[], flashcards, source_count, trust, concept_role, created, updated,
      aliases[], tags[]
      (concept_role ∈ study|reference|scaffold — optional; absent ⇒ "study".
       Separates a note's stable purpose from the transient flashcards
       boolean, so reference/scaffold notes are not nagged for missing cards.)
      (`reviewed` RETIRED 2026-08-02 — it never carried information `status`
       did not. Flashcard eligibility is now status:final AND flashcards:false.)
      (source_count/trust are STORED and REQUIRED, maintained by
       concept_schema_sync.ps1; the indexer re-derives trust from the stored
       source_count and flags a stale score. 0/0.0 are legitimate values.)

    Pattern fields:
      stem, title, status, description, domain, problem, problem_type,
      ingredients[], use_count, context[], tags[], created, updated

    Solution fields:
      stem, title, status, description, domain, built_from[],
      constrained_by[], companion[], tags[], created, updated
      (companion[] lists binary deliverable filenames — .pptx/.docx/.xlsx
       that live alongside this .md. Empty = doc Solution; non-empty =
       composite Solution.)

    Decision fields:
      stem, title, status, description, domain, decision_type, date,
      expires, affected_patterns[], affected_solutions[], supersedes[],
      superseded_by[], tags[], created, updated
      (affected_solutions[] — optional Solution stems the decision reshapes,
       the solution-side mirror of affected_patterns[].)

    Idea fields:
      stem, title, status, description, domain, origin[], tags[],
      created, updated
"""

import os
import re
import json
import hashlib
import yaml
from pathlib import Path
from datetime import date

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

from kzn_paths import VAULT_PATH as VAULT, REPO_PATH as REPO   # the ONE home for the roots
from kzn_paths import without_twins   # IMP-69: a cloud-sync twin is not a file
INDEX = VAULT / "00_Inbox" / "VAULT_INDEX.json"

# Content-hash incremental cache (Phase 1c). Sidecar keyed by file path, storing
# a whole-file SHA-256 plus the already-computed parse result, so unchanged
# notes are skipped (no YAML re-parse / re-validate) on the next rebuild. The
# cache is a disposable derived artefact (gitignored): deleting it forces a
# full from-scratch build, which produces byte-identical output. Whole-file
# hashing (not chunked) avoids chunk-boundary churn. CACHE_VERSION is bumped
# whenever the parse/validate/extract logic below changes, which invalidates
# every entry so stale records can never leak into the index.
CACHE = VAULT / "00_Inbox" / ".index_cache.json"
CACHE_VERSION = 5   # bump on any parse/validate/extract change (v5: NON_ARTEFACT_TYPES skip)

# Explicit allowlist — only these directories are scanned (relative to VAULT)
SCAN_DIRS = [
    Path("20_Learning") / "21_Concepts",
    Path("20_Learning") / "22_Maps of Content",
    Path("40_Solutions"),                # Phase 5 artefacts: patterns, solutions, decisions
    Path("10_Ideas"),                    # idea notes (Phase 5 inputs)
    Path("00_Inbox") / "Note Pipe",
]

# Required fields for concept notes — agent quarantines notes missing any of these
REQUIRED_CONCEPT_FIELDS = {
    "title", "icon", "type", "status", "description",
    "domain", "source_type", "moc", "flashcards",
    "source_count", "trust",
    "created", "updated",
}

# Trustworthiness scoring (stored on the note, maintained by concept_schema_sync.ps1).
#   base  = 0.0                if source_count == 0   (no evidence behind the claim)
#         = 2 - 1/source_count otherwise              (1.0, 1.5, 1.67, 1.75 … → 2.0)
#   trust = base + 0.2 if status == "final"
# The curve has diminishing returns and an asymptote at 2.0, so corroboration
# always helps but never dominates; the final bonus caps the scale at 2.2.
TRUST_FINAL_BONUS = 0.2


def compute_trust(source_count: int, status: str) -> float:
    """The single definition of the trust score. The sync script and the
    validator below both read it from here, so the two can never disagree."""
    base = 0.0 if source_count <= 0 else 2 - (1 / source_count)
    if status == "final":
        base += TRUST_FINAL_BONUS
    return round(base, 2)

REQUIRED_MOC_FIELDS = {
    "title", "type", "status", "description", "domain",
    "note_count", "created", "updated",
}

# Phase 5 artefact required-field sets (in 40_Solutions/) and ideas (10_Ideas/).
# Kept slim — these mirror the Phase 5 validation gate. The pkm-solution skill
# enforces stricter pre-write checks (rationale section, suffix-vs-type, etc.).
REQUIRED_BASE_FIELDS     = {"title", "type", "status", "description", "domain", "created", "updated"}
REQUIRED_PATTERN_FIELDS  = REQUIRED_BASE_FIELDS | {"problem", "ingredients", "problem_type", "use_count"}
REQUIRED_SOLUTION_FIELDS = REQUIRED_BASE_FIELDS | {"built_from"}
REQUIRED_DECISION_FIELDS = REQUIRED_BASE_FIELDS | {"decision_type"}
REQUIRED_IDEA_FIELDS     = REQUIRED_BASE_FIELDS

# Controlled vocabularies — agent flags deviations
VALID_DOMAINS           = {"learning", "writing", "presentations", "biology", "strategy", "multiple", "enterprise-architecture", "ai-systems", "data-engineering", "cybersecurity", "economics", "career", "nutrition", "consumer-decisions"}
VALID_STATUSES          = {"draft", "final"}
VALID_TYPES             = {"concept", "moc", "pattern", "idea", "solution", "decision"}

# Documents that live in the vault but are NOT artefacts. They declare what they
# are; the indexer skips them instead of misclassifying them.
#
# Why this exists: dispatch treats an UNRECOGNISED `type:` as a concept and
# validates it against REQUIRED_CONCEPT_FIELDS, so a proposal or a spec with
# honest frontmatter was reported as a malformed concept. The established
# workaround was to carry no frontmatter at all (some spec folders did this), but
# that throws away real metadata. Declaring intent beats hiding from the parser.
NON_ARTEFACT_TYPES      = {"proposal", "documentation", "element-card", "flashcard-batch"}
VALID_SOURCE_TYPES      = {"book", "course", "article", "notebooklm", "shower-thought"}
VALID_DECISION_TYPES    = {"establishing", "changing", "deviating"}
VALID_DECISION_STATUSES = {"proposed", "accepted", "superseded", "expired"}
VALID_PROBLEM_TYPES     = {"learning", "communication", "leadership", "decision-making", "productivity"}
VALID_CONCEPT_ROLES     = {"study", "reference", "scaffold"}   # optional on concepts; absent ⇒ "study"


# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, list[str]]:
    """Parse YAML frontmatter. Returns (fields, errors).
    Tolerates a leading UTF-8 BOM (U+FEFF) — Windows editors sometimes
    prepend one and it defeats the literal `---` startswith check.
    Returns (None, []) for files that have no frontmatter at all — these
    are legacy/freeform files; the caller skips them silently rather than
    treating them as errors."""
    if content.startswith("﻿"):
        content = content[1:]
    if not content.startswith("---"):
        return None, []
    try:
        end = content.index("---", 3)
    except ValueError:
        return {}, ["frontmatter block never closed (missing closing ---)"]
    fm_text = content[3:end]
    try:
        fields = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        return {}, [f"YAML parse error: {str(e)[:120]}"]
    return fields, []


def str_field(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    return str(v).strip().strip("'\"")


def list_field(fields: dict, name: str) -> list[str]:
    """Coerce a frontmatter field to list[str] regardless of YAML shape."""
    raw = fields.get(name)
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    return [str(raw).strip()]


def parse_date(val) -> "date | None":
    """Parse a YYYY-MM-DD value to date; None on failure or empty."""
    if val is None or val == "":
        return None
    try:
        return date.fromisoformat(str(val).strip())
    except (ValueError, TypeError):
        return None


def _required_missing(fields: dict, required: set) -> list[str]:
    """Return ['missing field: X', ...] for every required field that is
    absent, None, or the empty string. Empty lists pass — list-non-empty
    rules live in per-type validators."""
    errors = []
    for f in sorted(required):   # sorted(): `required` is a set; deterministic order
        v = fields.get(f)
        if f not in fields or v is None or v == "":
            errors.append(f"missing field: {f}")
    return errors


# ── VALIDATORS ────────────────────────────────────────────────────────────────

def validate_concept(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_CONCEPT_FIELDS)

    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}' — must be one of {sorted(VALID_DOMAINS)}")
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: '{fields['status']}' — must be one of {sorted(VALID_STATUSES)}")
    if fields.get("source_type") and fields["source_type"] not in VALID_SOURCE_TYPES:
        errors.append(f"invalid source_type: '{fields['source_type']}' — must be one of {sorted(VALID_SOURCE_TYPES)}")

    moc = fields.get("moc")
    if moc is not None and not isinstance(moc, list):
        errors.append(f"moc must be a YAML list — got: {type(moc).__name__}")

    # title must derive to stem under the safe_stem rule (see CLAUDE.md)
    title = str(fields.get("title", ""))
    expected = title.strip().strip("'\"")
    expected = re.sub(r"'s\b", "", expected)
    expected = expected.replace("'", "")
    expected = expected.replace(" ", "_")
    for ch in ['"', '[', ']', '&', ',', '/', '\\', ':', '*', '?', '<', '>', '|', '.']:
        expected = expected.replace(ch, "")
    expected = re.sub(r"_+", "_", expected).strip("_")
    if expected and expected != stem:
        errors.append(f"title/filename mismatch: title '{title}' → expected stem '{expected}', actual stem '{stem}'")

    aliases = fields.get("aliases", [])
    if not isinstance(aliases, list) or len(aliases) < 2:
        errors.append(f"aliases must be a list with ≥ 2 entries — got: {aliases}")

    val = fields.get("flashcards")
    if val is not None and not isinstance(val, bool):
        errors.append(f"flashcards must be true or false — got: {repr(val)}")

    # `reviewed` was retired 2026-08-02: it carried no information `status` did
    # not already carry (reviewed:true never occurred without status:final).
    # Flashcard eligibility is now status:final AND flashcards:false.
    if "reviewed" in fields:
        errors.append("`reviewed` is retired — remove it (run concept_schema_sync.ps1 -Apply)")

    # source_count / trust are STORED and maintained by concept_schema_sync.ps1.
    # The indexer never recomputes source_count (that needs the note body, which
    # it does not read) but it DOES re-derive trust from the stored count, so a
    # stale or hand-edited score cannot pass unnoticed.
    # REQUIRED as of 2026-08-02: the migration is complete (all 811 concepts
    # carry both), so an unsynced note is now a hard failure rather than a
    # tolerated in-progress state. Absence is caught by REQUIRED_CONCEPT_FIELDS
    # above; the checks below police the VALUES.
    sc = fields.get("source_count")
    if sc is not None:
        if not isinstance(sc, int) or isinstance(sc, bool) or sc < 0:
            errors.append(f"source_count must be a non-negative integer — got: {repr(sc)}")
        else:
            tr = fields.get("trust")
            expected = compute_trust(sc, str(fields.get("status", "")).strip())
            if tr is not None:
                if not isinstance(tr, (int, float)) or isinstance(tr, bool):
                    errors.append(f"trust must be a number — got: {repr(tr)}")
                elif round(float(tr), 2) != expected:
                    errors.append(
                        f"trust is stale: {tr} stored but {expected} computed "
                        f"({sc} source(s), status:{fields.get('status')}) — run concept_schema_sync.ps1 -Apply"
                    )

    # concept_role is OPTIONAL (absent ⇒ "study"); only its VALUE is policed, so
    # no existing concept needs migrating. Distinguishes study/reference/scaffold
    # intent from the transient flashcards boolean.
    cr = fields.get("concept_role")
    if cr is not None and cr != "" and cr not in VALID_CONCEPT_ROLES:
        errors.append(f"invalid concept_role: '{cr}' — must be one of {sorted(VALID_CONCEPT_ROLES)}")

    return errors


def validate_moc(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_MOC_FIELDS)
    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}'")
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: '{fields['status']}'")
    return errors


def validate_pattern(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_PATTERN_FIELDS)
    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}'")
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: '{fields['status']}'")
    if not stem.endswith(" - Pattern"):
        errors.append("filename must end in ' - Pattern.md' for type:pattern")

    ingredients = fields.get("ingredients")
    if ingredients is not None and not isinstance(ingredients, list):
        errors.append("ingredients must be a YAML list")
    elif isinstance(ingredients, list) and len(ingredients) == 0:
        errors.append("ingredients must be non-empty")

    pt = fields.get("problem_type")
    if pt and pt not in VALID_PROBLEM_TYPES:
        errors.append(f"invalid problem_type: '{pt}' — must be one of {sorted(VALID_PROBLEM_TYPES)}")

    uc = fields.get("use_count")
    if uc is not None and not isinstance(uc, int):
        errors.append(f"use_count must be an integer — got: {repr(uc)}")

    return errors


def validate_solution(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_SOLUTION_FIELDS)
    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}'")
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: '{fields['status']}'")
    if not stem.endswith(" - Solution"):
        errors.append("filename must end in ' - Solution.md' for type:solution")

    bf = fields.get("built_from")
    if bf is not None and not isinstance(bf, list):
        errors.append("built_from must be a YAML list")
    elif isinstance(bf, list) and len(bf) == 0:
        errors.append("built_from must be non-empty")

    return errors


def validate_decision(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_DECISION_FIELDS)
    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}'")

    status = fields.get("status")
    if status and status not in VALID_DECISION_STATUSES:
        errors.append(f"invalid decision status: '{status}' — must be one of {sorted(VALID_DECISION_STATUSES)}")

    dt = fields.get("decision_type")
    if dt and dt not in VALID_DECISION_TYPES:
        errors.append(f"invalid decision_type: '{dt}' — must be one of {sorted(VALID_DECISION_TYPES)}")

    if dt == "deviating" and parse_date(fields.get("expires")) is None:
        errors.append("deviating decision must have expires: YYYY-MM-DD")

    if not stem.endswith(" - Decision"):
        errors.append("filename must end in ' - Decision.md' for type:decision")

    return errors


def validate_idea(stem: str, fields: dict) -> list[str]:
    errors = _required_missing(fields, REQUIRED_IDEA_FIELDS)
    if fields.get("domain") and fields["domain"] not in VALID_DOMAINS:
        errors.append(f"invalid domain: '{fields['domain']}'")
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"invalid status: '{fields['status']}'")
    return errors


# ── EXTRACTORS ────────────────────────────────────────────────────────────────

def extract_note_record(stem: str, fields: dict) -> dict:
    """Build the index record for a concept note."""
    return {
        "stem":        stem,
        "title":       str_field(fields, "title", stem),
        "type":        str_field(fields, "type", "concept"),
        "status":      str_field(fields, "status", "draft"),
        "description": str_field(fields, "description"),
        "domain":      str_field(fields, "domain"),
        "source_type": str_field(fields, "source_type"),
        "moc":         list_field(fields, "moc"),
        "flashcards":  bool(fields.get("flashcards", False)),
        "source_count": int(fields.get("source_count") or 0),
        "trust":       float(fields.get("trust") or 0.0),
        "concept_role": str_field(fields, "concept_role", "study"),  # study | reference | scaffold
        "created":     str_field(fields, "created"),
        "updated":     str_field(fields, "updated"),
        "aliases":     list_field(fields, "aliases"),
        "tags":        list_field(fields, "tags"),
    }


def extract_moc_record(stem: str, fields: dict) -> dict:
    return {
        "stem":        stem,
        "title":       str_field(fields, "title", stem),
        "domain":      str_field(fields, "domain"),
        "note_count":  int(fields.get("note_count", 0) or 0),
        "status":      str_field(fields, "status", "draft"),
        "description": str_field(fields, "description"),
        "created":     str_field(fields, "created"),
        "updated":     str_field(fields, "updated"),
    }


def extract_pattern_record(stem: str, fields: dict) -> dict:
    return {
        "stem":         stem,
        "title":        str_field(fields, "title", stem),
        "status":       str_field(fields, "status", "draft"),
        "description":  str_field(fields, "description"),
        "domain":       str_field(fields, "domain"),
        "problem":      str_field(fields, "problem"),
        "problem_type": str_field(fields, "problem_type"),
        "ingredients":  list_field(fields, "ingredients"),
        "use_count":    int(fields.get("use_count", 0) or 0),
        "context":      list_field(fields, "context"),
        "tags":         list_field(fields, "tags"),
        "created":      str_field(fields, "created"),
        "updated":      str_field(fields, "updated"),
    }


def extract_solution_record(stem: str, fields: dict) -> dict:
    return {
        "stem":           stem,
        "title":          str_field(fields, "title", stem),
        "status":         str_field(fields, "status", "draft"),
        "description":    str_field(fields, "description"),
        "domain":         str_field(fields, "domain"),
        "built_from":     list_field(fields, "built_from"),
        "constrained_by": list_field(fields, "constrained_by"),
        "companion":      list_field(fields, "companion"),
        "tags":           list_field(fields, "tags"),
        "created":        str_field(fields, "created"),
        "updated":        str_field(fields, "updated"),
    }


def extract_decision_record(stem: str, fields: dict) -> dict:
    return {
        "stem":              stem,
        "title":             str_field(fields, "title", stem),
        "status":            str_field(fields, "status", "proposed"),
        "description":       str_field(fields, "description"),
        "domain":            str_field(fields, "domain"),
        "decision_type":     str_field(fields, "decision_type"),
        "date":              str_field(fields, "date"),
        "expires":           str_field(fields, "expires"),
        "affected_patterns": list_field(fields, "affected_patterns"),
        "affected_solutions": list_field(fields, "affected_solutions"),
        "supersedes":        list_field(fields, "supersedes"),
        "superseded_by":     list_field(fields, "superseded_by"),
        "tags":              list_field(fields, "tags"),
        "created":           str_field(fields, "created"),
        "updated":           str_field(fields, "updated"),
    }


def extract_idea_record(stem: str, fields: dict) -> dict:
    return {
        "stem":        stem,
        "title":       str_field(fields, "title", stem),
        "status":      str_field(fields, "status", "draft"),
        "description": str_field(fields, "description"),
        "domain":      str_field(fields, "domain"),
        "origin":      list_field(fields, "origin"),
        "tags":        list_field(fields, "tags"),
        "created":     str_field(fields, "created"),
        "updated":     str_field(fields, "updated"),
    }


def is_decision_archived(rec: dict, today: date) -> bool:
    if rec["status"] in ("superseded", "expired"):
        return True
    if rec["decision_type"] == "deviating":
        exp = parse_date(rec.get("expires"))
        if exp is not None and exp <= today:
            return True
    return False


# ── SCAN ──────────────────────────────────────────────────────────────────────

# kind -> bucket name, for routing parsed results into the index buckets.
_KIND_BUCKET = {
    "concept": "concepts", "moc": "mocs", "pattern": "patterns",
    "solution": "solutions", "decision": "decisions", "idea": "ideas",
}


def classify_and_extract(stem: str, content: str) -> dict:
    """Pure function: filename stem + raw file content -> a parse RESULT.
    Result shape (JSON-serialisable, so it can be cached verbatim):
        {"kind": concept|moc|pattern|solution|decision|idea
                 |skip_no_fm|parse_error,
         "stem": stem, "record": <bucket record> | None, "errors": [str, ...]}
    This is exactly the per-file logic the non-incremental scan ran inline;
    routing it via route() reproduces the previous bucketing byte-for-byte."""
    fields, parse_errors = parse_frontmatter(content)
    if fields is None and not parse_errors:
        return {"kind": "skip_no_fm", "stem": stem, "record": None, "errors": []}
    if parse_errors:
        return {"kind": "parse_error", "stem": stem, "record": None, "errors": parse_errors}

    note_type = str(fields.get("type", "")).strip()

    # Declared non-artefact: skip like a frontmatter-less file, but without
    # forcing the document to strip its own metadata to stay invisible.
    if note_type in NON_ARTEFACT_TYPES:
        return {"kind": "skip_non_artefact", "stem": stem, "record": None, "errors": []}

    # MOC detection — by filename prefix OR by explicit type (fname == stem+'.md')
    if stem.startswith("MOC_") or note_type == "moc":
        return {"kind": "moc", "stem": stem,
                "record": extract_moc_record(stem, fields), "errors": validate_moc(stem, fields)}
    if note_type == "pattern":
        return {"kind": "pattern", "stem": stem,
                "record": extract_pattern_record(stem, fields), "errors": validate_pattern(stem, fields)}
    if note_type == "solution":
        return {"kind": "solution", "stem": stem,
                "record": extract_solution_record(stem, fields), "errors": validate_solution(stem, fields)}
    if note_type == "decision":
        return {"kind": "decision", "stem": stem,
                "record": extract_decision_record(stem, fields), "errors": validate_decision(stem, fields)}
    if note_type == "idea":
        return {"kind": "idea", "stem": stem,
                "record": extract_idea_record(stem, fields), "errors": validate_idea(stem, fields)}
    # Default: treat as concept (matches prior behaviour)
    return {"kind": "concept", "stem": stem,
            "record": extract_note_record(stem, fields), "errors": validate_concept(stem, fields)}


def route(result: dict, buckets: dict, skipped_no_frontmatter: list) -> None:
    """Apply a parse RESULT into the buckets — identically for fresh and cached
    results. A typed note with validation errors lands in BOTH its type bucket
    and validation_errors, exactly as the original inline scan did."""
    kind = result["kind"]
    stem = result["stem"]
    if kind == "skip_no_fm" or kind == "skip_non_artefact":
        skipped_no_frontmatter.append(stem)
        return
    if kind == "parse_error":
        buckets["validation_errors"].append({"stem": stem, "errors": result["errors"]})
        return
    if result["errors"]:
        buckets["validation_errors"].append({"stem": stem, "errors": result["errors"]})
    buckets[_KIND_BUCKET[kind]].append(result["record"])


def load_cache() -> dict:
    """Load the incremental cache, or an empty one on any problem (missing,
    corrupt, or a CACHE_VERSION bump). An unusable cache means a full rebuild —
    never an error, and never a stale record (version-gated)."""
    try:
        with open(CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CACHE_VERSION:
            return {}
        return data.get("files", {}) or {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_cache(files: dict) -> None:
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump({"version": CACHE_VERSION, "files": files}, f, ensure_ascii=False)
    except OSError as e:
        print(f"  [WARN] could not write index cache: {e}")


def scan_vault(vault: Path, scan_dirs: list) -> dict:
    """Walk scan_dirs and bucket every .md by frontmatter type, reusing cached
    parse results for files whose whole-file SHA-256 is unchanged (Phase 1c).
    Returns the same buckets shape as before, plus an "_incremental" stats
    sub-dict carrying the new cache. First-seen stem wins; the JSON output is
    identical to a from-scratch build (empty cache)."""
    buckets = {
        "concepts": [], "mocs": [], "patterns": [],
        "solutions": [], "decisions": [], "ideas": [],
        "validation_errors": [],
    }
    seen_stems = set()
    skipped_no_frontmatter = []  # legacy/freeform files; printed for visibility, not flagged

    old_files = load_cache()
    new_files = {}
    reused = reprocessed = 0

    for rel_dir in scan_dirs:
        target = vault / rel_dir
        if not target.exists():
            print(f"  [WARN] Directory not found, skipping: {target}")
            continue

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for fname in without_twins(files):
                if not fname.endswith(".md"):
                    continue
                stem = fname[:-3]

                if stem in seen_stems:
                    print(f"  [SKIP duplicate] {stem} (already indexed from another folder)")
                    continue
                seen_stems.add(stem)

                fpath = Path(root) / fname
                try:
                    rel = fpath.relative_to(vault).as_posix()
                except ValueError:
                    # a REPO-rooted scan dir; namespace the cache key so it can
                    # never collide with a vault-relative one
                    rel = "repo:" + fpath.relative_to(REPO).as_posix()

                raw = fpath.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()

                cached = old_files.get(rel)
                if cached is not None and cached.get("hash") == digest:
                    result = cached["result"]   # unchanged note: skip parse + validate
                    reused += 1
                else:
                    result = classify_and_extract(stem, raw.decode("utf-8", errors="replace"))
                    reprocessed += 1

                new_files[rel] = {"hash": digest, "result": result}
                route(result, buckets, skipped_no_frontmatter)

    for key, items in buckets.items():
        if key == "validation_errors":
            items.sort(key=lambda e: e["stem"])
        else:
            items.sort(key=lambda r: r["stem"])
    buckets["_skipped_no_frontmatter"] = sorted(skipped_no_frontmatter)
    buckets["_incremental"] = {
        "reused": reused,
        "reprocessed": reprocessed,
        "removed": len(set(old_files) - set(new_files)),
        "new_files": new_files,
    }
    return buckets


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not VAULT.exists():
        print(f"ERROR: Vault path does not exist: {VAULT}")
        return

    inbox = VAULT / "00_Inbox"
    if not inbox.exists():
        print(f"ERROR: 00_Inbox not found at: {inbox}")
        return

    print(f"Scanning vault: {VAULT}")
    print(f"  Dirs: {[str(d) for d in SCAN_DIRS]}")
    b = scan_vault(VAULT, SCAN_DIRS)

    today = date.today()
    decisions_live     = [d for d in b["decisions"] if not is_decision_archived(d, today)]
    decisions_archived = [d for d in b["decisions"] if     is_decision_archived(d, today)]

    index = {
        "generated":          str(today),
        "notes":              b["concepts"],
        "mocs":               b["mocs"],
        "patterns":           b["patterns"],
        "solutions":          b["solutions"],
        "decisions":          decisions_live,
        "decisions_archived": decisions_archived,
        "ideas":              b["ideas"],
        "validation_errors":  b["validation_errors"],
    }

    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    # Persist the content-hash cache for the next incremental run (Phase 1c).
    inc = b.get("_incremental", {})
    save_cache(inc.get("new_files", {}))

    print(f"[OK] Index written to: {INDEX}")
    print(f"  Incremental          : {inc.get('reused', 0)} reused (skipped), "
          f"{inc.get('reprocessed', 0)} reprocessed, {inc.get('removed', 0)} removed")
    print(f"  Concept notes        : {len(b['concepts'])}")
    print(f"  MOC files            : {len(b['mocs'])}")
    print(f"  Patterns             : {len(b['patterns'])}")
    print(f"  Solutions            : {len(b['solutions'])}")
    print(f"  Decisions (live)     : {len(decisions_live)}")
    print(f"  Decisions (archived) : {len(decisions_archived)}")
    print(f"  Ideas                : {len(b['ideas'])}")
    print(f"  Validation errors    : {len(b['validation_errors'])}")
    print(f"  Skipped (no frontmatter, legacy/freeform): {len(b['_skipped_no_frontmatter'])}")

    if b["validation_errors"]:
        print()
        print("  -- Notes with errors (agent will quarantine these) --")
        for e in b["validation_errors"][:10]:
            print(f"    {e['stem']}")
            for err in e["errors"]:
                print(f"      -> {err}")
        if len(b["validation_errors"]) > 10:
            print(f"    ... and {len(b['validation_errors']) - 10} more - see VAULT_INDEX.json")

    print()
    print("Next step: claude process-inbox  (ingestion)  |  claude /pkm-solution {brief}  (Phase 5)")


if __name__ == "__main__":
    main()

