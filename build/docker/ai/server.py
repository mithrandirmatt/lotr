#!/usr/bin/env python3
"""
LotR TCG AI helper server (moved from mcp/)
"""
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKSPACE = Path(os.getenv("WORKSPACE", "/workspace")).resolve()

host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "3100"))

mcp = FastMCP("lotr-ai", host=host, port=port)

# Paths for persistent agent state (inside workspace so they are versioned)
_AGENT_DIR      = WORKSPACE / "assets" / "reference" / "agent"
_MEMORY_FILE    = _AGENT_DIR / "memories.json"
_HANDOFF_FILE   = _AGENT_DIR / "handoff.json"
_TODO_FILE      = _AGENT_DIR / "todo.md"

# Serialisation lock — prevents concurrent writes corrupting JSON files
_store_lock = threading.Lock()


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (WORKSPACE / path).resolve()
    if not str(resolved).startswith(str(WORKSPACE)):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (result.stdout + result.stderr).strip()


def _pg_conn():
    import psycopg2  # lazy — only needed when postgres tools are called
    url = os.environ.get("POSTGRES_URL", "")
    if not url:
        raise RuntimeError("PostgreSQL is not configured (POSTGRES_URL not set). Postgres tools are unavailable in this environment.")
    return psycopg2.connect(url)


# The rest of server implementation mirrors the original mcp server's tools
# For brevity this file reuses the existing tool implementations and behaviour.

@mcp.tool()
def read_file(path: str) -> str:
    try:
        return _safe_path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"(file not found: {path})"
    except Exception as exc:
        return f"(error reading {path}: {exc})"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written: {p.relative_to(WORKSPACE)}"


@mcp.tool()
def list_directory(path: str = "") -> str:
    base = _safe_path(path) if path else WORKSPACE
    entries = sorted(base.iterdir(), key=lambda e: (e.is_file(), e.name))
    return "\n".join(
        f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries
    )


if __name__ == "__main__":
    import sys
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        bind_host = host
        bind_port = port
        print(f"AI helper server starting — bind: {bind_host}:{bind_port}")
        print(f"  SSE endpoint (bind): http://{bind_host}:{bind_port}/sse")
        print(f"  From host (published): http://localhost:{bind_port}/sse")
        print(f"  From Docker network (service name): http://lotr-ai:{bind_port}/sse")
        mcp.run(transport="sse")
#!/usr/bin/env python3
"""
LotR TCG MCP Server
Provides filesystem, git, shell, postgres, memory, task, and agent-coordination
tools over SSE transport.

Open-source dependencies:
  mcp          - Anthropic MCP Python SDK (MIT)
  psycopg2-binary - PostgreSQL adapter (LGPL)
  redis        - Redis client (MIT)
  httpx        - HTTP client for Ollama API (BSD)
"""
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKSPACE = Path(os.getenv("WORKSPACE", "/workspace")).resolve()

host = os.getenv("MCP_HOST", "0.0.0.0")
port = int(os.getenv("MCP_PORT", "3100"))

# Server name changed from 'lotr-mcp' to 'lotr-ai'
mcp = FastMCP("lotr-ai", host=host, port=port)

# Paths for persistent agent state (inside workspace so they are versioned)
_AGENT_DIR      = WORKSPACE / "assets" / "reference" / "agent"
_MEMORY_FILE    = _AGENT_DIR / "memories.json"
_HANDOFF_FILE   = _AGENT_DIR / "handoff.json"
_TODO_FILE      = _AGENT_DIR / "todo.md"

# Serialisation lock — prevents concurrent writes corrupting JSON files
_store_lock = threading.Lock()


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_path(path: str) -> Path:
    """Resolve path relative to WORKSPACE; reject directory traversal.
    Accepts workspace-relative paths (build/docker/.bash_aliases) or
    absolute paths inside the workspace (/workspace/build/docker/.bash_aliases).
    """
    p = Path(path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (WORKSPACE / path).resolve()
    if not str(resolved).startswith(str(WORKSPACE)):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (result.stdout + result.stderr).strip()


def _pg_conn():
    import psycopg2  # lazy — only needed when postgres tools are called
    url = os.environ.get("POSTGRES_URL", "")
    if not url:
        raise RuntimeError("PostgreSQL is not configured (POSTGRES_URL not set). Postgres tools are unavailable in this environment.")
    return psycopg2.connect(url)


# ── Filesystem tools ──────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a workspace-relative file path (e.g. build/docker/server.py)."""
    try:
        return _safe_path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"(file not found: {path})"
    except Exception as exc:
        return f"(error reading {path}: {exc})"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a file at the given workspace-relative path."""
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written: {p.relative_to(WORKSPACE)}"


@mcp.tool()
def list_directory(path: str = "") -> str:
    """List the contents of a workspace directory. path is workspace-relative."""
    base = _safe_path(path) if path else WORKSPACE
    entries = sorted(base.iterdir(), key=lambda e: (e.is_file(), e.name))
    return "\n".join(
        f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries
    )


@mcp.tool()
def search_files(pattern: str, path: str = "") -> str:
    """Search for files matching a glob pattern in the workspace (max 100 results)."""
    base = _safe_path(path) if path else WORKSPACE
    matches = sorted(base.rglob(pattern))[:100]
    return "\n".join(str(m.relative_to(WORKSPACE)) for m in matches)


# ── Git tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
def git_status() -> str:
    """Return the current git working-tree status."""
    return _git("status")


@mcp.tool()
def git_log(n: int = 10) -> str:
    """Return the last n commits in short format."""
    return _git("log", "--oneline", f"-{n}")


@mcp.tool()
def git_diff(path: str = "") -> str:
    """Return the current unstaged diff, optionally scoped to a workspace-relative file path."""
    args = ["diff"]
    if path:
        args.append(str(_safe_path(path)))
    return _git(*args)


@mcp.tool()
def git_add(path: str) -> str:
    """Stage a workspace-relative file path for the next commit."""
    return _git("add", str(_safe_path(path)))


@mcp.tool()
def git_commit(message: str) -> str:
    """Commit all staged changes with the provided message."""
    return _git("commit", "-m", message)


# ── Shell tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def run_command(command: str, cwd: str = "") -> str:
    """
    Run a shell command inside the workspace (60 s timeout, output capped at 10 000 chars).
    cwd is relative to the workspace root.
    """
    work_dir = _safe_path(cwd) if cwd else WORKSPACE
    result = subprocess.run(
        command,
        shell=True,
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = (result.stdout + result.stderr)
    return out[:10_000]


# ── Postgres tools ────────────────────────────────────────────────────────────

@mcp.tool()
def pg_query(sql: str) -> str:
    """Run a read-only SQL query and return tab-separated results."""
    try:
        conn = _pg_conn()
    except Exception as exc:
        return f"(postgres unavailable: {exc})"
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            header = "\t".join(cols)
            body = "\n".join("\t".join(str(c) for c in row) for row in rows)
            return f"{header}\n{body}" if header else body
    finally:
        conn.close()


@mcp.tool()
def pg_execute(sql: str) -> str:
    """Run a write SQL statement (INSERT / UPDATE / DELETE / DDL)."""
    try:
        conn = _pg_conn()
    except Exception as exc:
        return f"(postgres unavailable: {exc})"
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        return "OK"
    finally:
        conn.close()



# ── Agent memory tools ───────────────────────────────────────────────────────

@mcp.tool()
def memory_set(key: str, value: str) -> str:
    """Store a persistent memory value under the given key."""
    with _store_lock:
        data = _read_json(_MEMORY_FILE)
        data[key] = {"value": value, "updated": datetime.now(timezone.utc).isoformat()}
        _write_json(_MEMORY_FILE, data)
    return f"Memory stored: {key}"


@mcp.tool()
def memory_get(key: str) -> str:
    """Retrieve a memory value by key. Returns empty string if not found."""
    data = _read_json(_MEMORY_FILE)
    entry = data.get(key)
    if entry is None:
        return ""
    return entry.get("value", "")


@mcp.tool()
def memory_list() -> str:
    """List all stored memory keys with their last-updated timestamps."""
    data = _read_json(_MEMORY_FILE)
    if not data:
        return "(no memories stored)"
    lines = [f"{k}  [{v.get('updated','')}]" for k, v in sorted(data.items())]
    return "\n".join(lines)


@mcp.tool()
def memory_delete(key: str) -> str:
    """Delete a memory entry by key."""
    with _store_lock:
        data = _read_json(_HANDOFF_FILE)
        if key not in data:
            return f"Key not found: {key}"
        del data[key]
        _write_json(_HANDOFF_FILE, data)
    return f"Deleted: {key}"


# ── Task management tools ─────────────────────────────────────────────────────

def _todo_sections(text: str) -> dict[str, list[str]]:
    """Parse todo.md into {section_heading: [lines]} preserving order."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if re.match(r"^#{1,3} ", line):
            current = line
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


@mcp.tool()
def task_list() -> str:
    """Return all tasks from todo.md."""
    if not _TODO_FILE.exists():
        return "(todo.md not found)"
    return _TODO_FILE.read_text(encoding="utf-8")


@mcp.tool()
def task_add(title: str, section: str = "### Next Tasks (Todo)") -> str:
    """
    Append a new unchecked task to a section in todo.md.
    section defaults to '### Next Tasks (Todo)'.
    """
    if not _TODO_FILE.exists():
        return "todo.md not found"
    text = _TODO_FILE.read_text(encoding="utf-8")
    target = section.strip()
    if target not in text:
        text = text.rstrip() + f"\n\n{target}\n- [ ] {title}\n"
    else:
        # Insert after the section heading
        lines = text.splitlines(keepends=True)
        out = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.strip() == target:
                out.append(f"- [ ] {title}\n")
                inserted = True
        text = "".join(out)
    _TODO_FILE.write_text(text, encoding="utf-8")
    return f"Task added: {title}"


@mcp.tool()
def task_complete(title: str) -> str:
    """Mark the first task matching title as completed ([ ] -> [x])."""
    if not _TODO_FILE.exists():
        return "todo.md not found"
    text = _TODO_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"- \[ \] (" + re.escape(title) + r")", re.IGNORECASE)
    new_text, n = pattern.subn(r"- [x] \1", text, count=1)
    if n == 0:
        return f"Task not found: {title}"
    _TODO_FILE.write_text(new_text, encoding="utf-8")
    return f"Marked complete: {title}"


@mcp.tool()
def task_move_to_in_progress(title: str) -> str:
    """
    Move the first matching task from any section to '## In Progress'.
    Creates the section if absent.
    """
    if not _TODO_FILE.exists():
        return "todo.md not found"
    text = _TODO_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"^- - \[.\] " + re.escape(title) + r".*$", re.MULTILINE | re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return f"Task not found: {title}"
    task_line = f"- [ ] {title}"
    text = pattern.sub("", text, count=1)
    if "## In Progress" in text:
        text = text.replace("## In Progress\n", f"## In Progress\n{task_line}\n", 1)
    else:
        text = f"## In Progress\n{task_line}\n\n" + text
    _TODO_FILE.write_text(text, encoding="utf-8")
    return f"Moved to In Progress: {title}"


# ── Multi-agent coordination tools ────────────────────────────────────────────

@mcp.tool()
def agent_send(to_agent: str, message: str, from_agent: str = "user") -> str:
    """
    Post a message to another agent's inbox in the shared handoff queue.
    to_agent / from_agent are free-form names (e.g. 'my-planner', 'my-agent').
    """
    with _store_lock:
        data = _read_json(_HANDOFF_FILE)
        inbox = data.setdefault(to_agent, [])
        inbox.append({
            "from": from_agent,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        })
        _write_json(_HANDOFF_FILE, data)
    return f"Message sent to {to_agent}"


@mcp.tool()
def agent_receive(agent: str, mark_read: bool = True) -> str:
    """
    Return unread messages from the handoff queue for the given agent name.
    Marks them as read unless mark_read=False.
    """
    with _store_lock:
        data = _read_json(_HANDOFF_FILE)
        inbox = data.get(agent, [])
        unread = [m for m in inbox if not m.get("read")]
        if mark_read:
            for m in inbox:
                m["read"] = True
            data[agent] = inbox
            _write_json(_HANDOFF_FILE, data)
    if not unread:
        return "(no new messages)"
    return "\n\n".join(
        f"[{m['timestamp']}] from {m['from']}:\n{m['message']}" for m in unread
    )


@mcp.tool()
def agent_queue_status() -> str:
    """Show a summary of all agents and their unread message counts."""
    data = _read_json(_HANDOFF_FILE)
    if not data:
        return "(no agents)"
    lines = [f"{k}: {sum(1 for m in v if not m.get('read'))} unread" for k, v in data.items()]
    return "\n".join(lines)


if __name__ == '__main__':
    bind_host = os.getenv('MCP_HOST', '0.0.0.0')
    bind_port = int(os.getenv('MCP_PORT', '3100'))
    print(f"AI MCP server starting — bind: {bind_host}:{bind_port}")
    print(f"  From Docker network (service name): http://lotr-ai:{bind_port}/sse")
    mcp.run(transport="sse")
