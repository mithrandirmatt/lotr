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

## Godot Development (Local)

The repository includes a Godot 4 project in `gotdot/`. Use these conventions when performing Godot-related tasks:

- **Project path**: `gotdot/` — runable via the engine with `--path gotdot`.
- **Scene flow**: startup.tscn → menu.tscn → main.tscn (game scene). Use `gotdot/scenes/`.
- **Make targets**: `build/makefiles/godot.mk` provides `godot_run` (headless smoke-test), `godot_play` (open a window) and `godot_export` (export release).
- **Docker / WSLg**: The dev container is started with `PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run`. This run target will mount the WSLg X11 socket and PulseAudio runtime when available so GUI and audio work inside the container. Inside the container use `make godot_play` to open the editor/game window.
- **Headless CI**: Use `make godot_run` for automated tests or CI where no display is present.
- **Graphics**: We force `--rendering-driver opengl3` for `godot_play` to avoid unreliable Vulkan initialisation in container/WSLg environments.
- **Assets**: Processed card images live under `build/do/assets/cards/processed/` (generated, gitignored). Sync them to the Godot project with `make wiki_game_asset_creation` — this copies PNGs to `gotdot/assets/cards/` and copies database JSON into `gotdot/assets/data/`.

When asked to run, test, or export the Godot project, prefer the `make` targets and the `docker.ps1` wrappers so runs are reproducible on other machines.
