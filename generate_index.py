#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
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
      moc[], reviewed, flashcards, created, updated, aliases[], tags[]

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
      expires, affected_patterns[], supersedes[], superseded_by[],
      tags[], created, updated

    Idea fields:
      stem, title, status, description, domain, origin[], tags[],
      created, updated
"""

import os
import re
import json
import yaml
from pathlib import Path
from datetime import date

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

VAULT = Path(__file__).parent
INDEX = VAULT / "00_Inbox" / "VAULT_INDEX.json"

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
    "domain", "source_type", "moc", "reviewed", "flashcards",
    "created", "updated",
}

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
VALID_DOMAINS           = {"learning", "writing", "presentations", "biology", "strategy", "multiple", "enterprise-architecture", "ai-systems", "data-engineering"}
VALID_STATUSES          = {"draft", "needs-review", "final"}
VALID_TYPES             = {"concept", "moc", "pattern", "idea", "solution", "decision"}
VALID_SOURCE_TYPES      = {"book", "course", "article", "notebooklm", "shower-thought"}
VALID_DECISION_TYPES    = {"establishing", "changing", "deviating"}
VALID_DECISION_STATUSES = {"proposed", "accepted", "superseded", "expired"}
VALID_PROBLEM_TYPES     = {"learning", "communication", "leadership", "decision-making", "productivity"}


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
    for f in required:
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

    for bf in ("reviewed", "flashcards"):
        val = fields.get(bf)
        if val is not None and not isinstance(val, bool):
            errors.append(f"{bf} must be true or false — got: {repr(val)}")

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
        "reviewed":    bool(fields.get("reviewed", False)),
        "flashcards":  bool(fields.get("flashcards", False)),
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

def scan_vault(vault: Path, scan_dirs: list) -> dict:
    """Walk scan_dirs and bucket every .md by frontmatter type.
    Returns: {"concepts": [...], "mocs": [...], "patterns": [...],
              "solutions": [...], "decisions": [...], "ideas": [...],
              "validation_errors": [...]}. First-seen stem wins."""
    buckets = {
        "concepts": [], "mocs": [], "patterns": [],
        "solutions": [], "decisions": [], "ideas": [],
        "validation_errors": [],
    }
    seen_stems = set()
    skipped_no_frontmatter = []  # legacy/freeform files; printed for visibility, not flagged

    for rel_dir in scan_dirs:
        target = vault / rel_dir
        if not target.exists():
            print(f"  [WARN] Directory not found, skipping: {target}")
            continue

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for fname in files:
                if not fname.endswith(".md"):
                    continue
                stem = fname[:-3]

                if stem in seen_stems:
                    print(f"  [SKIP duplicate] {stem} (already indexed from another folder)")
                    continue
                seen_stems.add(stem)

                fpath = Path(root) / fname
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()

                fields, parse_errors = parse_frontmatter(content)
                if fields is None and not parse_errors:
                    skipped_no_frontmatter.append(stem)
                    continue
                if parse_errors:
                    buckets["validation_errors"].append({"stem": stem, "errors": parse_errors})
                    continue

                note_type = str(fields.get("type", "")).strip()

                # MOC detection — by filename prefix OR by explicit type
                if fname.startswith("MOC_") or note_type == "moc":
                    val = validate_moc(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["mocs"].append(extract_moc_record(stem, fields))

                elif note_type == "pattern":
                    val = validate_pattern(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["patterns"].append(extract_pattern_record(stem, fields))

                elif note_type == "solution":
                    val = validate_solution(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["solutions"].append(extract_solution_record(stem, fields))

                elif note_type == "decision":
                    val = validate_decision(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["decisions"].append(extract_decision_record(stem, fields))

                elif note_type == "idea":
                    val = validate_idea(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["ideas"].append(extract_idea_record(stem, fields))

                else:
                    # Default: treat as concept (matches prior behaviour)
                    val = validate_concept(stem, fields)
                    if val:
                        buckets["validation_errors"].append({"stem": stem, "errors": val})
                    buckets["concepts"].append(extract_note_record(stem, fields))

    for key, items in buckets.items():
        if key == "validation_errors":
            items.sort(key=lambda e: e["stem"])
        else:
            items.sort(key=lambda r: r["stem"])
    buckets["_skipped_no_frontmatter"] = sorted(skipped_no_frontmatter)
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

    print(f"[OK] Index written to: {INDEX}")
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
