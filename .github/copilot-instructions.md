# Project Guidelines

## Agent Role

The assistant in this repository is a **coding agent**. It is expected to:

1. Read and edit files directly using the provided tools (`apply_patch`, `create_file`).
2. Verify edits immediately after applying them.
3. Follow all rules defined in `.github/agent/rules.md` and the guidelines above.
4. Avoid asking the user to write or modify files manually unless a choice must be made.

This rule is placed near the top so it is visible before any other instructions are processed.

> Additional decision‑making guidance: see `.github/copilot-helper.md`

## Iterating and Troubleshooting

- **Never hand back until you have verified the fix works.**
  Run the command in a terminal and confirm success output before responding.
- If you cannot run it (e.g., requires an interactive container session the user controls), say so explicitly and provide exact verification steps for the user to run – not a guess.
- **Fix → verify → fix again if it fails.** Repeat until the terminal shows a clean success.
- Do not describe what “should” work. Only claim it works if you have seen passing output.
- If blocked after 3 attempts with the same approach, stop and explain the root cause clearly rather than making a fourth guess.

## Tool Preferences

| Preference | What to do |
|------------|-----------|
| **Built‑in tools** | Use over shell commands for workspace operations. |
| `file_search` / `grep_search` | Find files & content – never use `grep`, `find`, `rg`, or `ls`. |
| `read_file` / `semantic_search` | Read file content – never use `cat`, `head`, or `tail`. |
| `run_in_terminal` | Only when a shell is genuinely required (build, test, git). |

> Prefer `tool_search` to discover available tools before falling back to terminal equivalents.

## Code Style

- Match existing code style: indentation, naming conventions, comment style.
- Keep changes minimal and focused. Do not refactor, add comments, or add docstrings unless explicitly asked.
- ASCII‑only in PowerShell scripts – no curly quotes, em dashes, or non‑breaking spaces.

## Verify Code Changes

1. **Always read back any file you have edited** immediately after the edit to confirm the result matches intent.
2. For partial edits (inserting into or appending to an existing file), read the surrounding context to confirm existing content was not removed or corrupted.
3. If the post‑edit read reveals unintended changes, fix them before responding.

## Safety

- Never expose secrets, credentials, or tokens.
- For destructive operations (`delete`, `overwrite`, `--force`) always ask before proceeding.
- Shell tool is restricted – only run commands when clearly necessary; explain purpose before running.

## Build & Test

| Tool | Path |
|------|------|
| Make system | `make` (from `build/`); see `build/makefile` and `build/makefiles/`. |
| Docker | `build/docker/` scripts manage the `lotr‑docker‑service` WSL2 distro. |
| Python | Targets in `build/py/`. |

## Dev Container Workflow (CRITICAL)

- **All development work MUST run inside the dev container** – Python, Node.js, Godot, database commands, tests.
- Never run development commands on the host machine.
- Never probe the host with `node --version`, `npm --version`, `python --version`, etc. The host is not the dev environment.

> **If a tool is missing when running a command inside the container:**
> 1. Add it to `build/docker/Dockerfile`.
> 2. Rebuild via `build/docker/docker.ps1`.
> 3. Re‑run the command inside the container.

> Exception: PowerShell scripts that start/stop services (`build/docker/docker.ps1`, etc.) run on the host.

## Workflows

Consult the appropriate workflow file before starting any non‑trivial task:

| Task type | Workflow file |
|-----------|--------------|
| New feature | `.github/agent/workflows/workflow-new-feature.md` |
| Issue creation | `.github/agent/workflows/workflow-issue-create.md` |
| Validation/testing | `.github/agent/workflows/workflow-validation.md` |
| Server infrastructure | `.github/agent/workflows/workflow-server-infrastructure.md` |
| Game logic | `.github/agent/workflows/workflow-generate-game-logic.md` |

> General workflow guidance: `.github/agent/workflow.md`

## Issue Tracking

The project uses **local markdown files** – not GitHub Issues or GitKraken MCP.

| File | Purpose |
|------|---------|
| `assets/reference/agent/issues-current.md` | Active + queued issues |
| `assets/reference/agent/issues-completed.md` | Completed issues archive |
| `assets/reference/agent/issues-tracker.md` | Full issue tracking data |

- Always use these files as the source of truth.
- Follow `workflow‑issue-create.md` when creating a new issue.
- Follow `workflow-new-feature.md` when implementing a feature issue.
- GitKraken MCP tools are secondary – only use when explicitly requested.

## Memory Usage

Read memory at the start of every conversation. Update it as work progresses.

### On every conversation start
- Read `/memories/repo/todos.md` – current active issue and recent completed work.
- Read `/memories/repo/architecture-decisions.md` – if touching server, models, or API code.

### When starting work on an issue
- Update `/memories/repo/todos.md`: set status to `in-progress`.
- Create `/memories/session/current-work.md` with: issue ID, goal, files being changed, next steps.

### During work
- Update `/memories/session/current-work.md` as steps complete.

### When completing an issue
- Update `/memories/repo/todos.md`: set status to `completed`, list key files changed.
- Move the issue entry from `assets/reference/agent/issues-current.md` to `assets/reference/agent/issues-completed.md`.
- Delete `/memories/session/current-work.md`.

### When shelving an issue
- Keep session memory intact; note the shelf reason in `/memories/session/current-work.md`.

## Agent Conventions

- Agent source profiles: `.github/agents/*.agent.md`
- Run `make agent_update` (from `build/`) to regenerate `.github/agents/generated/`.
- Never edit files in `.github/agents/generated/` directly – they are generated outputs.