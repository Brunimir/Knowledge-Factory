# Annex 3 — Pattern Generator
# Folder: 40_Solutions
#
# WHEN TO USE
# A Pattern is created when 3–5 concept notes from your vault
# cluster around a shared real-world problem. It synthesises
# their mechanisms into a reusable playbook.
#
# Minimum threshold: 3 concept notes from the same or adjacent MOCs.
# Trigger: you notice yourself applying the same combination of
# concepts repeatedly to solve a recurring problem.
#
# HOW TO GENERATE
# Feed this template + 3–5 concept notes to Claude with the prompt:
#
#   "Use these concept notes from my vault to generate a Pattern
#    following the Annex 3 template. The problem I am trying to solve
#    is: [describe it in one sentence]."
#
# Claude will populate each section using the mechanisms from your
# concept notes, not from general knowledge.

════════════════════════════════════════════════════════════════
PATTERN TEMPLATE
════════════════════════════════════════════════════════════════

---
title: {Pattern Title — action-oriented, e.g. "The Deep Work Cycle"}
icon: {single emoji}
type: pattern
status: draft
context:
  - {situation 1 where this pattern applies}
  - {situation 2}
problem: {One sentence: what recurring problem does this solve?}
ingredients:
  - [[Concept Note 1]]
  - [[Concept Note 2]]
  - [[Concept Note 3]]
tags:
  - pattern
  - status/draft
---

## Pattern Essence
{One sentence capturing the core logic of how the ingredients combine.}
Example format: "Start with X to bypass Y, then use Z to produce W."

## Structure

Choose 2–3 of the following modules based on the pattern's nature.
Delete the modules you don't use.

### The Sequence (Workflow)
Step-by-step logic. Use when the pattern is a process.

1. {Step 1 — what you do and why (which concept drives it)}
2. {Step 2}
3. {Step 3}

### The Dos and Don'ts (Guardrails)
Use when the pattern has critical failure modes.

| Do | Don't |
|---|---|
| {High-leverage behaviour} | {Common trap} |
| {High-leverage behaviour} | {Common trap} |

### Force Multipliers
Small tweaks that increase the yield of this pattern.

- {Multiplier 1 — linked to mechanism from a concept note}
- {Multiplier 2}

### Success Indicators
How do you know the pattern is working?

- {Observable signal 1}
- {Observable signal 2}

### Anti-Patterns
When does applying this pattern make things worse?

- {Anti-pattern 1 — the boundary condition of this playbook}
- {Anti-pattern 2}

## Links
- Ingredients: {[[Concept Note 1]], [[Concept Note 2]], [[Concept Note 3]]}
- MoC: {[[MOC_relevant]]}
- Related patterns: [[]]
- Source [[]]

## Ideas
- Ideas Generated: [[]]

════════════════════════════════════════════════════════════════
EXAMPLE PATTERN (for reference — delete before using)
════════════════════════════════════════════════════════════════

---
title: The Deep Work Cycle
icon: 🔁
type: pattern
status: draft
context:
  - Acquiring new complex skills
  - Preparing for high-stakes presentations
  - Master-level career pivots
problem: Learning plateaus and the illusion of competence — thinking
  you know something because you just read it.
ingredients:
  - [[Neural Oscillation]]
  - [[Chunking]]
  - [[Active Recall]]
  - [[Spaced Repetition]]
  - [[Sleep and Learning]]
tags:
  - pattern
  - status/draft
---

## Pattern Essence
Alternate deliberate focused sessions with enforced diffuse breaks,
test retention through active recall before sleep, and use spaced
repetition to lock chunks into long-term memory.

## Structure

### The Sequence (Workflow)
1. **Focus block (25–50 min):** Enter focused mode on a single chunk.
   Close all notifications. Target the Goldilocks difficulty level.
2. **Diffuse break (10–20 min):** Stop completely. Walk, do dishes —
   no phone. Let the brain enter diffuse mode to consolidate.
3. **Active recall audit:** Before returning to new material, write
   the core idea from memory. Do not look at notes first.
4. **Pre-sleep review:** Review the day's hardest chunk immediately
   before sleep. The brain rehearses it during sleep consolidation.
5. **Spaced repetition:** Add the chunk to your Anki deck. Review at
   increasing intervals — do not re-read the note instead.

### Anti-Patterns
- Staying in focused mode when stuck — the Einstellung effect
  (blocked by old thinking). Forced diffuse breaks break the block.
- Using re-reading as a substitute for active recall — this creates
  the illusion of competence without the neural trace.
- Skipping sleep to fit in more study — sleep deprivation degrades
  every other step in this pattern.

## Links
- Ingredients: [[Neural Oscillation]], [[Chunking]], [[Active Recall]],
  [[Spaced Repetition]], [[Sleep and Learning]]
- MoC: [[MOC_Learning and Memory]]
- Related patterns: [[]]
- Source [[Learning.md]]
