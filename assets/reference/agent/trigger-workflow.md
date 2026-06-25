---
name: lotr-trigger-workflow
---
# Trigger Workflow for Agent Learning Capture

## How triggers work

When you use `[TRAINING]`, `[CORRECTION]`, or `[RELEARN]` in a message to the agent, the agent recognizes these markers and enters a reflection mode based on the guidance in `training-triggers.md` and `training-maintenance.md`.

The agent is injected with knowledge of:
- What each trigger means (see `training-triggers.md`)
- How to categorize learnings (LotR-specific vs. generic)
- Quality standards for what gets recorded (see `training-maintenance.md`)

## Workflow by trigger type

### [TRAINING]
1. User describes a positive learning or discovery from a completed task.
2. Agent reads the description and the relevant context.
3. Agent proposes a learning entry with:
   - Concise learning statement (1-2 sentences)
   - Category (LotR-specific or generic)
   - Evidence link (file, task, or error that triggered the learning)
   - Why it's reusable
   - Destination file
4. User approves or refines the entry.
5. Entry is appended to either `reinforcement-lotr.md` or `reinforcement-generic.md`.

### [CORRECTION]
1. User identifies a mistake, misconception, or stale guidance the agent made or followed.
2. Agent captures:
   - What the error was
   - What the correct understanding is
   - Why the prior understanding was wrong
   - Whether it should replace, refine, or deprecate older guidance
3. Entry is appended with a note marking it as a correction or addendum to prior learning.

### [RELEARN]
1. User asks the agent to revisit an older learning and validate or refresh it.
2. Agent:
   - Locates the relevant entry in the reinforcement files
   - Re-evaluates it based on current evidence or changed circumstances
   - Proposes a refreshed understanding or deprecation
   - Records the updated conclusion with a date marker
3. Entry is updated or a new dated addendum is added.

## Captured entry format

When the agent proposes a learning entry, it will include:
```
**Trigger:** [TRAINING|CORRECTION|RELEARN]
**Learning:** [concise statement]
**Category:** [LotR-specific|generic]
**Evidence:** [file, error, task, or issue reference]
**Why reusable:** [how this helps in future work]
**Destination:** [reinforcement-lotr.md|reinforcement-generic.md]
**Status:** [new|correction to X|refresh of X]
```

## How to record an entry

1. User provides a trigger and context.
2. Agent proposes the entry in the structured format above.
3. User says "OK" or "record" or provides refinements.
4. Agent or user appends the entry to the destination file.

Optionally, the system can provide a helper tool or script to automate the append step.

## Note on deduplication

After recording entries, periodically run the maintenance workflow (see `training-maintenance.md`) to:
- Merge duplicate learnings
- Consolidate repeated ideas
- Archive stale material
- Keep the corpus lean and reusable
