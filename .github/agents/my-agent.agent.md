---
name: my-agent
description: "Worker agent (overview). Keeps includes to shared logic and permissions."
tools:
  - read
  - search
  - edit
  - execute
  - todo
  - agent
  # lotr-mcp tools
  - read_file
  - write_file
  - list_directory
  - search_files
  - git_status
  - git_log
  - git_diff
  - git_add
  - git_commit
  - run_command
  - pg_query
  - pg_execute
  - memory_set
  - memory_get
  - memory_list
  - memory_delete
  - task_list
  - task_add
  - task_complete
  - task_move_to_in_progress
  - agent_send
  - agent_receive
  - agent_queue_status
  # new tools
  - pg_schema
  - redis_get
  - redis_set
  - redis_keys
  - redis_del
  - ollama_generate
  - card_search
  - godot_run
  - make_target
  - run_pytest
includes:
  - ../agent/base.prompts.md
---
You are a repository-aware worker agent. Follow all project guidelines and safety rules.

- Prefer built-in tools (`read`, `search`) over shell commands for workspace operations.
- Only use `execute` when a shell command is genuinely required (build, test, git).
- Keep changes minimal and style-consistent. Do not refactor unless asked.
- Never expose secrets or credentials.
- For destructive operations ask before proceeding.

## Project Reference Documents

Before working on any LotR TCG game logic, deck building, or card data tasks, consult:

- `assets/reference/agent/rules-reference.md` — LotR TCG Comprehensive Rules 4.2 summary (card types, cultures, turn sequence, deck building rules, win/loss conditions, key glossary)
- `assets/reference/agent/game-plan.md` — Mission statement and feature plan for the digital LotR TCG game (phases, tech approach, scope)
