# Project Guidelines

## Tool Preferences

- **Always use built-in tools over shell commands for workspace operations.**
  - Use `file_search` or `grep_search` (custom tools) to find files and content — never `grep`, `find`, `rg`, or `ls` in a terminal.
  - Use `read_file` or `semantic_search` to read and search file content — never `cat`, `head`, or `tail`.
  - Use `run_in_terminal` only for operations that genuinely require a shell (building, running tests, git operations).

- **Prefer `tool_search` to discover available tools** before falling back to terminal equivalents.

## Code Style

- Match existing code style — indentation, naming conventions, comment style — before introducing new patterns.
- Keep changes minimal and focused. Do not refactor, add comments, or add docstrings unless explicitly asked.
- ASCII-only in PowerShell scripts — no curly quotes, em dashes, or non-breaking spaces.

## Safety

- Never expose secrets, credentials, or tokens.
- For destructive operations (delete, overwrite, `--force`) ask before proceeding.
- Shell tool is restricted — only run commands when clearly necessary; explain purpose before running.

## Build & Test

- Build system: `make` (from `build/`); see `build/makefile` and `build/makefiles/`.
- Docker: `build/docker/` scripts manage the `lotr-docker-service` WSL2 distro.
- Python: targets in `build/py/`.

## Agent Conventions

- When working with agents: source profiles are in `.github/agents/*.agent.md`; run `make agent_update` (from `build/`) to regenerate `.github/agents/generated/`.
- Do not edit files in `.github/agents/generated/` directly — they are generated outputs.
