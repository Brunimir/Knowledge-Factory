"""Capture fidelity — does the note actually say what the source said?

WHY IT EXISTS
    Nothing in this factory has ever compared a claim to the document it cites.
    Capture asserts, process transforms, and every gate inspects artefact SHAPE:
    that adjudication happened, that a Source line changed, that a field exists.
    A well-formed fabrication passes all of them.

    The 2026-08-15 audit measured what that costs. Four sources, three layers
    each (original -> NotebookLM extract -> vault note):

        Ackerlof, "Market for Lemons"    3 of 4 quotes fabricated; a 1970 paper
                                         credited with mitigating collapse via
                                         "blockchain"
        Minto, "Pyramid Principle"       imported Ericsson's long-term working
                                         memory theory; source is a Bookey app
                                         summary, not the book
        Akidau, "Streaming 102"          one misquote that UPGRADES a claim
                                         ("also an example" -> "the canonical
                                         example")
        Hannover Re, APM definitions     20 of 20 quotes exact. Clean.

    The pattern: fabrication tracks source FAME, not difficulty. A canonical
    text is reconstructed from parametric memory and dressed as reading; an
    obscure corporate PDF has no memory to draw on, so it gets read. Obscurity
    is protective, which inverts the intuition anyone would bring to this.

THE DENOMINATOR IS EVERY CONCEPT, and the ceiling is real. `fidelity_pct`
divides by the whole corpus, so it answers "how much of my vault has been
checked against its source" - not "how much of my queue is done". It therefore
CANNOT exceed `provenance_pct`, because 585 notes (67%) cite sources that were
never retained - 307 of them Microsoft Learn courses - and 80 cite nothing at
all. Those are not a review backlog; they are unverifiable by construction.

    fidelity_pct   reviewed / all notes        <- what is assured
    provenance_pct verifiable / all notes      <- the hard ceiling on the above
    the gap between them                       <- the reviewable backlog

Unlike the retain KPI, whose ceiling is a CHOICE (draft is a valid resting
state), this ceiling is a physical impossibility. Raising it is capture's job -
retain the source at capture time - and no amount of reviewing touches it.

REVIEW BY SOURCE, NOT BY NOTE. The 207 verifiable notes span just 24 files
(median 7 notes each; the top 12 cover 80%). Read the document once, adjudicate
everything derived from it. A 24-item queue, not a 207-item one.

VERDICTS - closed vocabulary, same contract as the overlap ledger:

    faithful      every claim traces to the source
    drifted       a real claim distorted - wrong actor, upgraded quote, a
                  role reversed (evidence presented as remedy)
    fabricated    content not in the source, presented as sourced
    unverifiable  source not retained, paywalled, or itself a summary

APPEND-ONLY EVIDENCE, never regenerated. A verdict records what was decided at
a moment; recomputing it would destroy the record of what was actually found.

INVENTED METAPHORS ARE NOT DEFECTS. See METAPHOR CRITERIA in
docs/inbox-pipeline.md. A metaphor the note invents to
teach is legitimate and encouraged; the defect is inventing one and dressing it
as the source's words. Of Minto's 8 invented metaphors, 7 are good teaching
devices and 1 is a defect - it sits in quotation marks.

    python fidelity_ledger.py                # coverage report
    python fidelity_ledger.py pending        # sources awaiting review
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from kzn_paths import VAULT_PATH as VAULT   # the ONE home for the vault root
from kzn_paths import without_twins   # IMP-69: a cloud-sync twin is not a file
CONCEPTS = VAULT / "20_Learning" / "21_Concepts"
SOURCES = VAULT / "30_Sources"
LEDGER = VAULT / "00_Inbox" / "FIDELITY_LEDGER.json"

OUTCOMES = {"faithful", "drifted", "fabricated", "unverifiable"}

# HOW HARD THE CHECK WAS. A verdict without this is uninterpretable: "faithful"
# against a frozen PDF is a much stronger claim than "faithful" against a live
# docs site that has moved since capture.
#
#   deep        every claim traced to the document. Only meaningful against a
#               FROZEN source, where a mismatch IS the finding.
#   high-level  the concept exists in the source and the core idea is broadly
#               right; no anachronism, no invented mechanism. Deliberately NOT
#               claim-by-claim. This is the correct tier for a LIVE source: the
#               article has drifted since capture, so exact divergence carries
#               little signal and chasing it would burn 312 notes' worth of
#               effort to manufacture false findings.
#   triage      no reachable source; recorded as unverifiable without a check.
#               Cheap, and counted separately for exactly that reason.
DEPTHS = {"deep", "high-level", "triage"}


_KNOWN_EXT = r"(docx|epub|html|jpg|json|md|pdf|png|ppt|pptx|txt|xls|xlsm|xlsx|xlt|doc)"


def _norm(s: str) -> str:
    # os.path.splitext would treat any trailing ".0"-style token as an
    # extension, truncating version numbers like "1.43.0" mid-citation.
    # Only strip a *real*, known file extension.
    s = str(s)
    m = re.match(rf"^(.*)\.{_KNOWN_EXT}$", s, re.I)
    base = m.group(1) if m else s
    return re.sub(r"[^a-z0-9]", "", base.lower())


# On a normalised-name COLLISION (e.g. a full PDF and a stub PPTX export both
# titled "Lean Six Sigma[Lean 6sigma Notes Finalised Work]"), silently keeping
# whichever file os.walk() happened to see last picked the 183KB pptx stub over
# the 21MB pdf for all 40 notes citing it (found during the 2026-08-16 fidelity
# review). Break ties by extension: prefer the format whose pagination is
# stable enough for `src-loc` page citations to mean something.
_EXT_PRIORITY = ["pdf", "epub", "docx", "doc", "pptx", "ppt", "html", "md",
                 "txt", "json", "xlsx", "xlsm", "xls", "xlt", "png", "jpg"]


def source_index() -> dict:
    """{normalised stem: real filename} for every retained source file."""
    out = {}
    for root, _dirs, files in os.walk(SOURCES):
        for f in files:
            key = _norm(f)
            if key in out and out[key] != f:
                prev_ext = os.path.splitext(out[key])[1].lstrip(".").lower()
                new_ext = os.path.splitext(f)[1].lstrip(".").lower()
                prev_rank = _EXT_PRIORITY.index(prev_ext) if prev_ext in _EXT_PRIORITY else len(_EXT_PRIORITY)
                new_rank = _EXT_PRIORITY.index(new_ext) if new_ext in _EXT_PRIORITY else len(_EXT_PRIORITY)
                if new_rank >= prev_rank:
                    continue
            out[key] = f
    return out


# A source is CHECKABLE when its text can be reached at review time. That is not
# the same as "a file sits in 30_Sources". Microsoft Learn is first-party
# documentation reachable through the MCP connector, and 312 notes cite it - by
# far the largest single body in the vault. Excluding it would have understated
# what is verifiable by two and a half times.
#
# CAVEAT, and it is a real one: Learn is LIVE and drifts. A note captured from
# the SC-900 path in June 2026 is checked against today's article, so a claim can
# be accurate-at-capture and stale-now, or the reverse. (The Conditional Access
# page already carries "agents (Preview)" content that post-dates the capture.)
# Treat a Learn mismatch as "verify by hand", never as proof of fabrication -
# unlike a retained PDF, which is frozen and where a mismatch IS the finding.
LIVE_DOC_RE = re.compile(r"(microsoft learn|learn\.microsoft\.com)\s*$", re.I)


def notes() -> dict:
    """{stem: {"citations": [...], "local": filename|None, "live": str|None}}

    `local`  a retained file - frozen, exact matching is meaningful.
    `live`   a connector-reachable doc - checkable, but the target moves.
    """
    idx = source_index()
    out = {}
    for p in sorted(without_twins(CONCEPTS.glob("*.md"))):
        txt = p.read_text(encoding="utf-8-sig")
        m = re.search(r"(?m)^- Source:?\s*(.+)$", txt)
        # source filenames can contain literal "[...]" (e.g. "Foo[Bar].pdf"),
        # so allow one level of nested brackets inside the wikilink target
        cites = [c.strip() for c in re.findall(r"\[\[((?:[^\[\]]|\[[^\]]*\])*)\]\]", m.group(1))] if m else []
        cites = [c for c in cites if c]
        local = next((idx[_norm(c)] for c in cites if _norm(c) in idx), None)
        live = None if local else next((c for c in cites if LIVE_DOC_RE.search(c)), None)
        out[p.stem] = {"citations": cites, "local": local, "live": live}
    return out


def load() -> dict:
    if not LEDGER.exists():
        return {}
    try:
        rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {r["note"]: r for r in rows if isinstance(r, dict) and "note" in r}


def evidence(row: dict) -> str:
    """The text recording what was checked. `finding` is the legacy field name."""
    return (row.get("note_text") or row.get("finding") or "").strip()


def append(entries: list) -> int:
    """Append verdicts. An existing note is NOT re-judged - same 'judge once'
    contract as the overlap ledger.

    A VERDICT WITHOUT EVIDENCE IS REJECTED. On 2026-08-16, 641 records were
    written here carrying an outcome, a depth and a date - and nothing saying
    what was checked or against what. Every one said `faithful`. The 2026-09-22
    re-audit judged all 641 again and found 149 that were not: 99 defects and 50
    notes citing a source that does not contain their material, including four
    Peter Lynch notes crediting Buffett's "Institutional Imperative" and a 2003
    book described with the post-2015 term "distributed monolith".

    Nothing in this module could have caught that, because the records were
    well-formed. They asserted a conclusion and recorded no basis for it, which
    is precisely the failure the whole file exists to detect in NOTES - here
    committed by the ledger itself.

    So the floor: an entry must say something about what was inspected. This is
    not a quality check and cannot be one - it only makes a silent blanket stamp
    impossible to record. `triage` is held to it too: "no reachable source" is
    itself evidence, and takes one line to write.
    """
    rows = []
    if LEDGER.exists():
        try:
            rows = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            rows = []
    seen = {r["note"] for r in rows if isinstance(r, dict) and "note" in r}
    added = 0
    for e in entries:
        if e.get("outcome") not in OUTCOMES:
            raise ValueError(f"outcome {e.get('outcome')!r} not in {sorted(OUTCOMES)}")
        if e.setdefault("depth", "deep") not in DEPTHS:
            raise ValueError(f"depth {e['depth']!r} not in {sorted(DEPTHS)}")
        if not evidence(e):
            raise ValueError(
                f"{e.get('note')!r}: verdict {e.get('outcome')!r} carries no evidence. "
                "Set note_text to what was checked and against what.")
        if e["note"] in seen:
            continue
        e.setdefault("date", date.today().isoformat())
        rows.append(e)
        seen.add(e["note"])
        added += 1
    LEDGER.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return added


def coverage() -> dict:
    n = notes()
    done = load()
    total = len(n) or 1
    verifiable = [s for s, v in n.items() if v["local"] or v["live"]]
    frozen = [s for s, v in n.items() if v["local"]]
    reviewed = [s for s in n if s in done]
    by, depth = {}, {}
    for s in reviewed:
        o = done[s]["outcome"]
        by[o] = by.get(o, 0) + 1
        d = done[s].get("depth", "deep")
        depth[d] = depth.get(d, 0) + 1
    # ASSURED is the number that survives scrutiny: notes actually inspected
    # against a document, excluding `triage` (recorded unverifiable, never
    # checked). Without this split, stamping the 353 sourceless notes would lift
    # coverage past 40% overnight without anyone having read anything - the
    # wallpaper failure this vault keeps refusing to ship.
    inspected = len(reviewed) - depth.get("triage", 0)
    defects = by.get("drifted", 0) + by.get("fabricated", 0)
    # sources, not notes: the review queue is per-document
    src_all, src_done = {}, {}
    for s, v in n.items():
        if not v["local"]:
            continue
        src_all.setdefault(v["local"], []).append(s)
        if s in done:
            src_done.setdefault(v["local"], []).append(s)
    return {
        "total_notes": len(n),
        "verifiable": len(verifiable),
        "frozen": len(frozen),
        "live": len(verifiable) - len(frozen),
        "reviewed": len(reviewed),
        "fidelity_pct": round(100 * len(reviewed) / total, 1),
        "provenance_pct": round(100 * len(verifiable) / total, 1),
        "backlog_notes": len(verifiable) - len(reviewed),
        "inspected": inspected,
        "assured_pct": round(100 * inspected / total, 1),
        "defect_rate": round(100 * defects / (inspected or 1), 1),
        "by_depth": depth,
        "by_outcome": by,
        "sources_total": len(src_all),
        "sources_reviewed": sum(1 for f, ss in src_all.items()
                                if len(src_done.get(f, [])) == len(ss)),
    }


def pending(limit: int = 20) -> list:
    """Unreviewed VERIFIABLE sources, biggest first - read the doc once."""
    n = notes()
    done = load()
    per = {}
    for s, v in n.items():
        if v["local"] and s not in done:
            per.setdefault(v["local"], []).append(s)
    return sorted(per.items(), key=lambda kv: -len(kv[1]))[:limit]


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "pending":
        for f, ss in pending(int(args[1]) if len(args) > 1 else 20):
            print(f"  {len(ss):3} note(s)  {f}")
        return 0
    c = coverage()
    print(f"capture fidelity  {c['reviewed']}/{c['total_notes']} notes reviewed "
          f"against their source = {c['fidelity_pct']}%")
    print(f"  provenance      {c['verifiable']}/{c['total_notes']} = {c['provenance_pct']}% "
          f"(the ceiling: {c['frozen']} retained files + {c['live']} connector-reachable)")
    print(f"  backlog         {c['backlog_notes']} verifiable note(s) unreviewed, "
          f"across {c['sources_total'] - c['sources_reviewed']} source document(s)")
    if c["by_outcome"]:
        print(f"  verdicts        {dict(sorted(c['by_outcome'].items()))}")
        print(f"  depth           {dict(sorted(c['by_depth'].items()))}")
        print(f"  assured         {c['inspected']}/{c['total_notes']} = {c['assured_pct']}% "
              f"actually inspected (excludes triage)")
        print(f"  DEFECT RATE     {c['defect_rate']}% of inspected notes carried a defect")
    return 0


if __name__ == "__main__":
    sys.exit(main())

