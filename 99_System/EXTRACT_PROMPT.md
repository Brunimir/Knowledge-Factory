# Extract Prompt

Paste this at the end of a Claude conversation when you suspect (per the gem heuristic) it produced something vault-worthy.

---

## The prompt

```
I want to evaluate this conversation for vault-worthy content.

First, apply this heuristic honestly: does this conversation contain something I 
couldn't articulate at the start? Not synthesis of things I already knew. Not a 
nicely-worded version of an existing idea. Something genuinely new in framing, 
mechanism, or connection.

Be critical. Most conversations don't pass this bar, and that's fine. If nothing 
rises to vault-worthy, say so plainly and stop.

If something does pass, draft ONE candidate note using the template below. Pick 
the single sharpest idea, not multiple. The candidate goes to 
00_Inbox/AI_Candidates/ in my Obsidian vault and will be reviewed during my 
weekly cleanup.

Template:
---
status: proposed
source: claude-chat-[today's date]
suggested_location: [Concepts/ | Patterns/ | Decisions/ | other]
suggested_type: [concept | pattern | decision | refinement]
extracted: [today's date]
related: []
---

# Candidate · [Sharp, specific title]

## Core idea
[1-2 sentences. The essential claim.]

## Mechanism
[How it works. Why it's true. The reasoning chain.]

## Application
[Where this applies. When to reach for it. What it predicts or enables.]

## Sources
- Claude conversation, [today's date]
- [Any external references that came up]

## Related
[Wikilinks to vault concepts this touches, if you know them]

---

Output rules:
- If nothing is vault-worthy, output exactly: "Nothing in this conversation rises to vault-worthy. Reasons: [brief]"
- If something is vault-worthy, output ONLY the filled-in template. No preamble, no postscript.
- Suggest the most plausible folder in suggested_location, but mark it as a suggestion.
- Title should be specific. "Memory architecture" is too broad. "Embeddings as lossy compression of meaning" is better.
- Use my own phrasing where possible — I should be able to read the candidate and recognize it as mine, not as Claude's voice.
```

---

## When to fire this

After substantive conversations only. Apply the gem heuristic in your own head first:

- Did I learn a new framing? Did a concept I already knew get sharper?
- Did two existing ideas connect in a way I hadn't seen before?
- Was there a useful pattern, distinction, or mental model articulated?

If none of those apply, don't fire the prompt. False extractions are noise.

## When NOT to fire this

- Conversations about coding tasks, drafting help, sanity checks
- Conversations where Claude restated things you already wrote into the conversation
- Conversations under 20 messages — generally too brief to produce real gems
- Conversations where you suspect Claude is being agreeable rather than insightful

## Disposition & Routing

The pasted prompt produces at most one *new-note* candidate - but a conversation can yield knowledge that is vault-worthy yet does NOT belong as a new candidate. After distilling each idea to a one/two-sentence statement, run a vault dedup check (name the closest existing note/MOC), then classify and route it:

| Disposition | Test | Route |
|---|---|---|
| **New** | No existing note covers it; genuinely new framing, mechanism, or connection | The pasted prompt's path - one sharpest candidate to `00_Inbox/AI_Candidates/`, then the cooling period below. |
| **Refinement** | A sharper or extended version of an *existing* concept (otherwise it is "a nicely-worded version of an existing idea") | One-line surgical patch on that concept note: a bullet placed **before** the `**Boundary condition:**` line in `## Mechanism`, and bump `updated`. **Only if `status: final` is NOT set** - for a final note use a `## Cross-Domain Links` entry on its MOC instead. Do not create a candidate. |
| **Already captured** | The insight was written into an artefact *during the same conversation* (a Solution, a Decision) | Exclude - it is already in the vault. |
| **Operational / tooling** | Knowledge about the PKM/vault machinery, not learnable domain knowledge | Route to `CLAUDE.md` / the relevant `SKILL.md`, not to a vault note. |

Rules of thumb:
- **One sharpest, New only.** If several survive as New, promote just the single sharpest; demote the rest to Refinement or Exclude.
- **Precision over recall.** Default to Exclude when unsure - a missed gem can be re-captured; a polluted vault is expensive to clean.
- **Patch safely.** Literal (not regex over special characters), guard that the anchor matches exactly once, keep `**Boundary condition:**` last in Mechanism, never rewrite the whole file.

Operationalized as the `extract-gems` skill: `99_System/Claude/gem-extraction/SKILL.md`.

## What to do with the output

If Claude returns a filled candidate:
1. Copy it into a new file in `00_Inbox/AI_Candidates/`
2. Name the file with a leading date and a short slug: `2026-05-23-embeddings-as-lossy-compression.md`
3. Wait for weekly review. Don't promote immediately, even if it feels right. The cooling period catches over-enthusiasm.

If Claude returns "Nothing rises to vault-worthy" — accept it. Don't argue. Claude reading the conversation cold is a useful second opinion. If you disagree strongly, write the note yourself rather than re-prompting Claude until it gives you the answer you want.
