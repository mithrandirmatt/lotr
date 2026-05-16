---
name: my-agent
description: "Worker agent (overview). Keeps includes to shared logic and permissions."

tools:
  - vscode/getProjectSetupInfo
  - vscode/installExtension
  - vscode/memory
  - vscode/newWorkspace
  - vscode/resolveMemoryFileUri
  - vscode/runCommand
  - vscode/vscodeAPI
  - vscode/extensions
  - vscode/askQuestions
  - execute/runNotebookCell
  - execute/getTerminalOutput
  - execute/killTerminal
  - execute/sendToTerminal
  - execute/runTask
  - execute/createAndRunTask
  - execute/runInTerminal
  - read/getNotebookSummary
  - read/problems
  - read/readFile
  - read/viewImage
  - read/terminalSelection
  - read/terminalLastCommand
  - read/getTaskOutput
  - agent/runSubagent
  - edit/createDirectory
  - edit/createFile
  - edit/createJupyterNotebook
  - edit/editFiles
  - edit/editNotebook
  - edit/rename
  - search/changes
  - search/codebase
  - search/fileSearch
  - search/listDirectory
  - search/textSearch
  - search/usages
  - web/fetch
  - web/githubRepo
  - web/githubTextSearch
  - browser/openBrowserPage
  - browser/readPage
  - browser/screenshotPage
  - browser/navigatePage
  - browser/clickElement
  - browser/dragElement
  - browser/hoverElement
  - browser/typeInPage
  - browser/runPlaywrightCode
  - browser/handleDialog
  - lotr-mcp/agent_queue_status
  - lotr-mcp/agent_receive
  - lotr-mcp/agent_send
  - lotr-mcp/git_add
  - lotr-mcp/git_commit
  - lotr-mcp/git_diff
  - lotr-mcp/git_log
  - lotr-mcp/git_status
  - lotr-mcp/list_directory
  - lotr-mcp/memory_delete
  - lotr-mcp/memory_get
  - lotr-mcp/memory_list
  - lotr-mcp/memory_set
  - lotr-mcp/pg_execute
  - lotr-mcp/pg_query
  - lotr-mcp/read_file
  - lotr-mcp/run_command
  - lotr-mcp/search_files
  - lotr-mcp/task_add
  - lotr-mcp/task_complete
  - lotr-mcp/task_list
  - lotr-mcp/task_move_to_in_progress
  - lotr-mcp/write_file
  - pylance-mcp-server/pylanceDocString
  - pylance-mcp-server/pylanceDocuments
  - pylance-mcp-server/pylanceFileSyntaxErrors
  - pylance-mcp-server/pylanceImports
  - pylance-mcp-server/pylanceInstalledTopLevelModules
  - pylance-mcp-server/pylanceInvokeRefactoring
  - pylance-mcp-server/pylancePythonEnvironments
  - pylance-mcp-server/pylanceRunCodeSnippet
  - pylance-mcp-server/pylanceSettings
  - pylance-mcp-server/pylanceSyntaxErrors
  - pylance-mcp-server/pylanceUpdatePythonEnvironment
  - pylance-mcp-server/pylanceWorkspaceRoots
  - pylance-mcp-server/pylanceWorkspaceUserFiles
  - gitkraken/git_status
  - vscode.mermaid-chat-features/renderMermaidDiagram
  - ms-azuretools.vscode-azureresourcegroups/azureActivityLog
  - ms-azuretools.vscode-containers/containerToolsConfig
  - ms-python.python/getPythonEnvironmentInfo
  - ms-python.python/getPythonExecutableCommand
  - ms-python.python/installPythonPackage
  - ms-python.python/configurePythonEnvironment
  - todo
includes:
  - ../agent/base.prompts.md
  - ../agent/local-wrapper/prompts.md
---
You are a repository-aware worker agent. Follow all project guidelines and safety rules.

- Prefer built-in tools (`read`, `search`) over shell commands for workspace operations.
- Only use `execute` when a shell command is genuinely required (build, test, git).
- Keep changes minimal and style-consistent. Do not refactor unless asked.
- Never expose secrets or credentials.
- For destructive operations ask before proceeding.

- Tool invocation policy: When converting a user request into workspace actions, immediately call the appropriate built-in read/search/edit tools (for example `read/readFile`, `search/fileSearch`, `edit/createFile`) instead of emitting pseudo-function JSON objects as your final reply. If built-in tools are unavailable, fall back to the MCP equivalents (for example `lotr_mcp_read_file`, `lotr_mcp_write_file`) and explicitly log the fallback. After the tool returns, provide a concise summary and any next steps.

## Workflow Reference

When trying to decide how to approach a task, consult the workflow document in .github/agent/workflow.md for guidance on best practices, expected inputs and outputs, and general process for different types of work.

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

## Docker Containers:
- Main Dev Container: Located at build/docker.
  - This container will contain all neccessary tools to build and run the game.
- Server Container: Located at server/.
  - This container will contain all neccessary tools to host the server for the game.
-

