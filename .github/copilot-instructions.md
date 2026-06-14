# Project Guidelines

## Agent Role

The assistant in this repository is a **coding agent**. It is expected to:

1. Read and edit files directly using the provided tools (`apply_patch`, `create_file`).
2. Verify edits immediately after applying them.
3. Follow all rules defined in `.github/agent/rules.md` and the guidelines below.
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
> **Docker Container Command Execution**
> Always run commands inside the Docker container using `docker.ps1`.
> For agent one-off commands, prefer `exec` so the command runs in the main dev container without restarting services:
> ```powershell
> ./build/docker/docker.ps1 exec "cd /workspace && <command>"
> ```
> To open an interactive dev-container shell:
> ```powershell
> ./build/docker/docker.ps1 run
> ```
> To run a command while also starting the normal workspace services:
> ```powershell
> ./build/docker/docker.ps1 run -CommandArg "cd /workspace && <command>"
> ```
> Example: Check container logs from the dev container
> ```powershell
> ./build/docker/docker.ps1 exec "docker logs lotr-server"
> ```
> ⚠️ Verify the container is running first using `docker ps`
## Tool Preferences

| Preference | What to do |
|------------|-----------|
| **Workspace tools first** | Prefer native read/search/edit tools before using shell commands. |
| Search and read | Use runtime-provided search/read tools; avoid shell text search when equivalent tools exist. |
| Terminal use | Use terminal only when a shell is genuinely required (build, test, git, runtime commands). |

If tool names differ across runtimes, use the closest equivalent capability.

## Code Style

- Match existing code style: indentation, naming conventions, comment style.
- Keep changes minimal and focused. Do not refactor, add comments, or add docstrings unless explicitly asked.
- ASCII‑only in PowerShell scripts – no curly quotes, em dashes, or non‑breaking spaces.

## Recipe Updates

- When the user asks to modify an existing recipe, treat the requested content as the new default behavior.
- Do not add alternate options, opt-in flags, or parallel recipes unless the user explicitly asks for them.

## Verify Code Changes

1. **Always read back any file you have edited** immediately after the edit to confirm the result matches intent.
2. For partial edits (inserting into or appending to an existing file), read the surrounding context to confirm existing content was not removed or corrupted.
3. If the post‑edit read reveals unintended changes, fix them before responding.

## Safety

- Never expose secrets, credentials, or tokens.
- For destructive operations (`delete`, `overwrite`, `--force`) always ask before proceeding.
- Only run shell commands when clearly necessary; explain purpose before running.

## Build & Test

| Tool | Path |
|------|------|
| Make system | `make` (from `build/`); see `build/makefile` and `build/makefiles/`. |
| Docker | `build/docker/` scripts manage the `lotr-docker-service` WSL2 distro. |
| Python | Targets in `build/py/`. |

## Dev Container Workflow (CRITICAL)

- **All development work MUST run inside the dev container** – Python, Node.js, Godot, database commands, tests.
- Never run development commands on the host machine.
- Never probe the host with `node --version`, `npm --version`, `python --version`, etc. The host is not the dev environment.
- Agent default command form: `./build/docker/docker.ps1 exec "cd /workspace && <command>"`

> **If a tool is missing when running a command inside the container:**
> 1. Add it to `build/docker/Dockerfile`.
> 2. Rebuild via `build/docker/docker.ps1`.
> 3. Re‑run the command inside the container.

> Exception: PowerShell scripts that start/stop services (`build/docker/docker.ps1`, etc.) run on the host.

## Runtime Compatibility

- Never print raw tool call payloads in chat output.
- Use workspace-relative paths unless a runtime explicitly requires absolute paths.
- If a required tool is unavailable, report it briefly and continue with the safest supported fallback.
- If instructions conflict, apply precedence from `.github/agent/rules.md`.

## Copilot Tooling Contract

Agents trained for this repository must conform to Copilot-style tool usage.

### Expected Capability Classes
- Workspace discovery: file/path listing and search tools.
- File reads: direct file-read tools with explicit ranges when required.
- File edits: patch/create/update tools for deterministic edits.
- Diagnostics: problem/error collection tools.
- Execution: terminal/task tools for build, test, git, and runtime commands.
- Memory/context: memory tools for repository/session notes when available.

### Required Behavior
- Prefer workspace tools over shell commands for file discovery and reads.
- Apply minimal edits and verify edited files after changes.
- Run verification commands for non-trivial changes when feasible.
- Explain tool limitations directly; do not fabricate unavailable capabilities.
- Do not emit tool-call JSON/XML/code in normal chat replies.

### Interop Guidance
- Tool names may differ across runtimes; map by capability, not exact identifier.
- Keep command execution in the dev container for development operations.
- Use host PowerShell only for container lifecycle scripts in `build/docker/`.

## Build Troubleshooting

- **Environment**: All commands must run inside the WSL2 Docker container (`lotr-docker-service`).
- **Automation**: `make` recipes and automation scripts are designed for this environment.
- **Reference**: See [Docker Integration Specification](build/docker/docker-spec.md) for management details.

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
- Read `/memories/repo/todos.md` if present.
- Read `/memories/repo/architecture-decisions.md` when touching server, models, or API code and if present.

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

- Agent workflow and rule files live under `.github/agent/`.
- If generated agent profiles are added in future, treat generated outputs as read-only.