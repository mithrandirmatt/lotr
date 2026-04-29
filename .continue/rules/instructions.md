---
description: Project-wide guidelines for this repository
alwaysApply: true
---

## Tool Preferences

- Use built-in search/read tools to find files and content — never `grep`, `find`, `rg`, `ls`, `cat`, `head`, or `tail`.
- Use the terminal only for operations that genuinely require a shell (building, running tests, git operations).

## Code Style

- Match existing code style — indentation, naming conventions, comment style — before introducing new patterns.
- Keep changes minimal and focused. Do not refactor, add comments, or add docstrings unless explicitly asked.
- ASCII-only in PowerShell scripts — no curly quotes, em dashes, or non-breaking spaces.

## Safety

- Never expose secrets, credentials, or tokens.
- For destructive operations (delete, overwrite, `--force`) ask before proceeding.
- Only run shell commands when clearly necessary; explain purpose before running.

## Build & Test

- Build system: `make` (from `build/`); see `build/makefile` and `build/makefiles/`.
- Docker: `build/docker/` scripts manage the `lotr-docker-service` WSL2 distro.
- Python: targets in `build/py/`.

## Agent Conventions

- Agent source profiles are in `.github/agents/*.agent.md`; run `make agent_update` (from `build/`) to regenerate `.github/agents/generated/`.
- Do not edit files in `.github/agents/generated/` directly — they are generated outputs.