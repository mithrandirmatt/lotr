# Copilot Decision‑Making Helper

This file contains heuristics and guidance that help the agent decide how to act when a request is ambiguous or not explicitly covered by other rules.

---
## How to Start Any Non‑Trivial Task
1. Read `/memories/repo/todos.md` – know what’s active.
2. Identify the task type and consult the matching workflow in `.github/agent/workflows/`.
3. Check `assets/reference/agent/issues-current.md` – is there an open issue for this?
4. If no issue exists and the task is non‑trivial, create one via `workflow-issue-create.md` first.
5. Update session memory before starting work.

---
## Choosing Where to Run Commands
| Situation | Action |
|-----------|--------|
| Running Python, Node, pip, npm, pytest | Inside dev container |
| Building/testing Godot | Inside dev container |
| Running database migrations | Inside dev container |
| Starting/stopping the container | Host PowerShell (`build/docker/docker.ps1`) |
| Tool not found | Add to `build/docker/Dockerfile`, rebuild, retry |
| Tool not found on host | Do NOT install on host – see above |

---
## Choosing Which Workflow to Use
| Trigger phrase | Workflow |
|----------------|----------|
| "add a feature", "implement X", "build X" | `workflow-new-feature.md` |
| "create an issue", "track this", "log this" | `workflow-issue-create.md` |
| "test", "verify", "validate", "does it work" | `workflow-validation.md` |
| "server", "API", "backend infra", "docker service" | `workflow-server-infrastructure.md` |
| "game logic", "card rules", "game mechanics" | `workflow-generate-game-logic.md` |
| Unclear | Read `.github/agent/workflow.md` and ask if still ambiguous |

---
## Issue Lifecycle
```
Create issue (issues-current.md + issues-tracker.md)
  → Start work (set in‑progress in todos.md, create session memory)
  → Implement (update session memory each step)
  → Verify (user sign‑off or automated test)
  → Complete (move to issues-completed.md, remove from issues-current.md, delete session memory)
```
- Never mark an issue complete without verification.
- If you can’t verify (e.g., needs container runtime), ask the user to sign off.

---
## When You Are Unsure
- **Ambiguous task scope** → Ask one focused clarifying question before proceeding.
- **Multiple valid approaches** → List them briefly (2‑3 bullets) and ask which to use.
- **Destructive action** → Always ask before executing (delete, drop, force‑push, overwrite).
- **Missing context** → Read `assets/reference/agent/issues-current.md` and session memory before asking.

---
## Tech Stack Quick Reference
| Layer | Technology |
|-------|-----------|
| Game client | Godot 4 (GDScript) |
| Backend API | FastAPI (Python) |
| Database | PostgreSQL (via SQLAlchemy + Alembic) |
| Admin panel | React + TypeScript + Vite |
| Currency | Tolkien (1 USD = 1 Tolkien) |
| Auth | JWT (access + refresh tokens) |
| Dev environment | Docker container (`lotr-docker‑service` WSL2 distro) |
| Build system | `make` (from `build/`) |

---
## Common Mistakes to Avoid
- Running `node`, `npm`, `python`, or `pip` on the host instead of in the container.
- Editing generated instruction artifacts directly instead of canonical files under `.github/agent/`.
- Marking an issue complete before it has been verified.
- Creating a new issue number that was previously used (check `issues-tracker.md`).
- Using GitKraken MCP for issue tracking unless explicitly asked.
- Skipping memory updates – always update `todos.md` and session memory as you go.

---
## Troubleshooting the Ollama / Copilot Call Stack
When a Copilot chat message to the local LLM silently fails, returns nothing, or returns a truncated/garbled response, work through the call chain in order.

### Call Chain Overview
```
VS Code Copilot (BYOM)
  │  port 11436
  ▼
olllama_proxy.py          ← strips think:false tokens, caps max_tokens
  │  port 8787
  ▼
headroom container       ← response compression proxy (ghcr.io/chopratejas/headroom)
  │  port 11434
  ▼
olllama (host)            ← actual LLM inference
  │  port 3100
  ▼
MCP server container     ← lotr-mcp, tools over SSE
```

### Step 1 — VS Code / Copilot Logs
These tell you whether Copilot sent the request at all and what error it received back.
| Log | Location |
|-----|----------|
| Copilot Chat output | VS Code → **Output** panel → dropdown → **GitHub Copilot Chat** |
| Copilot extension log | VS Code → **Output** panel → dropdown → **GitHub Copilot** |
| VS Code general log | `%APPDATA%\Code\logs\` (rotate on restart; look for `exthost` folder) |
| Copilot debug log (session) | `%APPDATA%\Code\User\workspaceStorage\<hash>\GitHub.copilot-chat\debug-logs\` |

**What to look for:** `Response too long`, `timeout`, `ECONNREFUSED`, `fetch failed`, HTTP 4xx/5xx from `http://localhost:11436`.

Online docs:
- VS Code Output panel: https://code.visualstudio.com/docs/editor/debugging#_debug-console-repl
- Copilot BYOM (Bring Your Own Model): https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-with-an-ide/using-claude-or-other-models-in-copilot

### Step 2 — Ollama Proxy Log (`ollama_proxy.py`)
The proxy runs on the **host** as a hidden Python process on port **11436**. It prints every request to stdout, but since it is launched with `Start-Process -WindowStyle Hidden` there is no visible window.

```powershell
# Check if the proxy process is running
Get-NetTCPConnection -LocalPort 11436 -State Listen

# Kill and restart it manually with visible output:
Stop-Process -Id (Get-NetTCPConnection -LocalPort 11436).OwningProcess -Force
python scripts/ollama_proxy.py --port 11436 --upstream http://localhost:8787 --max-tokens 4096
```

Script location: `scripts/ollama_proxy.py`.

**What to look for:**
- `POST /api/chat [think:false injected]` – confirms requests are passing through
- Connection refused errors to port 8787 (headroom not running)
- Timeout errors (Ollama inference too slow)

Key tunable: `--max-tokens` (default 4096). If Copilot reports "Response too long", lower this value.

Online docs:
- Ollama API reference: https://github.com/ollama/ollama/blob/main/docs/api.md

### Step 3 — Headroom Proxy Log
Headroom runs as a Docker container named `lotr-headroom` inside `lotr-docker-service` on port **8787**.

```powershell
# View live logs
wsl -d lotr-docker-service -u root -- docker logs -f lotr-headroom

# Check if container is running
wsl -d lotr-docker-service -u root -- docker ps --filter name=lotr-headroom

# Restart headroom
wsl -d lotr-docker-service -u root -- docker rm -f lotr-headroom
```

**What to look for:** HTTP errors, upstream connection failures to Ollama on the WSL gateway IP.

Online docs:
- Headroom GitHub: https://github.com/chopratejas/headroom

### Step 4 — Ollama Logs (Host)
Ollama runs natively on the Windows host (not in WSL). Logs vary by how it was started.

```powershell
# If Ollama is running as a Windows service / tray app, logs go to:
$env:LOCALAPPDATA\Ollama\logs\

# View the most recent server log
Get-Content "$env:LOCALAPPDATA\Ollama\logs\server.log" -Tail 50

# Check Ollama is reachable from WSL (headroom talks to the WSL gateway IP)
wsl -d lotr-docker-service -u root -- curl http://$(ip route show default | awk '/default/ {print $3}'):11434/api/tags
```

**What to look for:** model load errors, out‑of‑VRAM, slow generation (high token latency).

Online docs:
- Ollama troubleshooting: https://github.com/ollama/ollama/blob/main/docs/troubleshooting.md
- Ollama FAQ: https://github.com/ollama/ollama/blob/main/docs/faq.md

### Step 5 — MCP Server Log
The MCP server runs as a Docker container named `lotr-mcp` on port **3100** inside `lotr-docker-service`.

```powershell
# Live logs
wsl -d lotr-docker-service -u root -- docker logs -f lotr-mcp

# Check container status
wsl -d lotr-docker-service -u root -- docker ps --filter name=lotr-mcp
```

Server source: `build/docker/mcp/server.py`.
Port: `3100` (env var `MCP_PORT`). SSE endpoint: `http://lotr-mcp:3100/sse` (inside container network).

**What to look for:** tool call failures, JSON decode errors, filesystem permission errors on `/workspace`.

Online docs:
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP specification: https://spec.modelcontextprotocol.io/

### Step 6 — In‑House Script Logs
All PowerShell scripts write to `build/docker/logs/`. Relevant files:
| File | What it covers |
|------|---------------|
| `build/docker/logs/docker.log` | `docker.ps1` build/run/start – includes headroom and proxy startup messages |
| `build/docker/logs/start-wsl-docker.log` | Docker daemon start inside WSL |
| `build/docker/logs/stop-wsl-docker.log` | Docker daemon stop |
| `build/docker/logs/setup-wsl-docker.log` | Full distro + Docker install (only needed on first setup) |
| `build/docker/logs/setup-headroom.log` | Headroom image pull |
| `build/docker/logs/trouble-shoot.*.log` | Output from `trouble-shoot.ps1` |

```powershell
# Tail the main orchestration log in real time
Get-Content build/docker/logs/docker.log -Wait -Tail 30
```

---
## Quick Diagnostic Checklist
Run these in order when communication with the local LLM is broken:
```powershell
# 1. WSL distro running?
wsl -l -v

# 2. Docker running inside WSL?
wsl -d lotr-docker-service -u root -- docker info 2>&1 | Select-Object -First 5

# 3. MCP container up?
wsl -d lotr-docker-service -u root -- docker ps --filter name=lotr-mcp

# 4. Headroom container up?
wsl -d lotr-docker-service -u root -- docker ps --filter name=lotr-headroom

# 5. Ollama reachable from WSL?
wsl -d lotr-docker-service -u root -- curl -s http://$(ip route show default | awk '/default/ {print $3}'):11434/api/tags | head -c 200

# 6. Proxy listening?
Get-NetTCPConnection -LocalPort 11436 -State Listen -ErrorAction SilentlyContinue

# 7. End-to-end: send a minimal request through the proxy
Invoke-RestMethod -Uri 'http://localhost:11436/api/tags'
```
If step 3 or 4 fails: `PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run`.
If step 5 fails: Ollama is not running on the host – start it from the tray or `ollama serve`.
If step 6 fails: Re‑run `docker.ps1 run` which calls `Start-OllamaProxy` automatically.

---
## Summary
This helper consolidates all decision‑making heuristics, workflow references, and troubleshooting steps so the agent can act quickly and correctly while staying within the project’s rules.
