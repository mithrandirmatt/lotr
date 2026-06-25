---
name: lotr-training-triggers
---
# Supported Training Triggers

These are the only explicit user triggers that should start a reflection or reinforcement capture pass.
When the agent is asked what triggers it supports, it should answer with a name:description list.

## Triggers
- `[TRAINING]`: Record a new high-signal learning that should be preserved for future tasks.
- `[CORRECTION]`: Record a correction to previous guidance, behavior, or assumptions that was wrong or incomplete.
- `[RELEARN]`: Revisit an older learning, validate it again, and refresh or replace it if the newer evidence changes the conclusion.

## Capture rules
- The trigger must be explicit in the user request.
- Do not auto-log every task.
- Only capture a lesson if it is actionable, evidence-backed, and likely to help again later.
- If the task only restates existing knowledge, do not duplicate it.
- If a learning is project-specific, place it in the LotR reinforcement file.
- If a learning is generally applicable, place it in the generic reinforcement file.

## Minimum capture fields
- Trigger used.
- Short learning statement.
- Category: LotR-specific or generic.
- Evidence or source task.
- Why it matters.
- Destination file.

## Response contract
If the user asks, "what are your supported triggers?", respond with a compact list in the form:
- name: description

Do not add extra commentary unless the user asks for more detail.
