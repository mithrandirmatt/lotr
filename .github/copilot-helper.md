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
| Non-trivial request (default start) | `workflow-orchestration-baseline.md` |
| "add a feature", "implement X", "build X" | `workflow-new-feature.md` |
| "create an issue", "track this", "log this" | `workflow-issue-create.md` |
| "test", "verify", "validate", "does it work" | `workflow-task-verification.md` |
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

> **CURRENT (2026-07-28): host Ollama first, llama-server as fallback, no shim/proxy.**
> `build/docker/docker.ps1 run` now checks whether real host Ollama is already up
> and healthy on `http://127.0.0.1:11434` -- if so, it's used directly and is
> **never killed/restarted**. The host-native llama.cpp server
> (`build/docker/setup-llama-server.ps1`, `http://127.0.0.1:8090`) is only
> started (and recovered via stop+restart if it fails to come up healthy) when
> Ollama is NOT already serving. There is no translation shim and no
> think:false/max-tokens proxy in the request path anymore --
> `scripts/llama_ollama_shim.py` and `scripts/ollama_proxy.py` (port 11436) and
> the `lotr-headroom` container (port 8787) are all deprecated/unused by
> `docker.ps1`. `.vscode/settings.json`'s
> `github.copilot.chat.languageModel.ollama.serverUrl` (`http://localhost:11434`)
> now hits real Ollama directly in the common case. If host Ollama isn't
> running and llama-server is serving as the fallback instead, the Ollama BYOM
> provider has nothing to talk to on 11434 (llama-server doesn't implement
> Ollama's native API) -- that's an accepted tradeoff of removing the shim;
> start host Ollama (`ollama serve`, or just launch the Ollama app) if you need
> VS Code integration during a llama-server-fallback session.

### Call Chain Overview (current -- host Ollama preferred, llama-server as fallback, no shim)
```
VS Code Copilot (BYOM, "Ollama" provider, unchanged)
  │  http://localhost:11434
  ▼
ollama (host)              ← used directly when already running; never killed
```
```
(fallback, only when host Ollama is NOT already running/healthy)
build/docker/setup-llama-server.ps1  ← starts/recovers llama-server on 8090
  │  http://127.0.0.1:8090            (OpenAI-compatible surface only;
  ▼                                     NOT reachable via the Ollama BYOM
llama-server (host, llama.cpp, HIP/ROCm)   provider without host Ollama up)
```

### Call Chain Overview (deprecated -- host-native llama.cpp behind an Ollama-API shim, removed 2026-07-28)
```
VS Code Copilot (BYOM, "Ollama" provider, unchanged)
  │  http://localhost:11434
  ▼
scripts/llama_ollama_shim.py (host, translates Ollama API <-> OpenAI-compat API)
  │  http://127.0.0.1:8090
  ▼
llama-server (host, llama.cpp, HIP/ROCm)   ← actual LLM inference
```

### Call Chain Overview (deprecated -- historical reference only)
```
VS Code Copilot (BYOM)
  │  port 11436
  ▼
olllama_proxy.py          ← strips think:false tokens, caps max_tokens   [DEPRECATED]
  │  port 8787
  ▼
headroom container       ← response compression proxy (ghcr.io/chopratejas/headroom)  [DEPRECATED]
  │  port 11434
  ▼
olllama (host)            ← actual LLM inference
  │  port 3100
  ▼
MCP server container     ← lotr-mcp, tools over SSE (separate from chat model path)
```

### Step 1 — VS Code / Copilot Logs
These tell you whether Copilot sent the request at all and what error it received back.
| Log | Location |
|-----|----------|
| Copilot Chat output | VS Code → **Output** panel → dropdown → **GitHub Copilot Chat** |
| Copilot extension log | VS Code → **Output** panel → dropdown → **GitHub Copilot** |
| VS Code general log | `%APPDATA%\Code\logs\` (rotate on restart; look for `exthost` folder) |
| Copilot debug log (session) | `%APPDATA%\Code\User\workspaceStorage\<hash>\GitHub.copilot-chat\debug-logs\` |

**What to look for:** `Response too long`, `timeout`, `ECONNREFUSED`, `fetch failed`, HTTP 4xx/5xx from `http://localhost:11434` (the direct Ollama port -- not the deprecated 11436 proxy port).

Online docs:
- VS Code Output panel: https://code.visualstudio.com/docs/editor/debugging#_debug-console-repl
- Copilot BYOM (Bring Your Own Model): https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-with-an-ide/using-claude-or-other-models-in-copilot

### Step 1b — "Sorry, no response was returned" with a thinking model (common cause, no proxy involved)
Reasoning/"thinking" models (e.g. `qwen3.5`-based tags like
`lotr-agentic-rx7900xtx-agentic-qwen35-262k:latest`) return their chain-of-thought in a
separate `reasoning` field and only put the final answer in `content`. If the request's
`max_tokens` is too small, the model can burn its entire completion budget on `reasoning`
and return `finish_reason:"length"` with an **empty `content` string** -- Copilot then
shows "Sorry, no response was returned." because it only reads `content`.

To confirm, hit Ollama directly with a small vs. large `max_tokens` and compare:
```powershell
# Small budget -> often empty content, finish_reason=length
$body = '{"model":"<model>","messages":[{"role":"user","content":"Say OK"}],"max_tokens":16,"stream":false}'
Invoke-WebRequest -Uri http://localhost:11434/v1/chat/completions -Method Post -Body $body -ContentType 'application/json' -UseBasicParsing | Select -Expand Content

# Larger budget -> content populates, finish_reason=stop
$body = '{"model":"<model>","messages":[{"role":"user","content":"Say OK"}],"max_tokens":800,"stream":false}'
Invoke-WebRequest -Uri http://localhost:11434/v1/chat/completions -Method Post -Body $body -ContentType 'application/json' -UseBasicParsing | Select -Expand Content
```

**Tried and empirically confirmed NOT to work for this model (Ollama 0.32.1, model uses
built-in `RENDERER qwen3.5` / `PARSER qwen3.5`, not a hand-rolled TEMPLATE) -- do not
retry these as "the fix":**
- Appending `/no_think` to the Modelfile `SYSTEM` block -- read back as literal text.
- Appending `/no_think` to the end of the user message -- also read back as literal text.
- Setting `"think": false` in the JSON body of `POST /v1/chat/completions` -- no effect
  at all (byte-identical output with/without it).

**What DOES work:** `"think": false` in the JSON body of the **native**
`POST /api/chat` endpoint (not the OpenAI-compat `/v1/chat/completions`) reliably
disables thinking for this model. The catch: Copilot's ollama BYOM provider calls
`/v1/chat/completions`, so this isn't reachable without a request-rewriting hop --
which is exactly what the deprecated proxy attempted, except it also only rewrote
`/v1/chat/completions` bodies, so it **would have been a no-op for this too** (the
proxy was never actually fixing this, before or after its deprecation).

Realistic remediation options today:
1. Give the model enough `max_tokens`/`num_predict` headroom to finish reasoning AND
   emit an answer (the only lever confirmed to work end-to-end).
2. Check whether a newer Ollama version forwards `think` on the OpenAI-compat endpoint
   (unverified as of Ollama 0.32.1).
3. Use a different model/tag whose template actually honors `/no_think` natively.

Online docs:
- Ollama API reference: https://github.com/ollama/ollama/blob/main/docs/api.md

### Step 2 — [DEPRECATED] Ollama Proxy Log (`ollama_proxy.py`)
> Not part of the current request path. Skip unless the proxy has been intentionally
> reinstated. Kept only for historical/rollback reference.

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

### Step 3 — [DEPRECATED] Headroom Proxy Log
> Not part of the current request path. Kept only for historical/rollback reference.

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

# 6. End-to-end: send a minimal request directly to Ollama (NOT the deprecated 11436 proxy)
Invoke-RestMethod -Uri 'http://localhost:11434/api/tags'
```
If step 3 or 4 fails: `PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run`.
If step 5 fails: Ollama is not running on the host – start it from the tray or `ollama serve`.

> Deprecated: there used to be a step 6/7 here checking port 11436 and restarting
> `Start-OllamaProxy`. That proxy is deprecated -- do not start it or chase port 11436.

---
## Summary
This helper consolidates all decision‑making heuristics, workflow references, and troubleshooting steps so the agent can act quickly and correctly while staying within the project’s rules.
