"""GATE-KF-13 - every `quote:` in a capture extract must exist in its source.

WHAT IT PROBES
    Capture extracts justify each typed edge with a verbatim citation and a
    self-assigned confidence:

        - mechanism-of The Lemons Principle | quote: "..." | confidence: HIGH

    Nothing has ever checked those. The 2026-08-15 audit did, by hand, across
    four sources:

        Akerlof     3 of 4 quotes absent from the paper, all `confidence: HIGH`
        Streaming   "the canonical example of unaligned windows" - the source
                    says "they are ALSO AN example"; the quote upgrades the claim
        Minto       extract not retained; the fabrication surfaced in the note
        Hannover Re 20 of 20 exact. A clean source stays clean.

    The quotes never reach the note - the concept schema has no quote field - but
    the EDGES they justify do. So the vault ends up carrying relationships whose
    only evidence was invented, with the evidence discarded. Nobody downstream
    can tell. This gate is the one place the claim and the document meet.

WHY IT TARGETS THE EXTRACT AND NOT THE NOTE (learned the hard way, 2026-08-15)
    The first build of this gate checked quoted spans in note PROSE. It reported
    168 failures across 195 notes - 86%, essentially all false. In this vault a
    double quote overwhelmingly marks a SCARE QUOTE or a coined term ("whisper",
    "Watermelon", "engine room", "Fabricated Heroism"), not a citation, and a
    naive matcher pairs quote #2 with quote #3 across intervening prose and
    invents spans nobody ever wrote.

    That is the same failure this factory keeps logging - the instrument
    asserting more than it checked - committed by the instrument built to stop
    it. The lesson: gate the field whose MEANING is unambiguous. `quote:` is
    structured and means exactly one thing. Prose quotation marks mean five.

    Consequence: metaphor criterion 1 ("do not dress an invention as the
    source's words") is NOT machine-enforceable in note prose. It stays a
    review-time judgement recorded in FIDELITY_LEDGER.json.

CONSERVATIVE BY CONSTRUCTION - a gate that cries wolf gets switched off:
  * `...` elisions split; each segment checked independently.
  * [bracketed editorial insertions] stripped - that is what brackets are for.
  * fuzzy fallback (partial_ratio >= FUZZ) absorbs scan noise. Scholarly PDFs
    are dirty: the JSTOR Akerlof scan bleeds columns mid-sentence, so exact
    matching alone would fail on genuine quotes.
  * a block whose source is missing, unreadable (epub), or not retained is
    SKIPPED, never failed. Unreadable is not the same as wrong.

    python gate_quote_fidelity.py                  # Note Pipe (pre-run)
    python gate_quote_fidelity.py <extract.md>...  # named extracts
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

VAULT = Path(os.path.dirname(os.path.abspath(__file__)))
NOTE_PIPE = VAULT / "00_Inbox" / "Note Pipe"
SOURCES = VAULT / "30_Sources"

FUZZ = 85
MIN_LEN = 20

_SMART = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " "}


def flatten(s: str) -> str:
    for a, b in _SMART.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def strip_page_furniture(pages: list) -> str:
    """Join pages with running heads/feet removed.

    WHY THIS IS NOT COSMETIC. Scanned PDFs inject furniture into the middle of a
    sentence that continues across a page break. The JSTOR Akerlof scan turns

        "...deteriorates as the price level rises - with the result
         that no insurance sales may take place at any price."

    into that sentence with "This content downloaded from 142.58.148.213 on Mon,
    13 Aug 2018 ... All use subject to https://about.jstor.org/terms" wedged
    between the two halves. A model quoting the real sentence then fails an exact
    match AND the fuzzy fallback, because the interpolation is long. Observed
    2026-08-15: a correct capture block was REJECTED on a quote that is verbatim
    in the paper (partial_ratio 100 once the furniture is gone).

    Rejecting good captures is worse than the disease. A gate that fires on
    correct work gets switched off, and then it protects nothing.

    Detection is positional-frequency, not a pattern list: a line repeated on
    many pages is furniture whatever it says, so this needs no per-publisher
    rules. Kept deliberately conservative - short lines only, and only when they
    recur on a third of pages - so body text that happens to repeat survives.

    Frequency is keyed on the line with DIGITS MASKED, because the commonest
    furniture of all is a running head carrying the page number:

        MARKET FOR "LEMONS": AND MARKET MECHANISM 489
        MARKET FOR "LEMONS": AND MARKET MECHANISM 493

    Those are distinct strings and a literal-frequency count sees each once. The
    Akerlof quote above still failed after the first version of this function for
    exactly that reason - the header sat between the two halves of the sentence.
    """
    if len(pages) < 3:
        return "\n".join(pages)
    from collections import Counter
    key = lambda s: re.sub(r"\d+", "#", s.strip()).lower()
    seen = Counter()
    for p in pages:
        for ln in {l.strip() for l in p.splitlines() if l.strip()}:
            if len(ln) <= 120:
                seen[key(ln)] += 1
    cut = max(3, int(len(pages) * 0.33))
    furniture = {k for k, n in seen.items() if n >= cut}
    out = []
    for p in pages:
        out.append("\n".join(l for l in p.splitlines()
                             if key(l) not in furniture))
    return "\n".join(out)


def read_source(path: Path) -> str | None:
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import fitz
            d = fitz.open(path)
            return strip_page_furniture([d[i].get_text() for i in range(d.page_count)])
        if ext in (".md", ".txt"):
            return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return None
    return None


def _source_index() -> dict:
    out = {}
    for root, _d, files in os.walk(SOURCES):
        for f in files:
            out[re.sub(r"[^a-z0-9]", "", os.path.splitext(f)[0].lower())] = Path(root) / f
    return out


def audit(paths: list) -> tuple:
    """(checked, skipped, failures) over every `quote:` in the given extracts."""
    from rapidfuzz import fuzz
    idx = _source_index()
    cache: dict = {}
    checked = skipped = 0
    failures = []

    for p in paths:
        text = Path(p).read_text(encoding="utf-8-sig", errors="replace")
        for block in re.split(r"(?=Concept title:)", text):
            stem_m = re.search(r"Stem \(safe\):\s*(\S+)", block)
            if not stem_m:
                continue
            stem = stem_m.group(1)
            quotes = re.findall(r"quote:\s*\"([^\"]{%d,})\"" % MIN_LEN, block)
            if not quotes:
                continue
            fn = re.search(r"Filename:\s*(.+)", block)
            key = re.sub(r"[^a-z0-9]", "",
                         os.path.splitext(fn.group(1).strip())[0].lower()) if fn else None
            spath = idx.get(key) if key else None
            if spath is None:
                skipped += len(quotes)
                continue
            if spath not in cache:
                cache[spath] = read_source(spath)
            src = cache[spath]
            if not src:
                skipped += len(quotes)
                continue
            flat = flatten(src)
            for q in quotes:
                checked += 1
                for seg in q.split("..."):
                    seg = flatten(re.sub(r"\[[^\]]*\]", " ", seg))
                    if len(seg) < MIN_LEN or seg in flat:
                        continue
                    if fuzz.partial_ratio(seg, flat) >= FUZZ:
                        continue
                    failures.append((stem, spath.name, q, seg))
                    break
    return checked, skipped, failures


def main(argv) -> int:
    paths = [Path(a) for a in argv] if argv else sorted(NOTE_PIPE.glob("*.md"))
    if not paths:
        print("GATE-KF-13 quote fidelity: no extract files to check - PASS (vacuous)")
        return 0
    checked, skipped, failures = audit(paths)
    print(f"GATE-KF-13 quote fidelity: {checked} quote(s) checked, "
          f"{skipped} skipped (source not retained/readable)")
    if failures:
        print(f"\n  {len(failures)} FABRICATED quote(s) - not present in the cited source:\n")
        for stem, src, q, seg in failures:
            print(f"  [{stem}]  <- {src}")
            print(f"      claims : \"{q[:105]}\"")
            print(f"      missing: {seg[:105]}\n")
        print("  A `quote:` field asserts the document says this, verbatim.")
        print("  An invented illustration is fine - it just cannot wear quotation marks.")
        return 1
    print("  PASS - every quote traces to its source")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
