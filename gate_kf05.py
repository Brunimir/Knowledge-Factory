"""GATE-KF-05 - the flashcard authoring gate (FC-1..FC-4, FC-6).

Implements IMP-34 under [[Executable Gates and Complete Andon - Decision]].
Limits set by IMP-71 under [[Flashcard Card Design - Decision]]: at most 6 cards
per note and 18 words on a back (FC-4 blocks); over 9 words or more than one
sentence warns (FC-6). The numbers are practitioner opinion, not findings.

WHY THIS GATE EXISTS AND WHY IT RUNS HERE
    A flashcard that reaches Anki carries a 13-digit ^id, and correcting it
    afterwards destroys its review history. Every other gated artefact in the
    factory can be rewritten. So this is the one place where a check has to run
    BEFORE the irreversible step - between the agent's write and the launcher's
    Anki sync.

SCOPE - FORWARD ONLY, BY CONSTRUCTION
    Only the files listed in FLASHCARD_RUN_RESULT.json's files_written[] are
    read. The 99/263 pre-existing notes that repeat the boundary are therefore
    provably untouched - no suppression list is needed, because a baselined file
    is simply never opened. Within a file read, a card already carrying the
    plugin's ^id anchor is synced and skipped too (IMP-71): it can no longer be
    corrected. The agent is forbidden from writing an anchor; nothing here can
    tell one it wrote anyway from a real one.

WHAT IS *NOT* HERE
    FC-5 (fidelity: every clause traces to a manifest field) is JUDGMENT and is
    deliberately not implemented. Folding a rubric dimension into blocking code
    is how a gate acquires false positives and gets switched off. The pilot run
    proved the point: the one real fidelity defect in 75 cards ("because the
    house cannot walk", an explanation the source never gives) is invisible to
    every check below, and a causal-connective screen flagged 7 candidates of
    which only 1 was real - 86% false positives. That belongs to a human.

WHAT BLOCKS - RESOLVED EMPIRICALLY (gap ENV-24, closed 2026-08-06)

    FC-2, FC-3, FC-4    BLOCKING. Decidable.
    FC-6                ADVISORY. Decidable, but the target is softer than the cap.
    FC-1                RECLASSIFIED AS JUDGMENT - not implemented here.
    FC-5                judgment, as always. Whether a card sticks is judgment too.

    ENV-24 asked whether FC-1/FC-2 could be made decidable. They were measured
    separately against a corpus of 63 cards over 21 concepts whose ground truth
    was established by hand. The answer differs for the two, and the difference
    is structural rather than a matter of thresholds:

    FC-1 IS NOT DECIDABLE BY LEXICAL MEANS. Two definitions were tried and both
    failed. Raw overlap against the boundary text gave 1 false positive; the
    sharper "boundary-exclusive tokens" definition gave 3. The reason is visible
    in the data: for "Avoidance of Adverbs and Qualifiers" the boundary says some
    adverbs CANNOT be cut while the HOW card says redundant adverbs CAN be -
    opposite claims in identical vocabulary. A concept's boundary and its
    mechanism discuss the same nouns by definition, so no lexical measure
    separates "restates the boundary" from "discusses the same subject". FC-1
    asks for semantic entailment, which is a judgment task. It is therefore
    reclassified to a rubric dimension beside FC-5 rather than carried here as a
    check that cries wolf.

    (A structural trap was found on the way: the manifest DUPLICATES the boundary
    into `mechanism` - "the full ## Mechanism section ... includes the boundary
    line" - so differencing against mechanism erased every boundary-exclusive
    token and left 10 of 21 concepts undecidable. Corrected before the second
    measurement, which is how the true 3-false-positive figure emerged.)

    FC-2 IS DECIDABLE, and now blocks. It compares a card against tokens found
    ONLY in the source note's EXCLUDED sections (## Ideas, ## Links) and in no
    manifest field. Those sections hold different material - links to other notes,
    idea fragments - so their exclusive tokens are meaningful where the
    boundary's are not. Measured on the same corpus: 21 of 21 concepts testable,
    **0 false positives**.

    The principle behind both calls is unchanged: a blocking check that halts a
    clean batch gets switched off, and a gate nobody runs is worth less than no
    gate. The difference is that FC-2 now has the evidence to block and FC-1 has
    the evidence that it never could.

EXIT CODES
    0  every file passes - safe to sync
    1  at least one file is BLOCKED - the launcher must not sync it
    2  could not run (missing inputs) - the launcher should treat as unsafe
"""

import json
import os
import re
import sys

from kzn_paths import VAULT          # the ONE home for the vault root
FC_DIR = os.path.join(VAULT, "20_Learning", "23_FlashCards")
CONCEPTS = os.path.join(VAULT, "20_Learning", "21_Concepts")
RUN_RESULT = os.path.join(VAULT, "00_Inbox", "FLASHCARD_RUN_RESULT.json")
MANIFEST = os.path.join(VAULT, "00_Inbox", "FLASHCARD_CANDIDATES.json")
OUT = os.path.join(VAULT, "00_Inbox", "GATE_KF05_RESULT.json")

# Only the decidable checks block. FC-1 is absent by design - see the docstring.
BLOCKING = {"FC-0", "FC-2", "FC-3", "FC-4"}

MAX_CARDS = 6
MAX_BACK_WORDS = 18
TARGET_BACK_WORDS = 9
LEAK_MIN_EXCL = 3         # below this an excluded section is too thin to judge
LEAK_MIN_HITS = 2         # exclusive tokens a card must echo to count as leaked.
                          # Measured: 0 false positives over 21 concepts / 63
                          # cards written from the manifest alone.

STOP = set("""a an the and or but if then than that this these those of to in on at by for with
from as is are was were be been being it its it's you your they their them he she we our us not
no do does did can could should would may might will shall have has had which who whom whose what
when where why how all any both each few more most other some such only own same so too very s t
just don now one two three""".split())

# Sentence split that survives a closing quote or paren after the terminator.
# A naive [.!?]\s+ split undercounts `... like "improve." Next sentence` - hit
# twice while building the pilot checker, so it is spelled out here once.
SENT_SPLIT = re.compile(r'(?<=[.!?])["\'”\)]?\s+(?=[A-Z"\'“(])')

# A marker regex ("breaks down when", "fails if", ...) was tried here and
# removed: it double-counted a single genuine boundary mention on "Positive
# Form", because the WHEN card legitimately paraphrases the boundary as its
# "Do NOT" clause. Overlap against the manifest's own boundary text is the
# less wrong of the two proxies.


# The plugin appends a block anchor (`^q-xxxx` or a legacy 13-digit id) to a
# synced card line; it is not part of the question or answer.
ANCHOR = re.compile(r"\s*\^(?:q-[a-z0-9]{4}|\d{13})\s*$")


def words(text):
    """Content words, crudely stemmed to a 5-char prefix so morphological
    variants match (varying/vary, participles/participle)."""
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t[:5] for t in toks if len(t) > 2 and t not in STOP}


def overlap(sub, whole):
    """Share of `sub`'s content words present in `whole`."""
    s = words(sub)
    if not s:
        return 0.0
    return len(s & words(whole)) / len(s)


# An acronym with its spelled-out form: `ISS (International Space Station)`.
ACRONYM_FORM = re.compile(r"(\S+)\s+\(([^()]+)\)")


def is_acronym_form(match):
    """True when the brackets spell out the acronym before them: the acronym has
    at least two capitals, and they appear in order in the bracketed text."""
    capitals = [c for c in match.group(1) if c.isupper()]
    if len(capitals) < 2:
        return False
    expansion = iter(match.group(2).upper())
    return all(c in expansion for c in capitals)


def back_words(answer):
    """Words on a back. A bare ` - ` separator is not a word, and an acronym
    with its spelled-out form is one word."""
    merged = ACRONYM_FORM.sub(lambda m: "ACRONYM" if is_acronym_form(m) else m.group(0), answer)
    return sum(1 for t in merged.split() if re.search(r"\w", t))


def parse_cards(text):
    """Return ([(line_no, body)], stray, synced) for a flashcard file.

    A card is exactly one line: a list item, `- Question :: Answer`. A trailing
    `^id` anchor means the plugin has synced it, so it is counted in `synced` and
    not returned. This is the flashcards-obsidian
    v2 inline syntax; v2 reads `::` only inside list items, and treats a standalone
    `#card` line as "previous heading is the question". Anything else - including
    a leftover v1 `#card` line - is an FC-3 structural defect, reported by the caller.
    """
    lines = text.splitlines()
    start = 0
    for i, l in enumerate(lines):
        if l.startswith("# "):
            start = i + 1
            break
    cards, stray, synced = [], [], 0
    i = start
    while i < len(lines):
        raw = lines[i]
        if raw.startswith("- "):
            if ANCHOR.search(raw[2:]):
                synced += 1
            else:
                cards.append((i + 1, raw[2:]))
            i += 1
            continue
        if raw.strip() and not raw.startswith("^") and not raw.startswith("<!--"):
            stray.append((i + 1, raw.strip()[:60]))
        i += 1
    return cards, stray, synced


def attribute(question, titles):
    """Best-matching concept title for a card question.

    Substring matching is not enough: GF-2 legitimately rephrases a title into
    the question ("Varying Sentence and Paragraph Length" -> "when should you
    vary sentence and paragraph length"), which silently orphaned a card in the
    pilot check. Stemmed token overlap handles it.
    """
    best, score = None, 0.0
    for t in titles:
        sc = overlap(t, question)
        if sc > score:
            best, score = t, sc
    return (best, score) if score >= 0.6 else (None, score)


def check_file(path, cands):
    """Run FC-1..FC-4 over one flashcard file. Returns a result dict."""
    name = os.path.basename(path)
    res = {"file": name, "cards": 0, "concepts": [], "violations": [], "blocked": False}

    if not os.path.exists(path):
        res["violations"].append({"check": "FC-0", "detail": "file not found"})
        res["blocked"] = True
        return res

    text = open(path, encoding="utf-8").read()
    cards, stray, synced = parse_cards(text)
    res["cards"] = len(cards)
    res["synced_skipped"] = synced

    by_title = {c["title"]: c for c in cands}
    titles = list(by_title)
    grouped = {}

    for ln, body in cards:
        # ---- FC-3 structural (exact) -----------------------------------
        if "::" not in body:
            res["violations"].append({"check": "FC-3", "line": ln,
                                      "detail": "card line has no :: separator"})
            continue
        q, a = body.split("::", 1)
        for pat, why in ((r"—", "em-dash"), (r"\[\[", "wikilink"),
                         (r"\*\*", "bold"), (r"^\s*[-*+]\s", "bullet"),
                         (r"^\s*#{1,6}\s", "heading")):
            if re.search(pat, body):
                res["violations"].append({"check": "FC-3", "line": ln, "detail": why})

        owner, _score = attribute(q, titles)
        if owner is None:
            res["violations"].append({"check": "FC-3", "line": ln,
                                      "detail": "card matches no manifest concept"})
            continue
        grouped.setdefault(owner, []).append((ln, q.strip(), a.strip()))

        # ---- FC-4 back length (exact), FC-6 target (advisory) -----------
        w = back_words(a)
        if w > MAX_BACK_WORDS:
            res["violations"].append({"check": "FC-4", "line": ln,
                                      "detail": f"{w} words on the back (max {MAX_BACK_WORDS})"})
        elif w > TARGET_BACK_WORDS:
            res["violations"].append({"check": "FC-6", "line": ln,
                                      "detail": f"{w} words on the back (target {TARGET_BACK_WORDS})"})
        n = len([s for s in SENT_SPLIT.split(a.strip()) if s.strip()])
        if n > 1:
            res["violations"].append({"check": "FC-6", "line": ln,
                                      "detail": f"{n} sentences on the back (one idea, one sentence)"})
        if ";" in a:
            res["violations"].append({"check": "FC-6", "line": ln,
                                      "detail": "semicolon on the back (usually two ideas)"})

    for ln, txt in stray:
        res["violations"].append({"check": "FC-3", "line": ln,
                                  "detail": f"non-card line in body: {txt}"})

    for title, items in grouped.items():
        cand = by_title[title]
        res["concepts"].append({"title": title, "stem": cand["stem"], "cards": len(items)})

        # ---- FC-4 card cap (exact) -------------------------------------
        if len(items) > MAX_CARDS:
            res["violations"].append({"check": "FC-4", "line": items[0][0],
                                      "detail": f"{title}: {len(items)} cards (max {MAX_CARDS})"})

        # ---- FC-1 -------------------------------------------------------
        # DELIBERATELY ABSENT. Reclassified to a judgment rubric dimension
        # (ENV-24): boundary and mechanism share vocabulary by nature, so no
        # lexical test separates "restates the boundary" from "discusses the
        # same subject". Measured at 1 and 3 false positives under two
        # definitions, against a ground truth of 0. A human judges it.

        # ---- FC-2 section allowlist (decidable, BLOCKING) ---------------
        # The manifest carries only the 6 permitted fields, so leakage is
        # detectable as content whose tokens appear in the SOURCE note's
        # EXCLUDED sections and in NO manifest field. Unlike FC-1, those
        # sections hold different material (links, idea fragments), so their
        # exclusive tokens are meaningful. Measured: 0 false positives.
        allowed = " ".join(str(cand.get(f) or "") for f in
                           ("core", "metaphor", "mechanism", "boundary", "when_to", "when_not"))
        src = os.path.join(CONCEPTS, cand["stem"] + ".md")
        if os.path.exists(src):
            body = open(src, encoding="utf-8", errors="replace").read()
            secs = re.findall(r"(?ms)^##\s+(?:Ideas|Links)\s*\n(.*?)(?=\n##\s|\Z)", body)
            excl = words(" ".join(secs)) - words(allowed)
            if len(excl) >= LEAK_MIN_EXCL:
                for ln, _q, a in items:
                    got = words(a) & excl
                    if len(got) >= LEAK_MIN_HITS:
                        res["violations"].append(
                            {"check": "FC-2", "line": ln,
                             "detail": f"{title}: {len(got)} token(s) traced to an excluded "
                                       f"section and to no manifest field: {', '.join(sorted(got)[:4])}"})

    # Split before deciding: only the decidable checks may halt a sync.
    res["warnings"] = [v for v in res["violations"] if v["check"] not in BLOCKING]
    res["violations"] = [v for v in res["violations"] if v["check"] in BLOCKING]
    res["blocked"] = len(res["violations"]) > 0
    return res


def main():
    args = sys.argv[1:]
    files = []
    if "--files" in args:
        files = args[args.index("--files") + 1:]
    else:
        if not os.path.exists(RUN_RESULT):
            print("GATE-KF-05: FLASHCARD_RUN_RESULT.json not found - cannot scope the gate.")
            return 2
        try:
            files = json.load(open(RUN_RESULT, encoding="utf-8")).get("files_written") or []
        except Exception as e:
            print(f"GATE-KF-05: could not read run result: {e}")
            return 2

    if not files:
        print("GATE-KF-05: files_written[] is empty - nothing written, nothing to gate.")
        json.dump({"blocked": [], "passed": [], "results": []}, open(OUT, "w", encoding="utf-8"), indent=2)
        return 0

    if not os.path.exists(MANIFEST):
        print("GATE-KF-05: FLASHCARD_CANDIDATES.json not found - cannot judge fidelity scope.")
        return 2
    cands = json.load(open(MANIFEST, encoding="utf-8"))["candidates"]

    results = [check_file(os.path.join(FC_DIR, os.path.basename(f)), cands) for f in files]
    blocked = [r["file"] for r in results if r["blocked"]]
    passed = [r["file"] for r in results if not r["blocked"]]

    json.dump({"generated": __import__("datetime").date.today().isoformat(),
               "blocked": blocked, "passed": passed, "results": results},
              open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"GATE-KF-05 (FC-1..FC-4, FC-6) over {len(files)} file(s) written this run:")
    for r in results:
        mark = "BLOCKED" if r["blocked"] else "pass   "
        print(f"  [{mark}] {r['file']}  ({r['cards']} cards, {len(r['concepts'])} concepts)")
        for v in r["violations"]:
            loc = f"line {v['line']}" if "line" in v else "-"
            print(f"             BLOCK {v['check']} {loc}: {v['detail']}")
        for v in r.get("warnings", []):
            loc = f"line {v['line']}" if "line" in v else "-"
            print(f"             warn  {v['check']} {loc}: {v['detail']}")
    print("  Blocking: FC-2 (section allowlist), FC-3 (structure), FC-4 (cards per note, words on a back). Advisory: FC-6.")
    print("  FC-1 and FC-5 are JUDGMENT and are not checked here - a human still reads the cards.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())

