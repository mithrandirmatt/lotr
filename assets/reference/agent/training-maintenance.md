---
name: lotr-training-maintenance
---
# Training Maintenance Guide

## Purpose
Keep the reinforcement corpus useful over time by removing repetition, consolidating repeated lessons, and preserving only unique, reusable learning.

## Review cadence
- Run a short post-task reflection whenever the user uses `[TRAINING]`, `[CORRECTION]`, or `[RELEARN]`.
- Review the corpus periodically when the user requests a cleanup or when entries start to overlap.
- Prefer small, frequent curation passes over large unreviewed dumps of notes.

## What belongs in training
Record a lesson only if it is:
- Specific enough to be reused.
- Backed by the task, file, or error that exposed it.
- Different from existing entries in meaning, not just phrasing.
- Useful for a future LotR task or a future generic agent task.

## What does not belong in training
Do not record entries that are:
- One-off fixes with no general reuse value.
- Duplicate wording of an existing lesson.
- Unsourced guesses or speculation.
- Raw task logs without a lesson attached.
- Temporary state that will soon be outdated.

## Optimization workflow
1. Read the new candidate entry.
2. Compare it to existing entries in the same bucket.
3. Merge duplicates into one canonical lesson.
4. Rewrite repeated ideas into a stronger, shorter statement.
5. Move corrected guidance into the appropriate bucket.
6. Archive stale material if it is no longer true.

## Bucket rules
- Put project-specific game, build, server, Docker, ML, or repo-structure lessons into `reinforcement-lotr.md`.
- Put tool-usage, debugging, planning, or workflow lessons that apply broadly into `reinforcement-generic.md`.
- If a lesson seems generic but was discovered in LotR work, store the lesson in the generic file and mention the LotR context in the evidence field.

## Post-reflection directives
After task completion, the agent should:
- Decide whether the task produced a new learning.
- Decide whether the learning corrects an older rule or adds a new one.
- Decide whether the entry is unique or should be merged with an existing note.
- Keep the final note short, direct, and evidence-backed.

## Quality bar
A good entry should answer:
- What did we learn?
- Why is it reusable?
- What evidence supports it?
- Where should it live?
- Does it replace or refine an older note?
