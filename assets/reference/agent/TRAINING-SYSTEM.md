---
name: lotr-training-system-guide
---
# Agent Training System Guide

This guide explains how to use the agent training and reinforcement system to capture learnings and improve the agent's knowledge over time.

## Overview

The system has three parts:
1. **Trigger prompts** (`[TRAINING]`, `[CORRECTION]`, `[RELEARN]`) that signal the agent to record learnings.
2. **Training corpus** (injected into the agent's context) that teaches the agent about the LotR project, game mechanics, build system, and prior learnings.
3. **Reinforcement files** where learnings are stored and can be reviewed, curated, and eventually folded back into agent training.

## Supported triggers

When you use one of these tags in a message to the agent, it enters a reflection mode:

- **`[TRAINING]`**: Record a positive learning or discovery from a completed task.
- **`[CORRECTION]`**: Record a correction to previous guidance, behavior, or assumptions that were wrong or incomplete.
- **`[RELEARN]`**: Revisit an older learning, validate it, and refresh or replace it if evidence has changed.

### Example usage

```
[TRAINING] The Docker exec command in docker.ps1 normalizes to run -NoDevServices
for one-off agent commands. This prevents the main app services from restarting.
```

```
[CORRECTION] I said to read files AFTER edits to verify intent, but actually we should
read files BEFORE edits to establish a baseline, then read AFTER to confirm changes.
```

```
[RELEARN] Let me reconsider the Godot build process. Is it still accurate that we
don't need to rebuild when only scripts change?
```

## Workflow

### Step 1: Use a trigger in your prompt
Provide context and the trigger tag when you want to record a learning.

### Step 2: Agent proposes an entry
The agent, using the guidance from the injected training corpus, will propose a structured learning entry with:
- Concise learning statement
- Category (LotR-specific or generic)
- Evidence reference (file, task, error)
- Why it's reusable
- Suggested destination file

### Step 3: Review and approve
You can accept, refine, or reject the proposed entry.

### Step 4: Record the entry
Use the helper script to record the entry:
```bash
python3 scripts/record_learning.py \
    --trigger TRAINING \
    --category lotr \
    --learning "Docker exec commands normalize to run -NoDevServices for one-offs" \
    --evidence "build/docker/docker.ps1 wrapper logic" \
    --reusable "Helps predict container behavior in agent scripts"
```

Or manually append the formatted entry to the appropriate reinforcement file (see [trigger-workflow.md](trigger-workflow.md)).

## Reinforcement files

Learnings are stored in two places:

- **`assets/reference/agent/reinforcement-lotr.md`** — Project-specific learnings about:
  - Game rules and mechanics
  - Build and Docker workflows
  - LotR TCG engine implementation details
  - Repository structure and conventions

- **`assets/reference/agent/reinforcement-generic.md`** — Broadly applicable learnings about:
  - Debugging techniques
  - Planning and refactoring patterns
  - Tool usage habits
  - Testing and verification practices

## Review and maintain

The corpus should stay lean and high-signal. Periodically:

1. **Review new entries** for duplicates or unclear phrasing.
2. **Consolidate repeated ideas** into single canonical lessons.
3. **Archive stale material** if it's no longer true or useful.
4. **Consider promoting** high-confidence generic learnings into the next round of agent training.

See [training-maintenance.md](training-maintenance.md) for detailed curation guidelines.

## Quick reference

| File | Purpose |
|------|---------|
| [project-overview.md](project-overview.md) | High-level project mission, tech stack, directories, and boundaries. |
| [training-triggers.md](training-triggers.md) | Explicit trigger definitions and capture rules. |
| [training-maintenance.md](training-maintenance.md) | Curation guidelines, quality bar, and review process. |
| [trigger-workflow.md](trigger-workflow.md) | Detailed workflow for how triggers are processed and entries captured. |
| [reinforcement-lotr.md](reinforcement-lotr.md) | Living log of LotR-specific learnings. |
| [reinforcement-generic.md](reinforcement-generic.md) | Living log of broadly applicable learnings. |
| [scripts/record_learning.py](../../scripts/record_learning.py) | Helper tool to record structured entries with validation. |

## Expected behavior

When you ask the agent "what are your supported triggers?", it should respond with:
```
- [TRAINING]: Record a new high-signal learning that should be preserved for future tasks.
- [CORRECTION]: Record a correction to previous guidance, behavior, or assumptions that was wrong or incomplete.
- [RELEARN]: Revisit an older learning, validate it again, and refresh or replace it if the newer evidence changes the conclusion.
```

This confirms the training corpus has been injected correctly.

## Next steps

1. Try using a trigger in a message to the agent.
2. Review the agent's proposed entry.
3. Use `scripts/record_learning.py` to record it.
4. After a few weeks, review the reinforcement files for duplicates and quality.
5. Use [training-maintenance.md](training-maintenance.md) to optimize the corpus.

---

**Questions?** See [training-triggers.md](training-triggers.md) for capture rules or [trigger-workflow.md](trigger-workflow.md) for the step-by-step flow.
