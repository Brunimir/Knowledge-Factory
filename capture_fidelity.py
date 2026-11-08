"""Capture-time fidelity verification — check the capture BEFORE it becomes notes.

WHERE THIS SITS, AND WHY THERE

    capture (NotebookLM) -> Note Pipe -> [VERIFY] -> process-inbox -> concept notes
                                            ^
                                        this module

    Verification belongs at the END of capture, not after processing, for one
    blunt reason: once a note exists it is expensive to correct and, the moment
    the human promotes it, Safety Rule 6 locks it. A fabrication caught here
    costs an edit to a Note Pipe block. The same fabrication caught after
    promotion costs a Decision.

    The 2026-08-15 audit measured what gets through today: 18.3% of checkable
    `quote:` fields were fabricated, and every content fabrication reached the
    vault intact, because `process-inbox` transforms faithfully and never opens
    the source. Nothing was ever checked against a document.

TWO LAYERS, BECAUSE ONLY ONE OF THEM IS MECHANISABLE

    deterministic   GATE-KF-13 (gate_quote_fidelity.py) - every `quote:` field
                    must appear in the document the block names. No judgement,
                    no false positives, already blocking.
    judgement       THIS manifest - the claims themselves. Whether a Mechanism
                    bullet, a boundary condition or a worked example is
                    supported cannot be decided by string matching; it needs an
                    agent that has read both. The manifest tells it exactly what
                    to check and against what.

WHAT COUNTS AS A CHECKABLE SOURCE

    frozen  a file retained in 30_Sources. Exact matching is meaningful; a
            mismatch IS the finding.
    live    Microsoft Learn, reachable through the MCP connector. 312 notes cite
            it - the largest single body in the vault. But Learn DRIFTS: a claim
            captured from the SC-900 path in June 2026 is checked against
            today's article. A mismatch here means "verify by hand", never
            "fabricated". Do not let a live-source mismatch fail a run.
    absent  nothing to check against. Not a defect and not a backlog - it is
            `provenance`, and the fix is at capture time: keep the file.

VERDICTS reuse the FIDELITY_LEDGER vocabulary, keyed by stem, so a verdict made
here carries forward to the note that stem becomes:

    faithful / drifted / fabricated / unverifiable

    python capture_fidelity.py manifest   # build the queue from Note Pipe
    python capture_fidelity.py gate       # block process-inbox on unverified
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from kzn_paths import VAULT_PATH as VAULT   # the ONE home for the vault root
from kzn_paths import without_twins   # IMP-69: a cloud-sync twin is not a file
NOTE_PIPE = VAULT / "00_Inbox" / "Note Pipe"
MANIFEST = VAULT / "00_Inbox" / "CAPTURE_FIDELITY.json"

sys.path.insert(0, str(VAULT))


def _claims(block: str) -> dict:
    """The assertions worth checking, by kind. Everything else is packaging."""
    def sect(name, stop=r"\n## "):
        m = re.search(r"## %s(.*?)(?=%s|$)" % (re.escape(name), stop), block, re.S)
        return m.group(1) if m else ""

    core = sect("Core Idea (Summary)")
    mech = sect("Mechanism (Key details)")
    app = sect("Application")
    bullets = [b.strip(" -•\t") for b in re.findall(r"(?m)^\s*[-•]\s+(.+)$", mech)]
    return {
        # the single claim the note stands on
        "core_idea": " ".join(re.split(r"(?<=[.!?])\s", " ".join(core.split()))[:2])[:400],
        # mechanism bullets minus the boundary, which is checked separately
        "mechanism": [b for b in bullets if not b.startswith("**Boundary")][:8],
        "boundary": next((b for b in bullets if b.startswith("**Boundary")), None),
        # examples and metaphors are where invention concentrates
        "example": (re.search(r"\*\*Example:\*\*\s*(.+)", block) or [None, None])[1],
        "metaphor": (re.search(r"\*\*Metaphor:\*\*\s*(.+)", block) or [None, None])[1],
        "when_not": (re.search(r"\*\*When NOT to use:\*\*\s*(.+)", app) or [None, None])[1],
        # structured citations - the deterministic half already gates these
        "quotes": re.findall(r"quote:\s*\"([^\"]{20,})\"", block),
    }


# TEACHING AIDS THE REVIEW MAY ADD (2026-08-15).
#
# Review is the RIGHT moment to author these and generation is the wrong one.
# The diagnosed root cause of 8 fabricated Minto metaphors was template slot
# pressure: a field demanding to be filled while the model was mid-extraction. At
# review there is no slot to fill - the reviewer has read both sides and is
# making a deliberate authoring decision. The Minto capture returning [NONE] six
# times out of six is that instruction working; it is not a gap in the model, it
# is a gap this step exists to close.
#
# METAPHOR and EXAMPLE ARE NOT THE SAME RISK, and conflating them is what caused
# the damage:
#
#   metaphor  an ANALOGY. Asserts nothing about the domain - "MECE is like a
#             completed puzzle" adds no fact to MECE. Invent freely under the
#             four criteria in inbox-pipeline.md. Editorial by default; the only
#             hard rule is criterion 1, never dress it as the author's words.
#             Only 20.4% of notes carry one, and the flashcard extractor reads
#             the field ("do NOT invent one"), so ~80% of cards ship without a
#             visualisation aid.
#
#   example   a CONCRETE INSTANCE, which does assert something about the world.
#             Minto's fabricated "warehouse at 100% capacity needing 20% more
#             stock" was an invented example wearing the author's voice. Prefer
#             one FROM the source. If you invent, mark it inline:
#                 **Example:** *(illustrative)* ...
#             Inline, not a new label - `gate_concept_body`, `concept_quality`
#             and the flashcard extractor all match on the literal
#             `**Example:**`, so a renamed field would go silently unread.
#
# Adding either NEVER changes the fidelity verdict. The verdict asks whether the
# note misrepresents the source; an editorial metaphor does not, by construction.
def enrichable(claims: dict) -> list:
    """Teaching aids this block lacks - offered to the reviewer, never auto-filled."""
    out = []
    if not claims.get("metaphor") or "[NONE]" in str(claims.get("metaphor")):
        out.append("metaphor")
    if not claims.get("example") or "[NONE]" in str(claims.get("example")):
        out.append("example")
    return out


def _resolve(block: str) -> dict:
    """Where this block's claims can be checked, and how frozen that target is."""
    import fidelity_ledger as fl
    fn = re.search(r"Filename:\s*(.+)", block)
    name = fn.group(1).strip() if fn else ""
    if name:
        idx = fl.source_index()
        key = re.sub(r"[^a-z0-9]", "", os.path.splitext(name)[0].lower())
        if key in idx:
            return {"kind": "frozen", "target": idx[key],
                    "how": "read the file; a mismatch is the finding"}
        if fl.LIVE_DOC_RE.search(name):
            return {"kind": "live", "target": name,
                    "how": "microsoft_docs_search; Learn drifts, so a mismatch "
                           "means verify by hand, never 'fabricated'"}
    return {"kind": "absent", "target": name or None,
            "how": "nothing to check against - this is provenance, not a defect"}


def _verdict_key(stem: str, claims: dict) -> str:
    """Identity for carrying a verdict forward: same stem, same claims. If the
    Note Pipe block changed since it was verified, the key changes too, so the
    old verdict does NOT survive - a changed capture must be re-checked, never
    trusted on the strength of a verdict given to different text."""
    import hashlib
    blob = json.dumps(claims, sort_keys=True, ensure_ascii=False)
    return f"{stem}:{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


def manifest() -> dict:
    # PRESERVE VERDICTS ACROSS REBUILDS. This is called fresh before every
    # `gate` check (see launch-process-inbox.ps1), which used to reset every
    # `verdict` to null unconditionally - so a human/agent that verified a
    # block and wrote its verdict would see that work erased the next time the
    # launcher ran, forcing the exact same re-verification forever. Same
    # "judge once" contract as fidelity_ledger.append() and the overlap ledger.
    prior_verdicts = {}
    if MANIFEST.exists():
        try:
            prior = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
            for b in prior.get("blocks", []):
                if b.get("verdict"):
                    prior_verdicts[_verdict_key(b["stem"], b.get("claims", {}))] = b["verdict"]
        except Exception:
            pass

    blocks = []
    for f in sorted(without_twins(NOTE_PIPE.glob("*.md"))):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        for b in re.split(r"(?=Concept title:)", text):
            m = re.search(r"Stem \(safe\):\s*(\S+)", b)
            if not m:
                continue
            src = _resolve(b)
            cl = _claims(b)
            carried = prior_verdicts.get(_verdict_key(m.group(1), cl))
            blocks.append({"stem": m.group(1), "file": f.name,
                           "source": src, "claims": cl,
                           "enrich": enrichable(cl),   # teaching aids it lacks
                           "verdict": carried})     # carried forward if unchanged, else the AGENT writes this
    out = {"generated": __import__("datetime").date.today().isoformat(),
           "blocks": blocks,
           "checkable": sum(1 for b in blocks if b["source"]["kind"] != "absent"),
           "vocabulary": ["faithful", "drifted", "fabricated", "unverifiable"],
           "enrich_available": sum(1 for b in blocks if b["enrich"]),
           "enrich_note": ("metaphor: invent freely under the four criteria, never "
                           "as the author's words. example: prefer one from the "
                           "source; if invented, mark it inline **Example:** "
                           "*(illustrative)* - inline because three downstream "
                           "parsers match the literal `**Example:**`.")}
    MANIFEST.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def gate() -> int:
    """Block process-inbox while a CHECKABLE capture is unverified or fabricated."""
    if not list(without_twins(NOTE_PIPE.glob("*.md"))):
        print("GATE-KF-14 capture fidelity: Note Pipe empty - PASS (vacuous)")
        return 0
    if not MANIFEST.exists():
        print("GATE-KF-14 capture fidelity: no manifest - run "
              "`python capture_fidelity.py manifest`, then verify")
        return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    pipe = {b["stem"] for f in without_twins(NOTE_PIPE.glob("*.md"))
            for b in [{"stem": s} for s in re.findall(
                r"Stem \(safe\):\s*(\S+)",
                f.read_text(encoding="utf-8-sig", errors="replace"))]}
    known = {b["stem"] for b in m.get("blocks", [])}
    if pipe - known:
        print(f"GATE-KF-14 capture fidelity: manifest is STALE - "
              f"{len(pipe - known)} block(s) not in it. Regenerate.")
        return 1

    checkable = [b for b in m["blocks"] if b["source"]["kind"] != "absent"]
    unjudged = [b for b in checkable if not b.get("verdict")]
    bad = [b for b in checkable if b.get("verdict") == "fabricated"]
    print(f"GATE-KF-14 capture fidelity: {len(checkable)} checkable block(s), "
          f"{len(m['blocks']) - len(checkable)} with no reachable source")
    if bad:
        print(f"\n  {len(bad)} block(s) verdict FABRICATED - these must not become notes:")
        for b in bad:
            print(f"    {b['stem']}  <- {b['source']['target']}")
        return 1
    if unjudged:
        print(f"\n  {len(unjudged)} checkable block(s) carry no verdict:")
        for b in unjudged[:12]:
            print(f"    {b['stem']:44} [{b['source']['kind']}] {b['source']['target']}")
        print("\n  Verify each against its source, then write `verdict` into the")
        print("  manifest. A capture nobody checked is not a capture nobody can trust -")
        print("  it is one whose trustworthiness was never established either way.")
        return 1
    print("  PASS - every checkable capture carries a fidelity verdict")
    return 0


def main(argv) -> int:
    if argv and argv[0] == "manifest":
        m = manifest()
        kinds = {}
        for b in m["blocks"]:
            kinds[b["source"]["kind"]] = kinds.get(b["source"]["kind"], 0) + 1
        print(f"[ok] {len(m['blocks'])} block(s) -> {MANIFEST.name}   {kinds}")
        if m["enrich_available"]:
            miss = {}
            for b in m["blocks"]:
                for e in b["enrich"]:
                    miss[e] = miss.get(e, 0) + 1
            print(f"     {m['enrich_available']} block(s) could gain a teaching aid: {miss}")
            print("     metaphor: invent freely (4 criteria) | example: prefer the "
                  "source's, else mark *(illustrative)*")
        return 0
    if argv and argv[0] == "gate":
        return gate()
    print(__doc__.strip().split("\n\n")[0])
    print("\n  python capture_fidelity.py manifest | gate")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

