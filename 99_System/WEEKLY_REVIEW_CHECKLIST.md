# Weekly Review · AI Candidates

Addition to the existing Sunday review process. Runs after `pkm-ingestion`, `pkm-flashcards`, and `pkm-review`, before closing out the week.

Estimated time: 10-20 minutes depending on candidate count.

> **Note:** `pkm-ingestion` does **not** process this folder (excluded via the `.aiignore` marker). Candidates require manual judgement; the agent should never auto-promote them into the canonical vault.

## The review steps

### 1. Open the folder

Browse `00_Inbox/AI_Candidates/` in Obsidian. Skip `_templates/` and `_archive/`. Count the candidates from the last week.

If there are zero, skip the rest. A zero-candidate week is fine — most weeks won't produce gems.

If there are more than five, something's off. Either you're firing the extract prompt too liberally, or the gem heuristic isn't filtering hard enough. Note this for the next week and tighten the heuristic.

### 2. Process each candidate

For each file, open it and decide one of three exits:

**Promote** — the idea survives. The candidate becomes a final note in the canonical vault.

- Read the candidate. Read it again. Ignore the wording; evaluate the idea.
- If the idea holds up: rewrite the candidate in your own words as a Concept Note (or Pattern, or Decision — whichever the suggested_type indicates), in the canonical folder.
- The rewrite is the work. Do not copy-paste. Rewriting is what makes the knowledge yours.
- Add wikilinks to existing related notes. Update the relevant MOC if needed.
- Fill in the Review notes section of the candidate with the decision and target location.
- Move the candidate to `_archive/`.

**Merge** — the idea is real but doesn't deserve a new note. It belongs inside an existing one.

- Identify which existing note absorbs the candidate's content.
- Edit that note: add the new framing, refinement, or connection. Use your own words.
- Fill in the candidate's Review notes with the merge target.
- Move the candidate to `_archive/`.

**Discard** — the idea didn't survive review.

- Common reasons: synthesis of things you already knew, restatement of an existing concept, too vague to be useful, Claude was being agreeable rather than insightful.
- Fill in the Review notes with the reason for discard (briefly — one sentence).
- Move to `_archive/`.

### 3. Stale candidate sweep

Look for any candidate older than two weeks that hasn't been processed.

Stale candidates are noise. Either make a decision now (one of the three exits above) or move directly to `_archive/` with a "stale, never reviewed" note in the Review section.

The two-week rule exists because the cost of accumulated noise outweighs the value of indefinite indecision. If you can't decide in two weeks, the candidate probably wasn't a gem anyway.

### 4. Reflect on the week's extraction rate

After processing, look at the promote/merge/discard ratio:

- **Mostly promotes** — good. The gem heuristic is working.
- **Mostly merges** — the extract prompt is finding refinements rather than new concepts. Not a problem, but worth noticing.
- **Mostly discards** — the gem heuristic isn't filtering enough. Either tighten the heuristic, or apply it more honestly before firing the extract prompt.

A discard-heavy week is a signal, not a failure. The system is working as designed when low-quality candidates get rejected. But a pattern of high discard rates over multiple weeks means the upstream filter (the gem heuristic) needs adjustment.

## Integration with existing skills

This review step happens manually for now. If it stabilizes into a clear pattern over a few months, consider whether the stale-candidate sweep or the promote/merge mechanics could be partially automated via a new skill (e.g., `pkm-candidates`). Don't automate prematurely — the judgement work is the point.

## Anti-patterns to avoid

- **Rubber-stamping candidates.** If you find yourself promoting most candidates without significant rewriting, the buffer isn't doing its job. The rewriting is the value.
- **Skipping the review for a week or two.** The folder accumulates, the cognitive load of the review grows, you skip the next week too, and within a month the candidate folder is a graveyard. Better to do a brief review every week than a thorough one occasionally.
- **Treating the candidate as the final note.** Candidates are drafts. Final notes earn their place through your rewriting, not through Claude's drafting.
- **Letting `pkm-ingestion` process candidates.** Verify the `.aiignore` marker is being respected by the skill. If candidates start disappearing from this folder between Sunday runs without going through review, the exclusion isn't working.
