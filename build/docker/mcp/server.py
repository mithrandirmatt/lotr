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

mcp = FastMCP("lotr-mcp", host=host, port=port)

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
        raise RuntimeError("POSTGRES_URL environment variable is not set")
    return psycopg2.connect(url)


# ── Filesystem tools ──────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file in the workspace."""
    return _safe_path(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a file in the workspace."""
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written: {p.relative_to(WORKSPACE)}"


@mcp.tool()
def list_directory(path: str = "") -> str:
    """List the contents of a directory in the workspace."""
    base = _safe_path(path) if path else WORKSPACE
    entries = sorted(base.iterdir(), key=lambda e: (e.is_file(), e.name))
    return "\n".join(
        f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries
    )


@mcp.tool()
def search_files(pattern: str, path: str = "") -> str:
    """Search for files matching a glob pattern (max 100 results)."""
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
    """Return the current unstaged diff, optionally scoped to a file."""
    args = ["diff"]
    if path:
        args.append(str(_safe_path(path)))
    return _git(*args)


@mcp.tool()
def git_add(path: str) -> str:
    """Stage a file for the next commit."""
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
    conn = _pg_conn()
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
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        return "OK"
    finally:
        conn.close()



# ── Agent memory tools ────────────────────────────────────────────────────────

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
        data = _read_json(_MEMORY_FILE)
        if key not in data:
            return f"Key not found: {key}"
        del data[key]
        _write_json(_MEMORY_FILE, data)
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
    pattern = re.compile(r"^- \[.\] " + re.escape(title) + r".*$", re.MULTILINE | re.IGNORECASE)
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
        return "(handoff queue is empty)"
    lines = []
    for agent, messages in sorted(data.items()):
        unread = sum(1 for m in messages if not m.get("read"))
        lines.append(f"{agent}: {unread} unread / {len(messages)} total")
    return "\n".join(lines)


# ── Postgres schema tool ─────────────────────────────────────────────────────

@mcp.tool()
def pg_schema(table: str = "") -> str:
    """
    Return schema information from PostgreSQL.
    If table is given, show columns + types for that table.
    Otherwise list all tables in the public schema.
    """
    conn = _pg_conn()
    try:
        with conn.cursor() as cur:
            if table:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                rows = cur.fetchall()
                if not rows:
                    return f"Table not found or no columns: {table}"
                lines = [f"{'column':<30} {'type':<25} {'nullable':<10} {'default'}",
                         "-" * 80]
                for col, dtype, nullable, default in rows:
                    lines.append(f"{col:<30} {dtype:<25} {nullable:<10} {default or ''}")
                return "\n".join(lines)
            else:
                cur.execute(
                    """
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                    """
                )
                rows = cur.fetchall()
                if not rows:
                    return "(no tables in public schema)"
                return "\n".join(f"{t:<40} {k}" for t, k in rows)
    finally:
        conn.close()


# ── Redis tools ───────────────────────────────────────────────────────────────

def _redis_conn():
    import redis  # lazy import
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(url, decode_responses=True)


@mcp.tool()
def redis_get(key: str) -> str:
    """Get the value of a Redis key. Returns empty string if not found."""
    val = _redis_conn().get(key)
    return val if val is not None else ""


@mcp.tool()
def redis_set(key: str, value: str, ex: int = 0) -> str:
    """
    Set a Redis key to value.
    ex: optional TTL in seconds (0 = no expiry).
    """
    r = _redis_conn()
    if ex > 0:
        r.set(key, value, ex=ex)
    else:
        r.set(key, value)
    return f"Set: {key}"


@mcp.tool()
def redis_keys(pattern: str = "*") -> str:
    """List Redis keys matching a pattern (default: all keys, max 200)."""
    keys = _redis_conn().keys(pattern)
    if not keys:
        return "(no keys found)"
    return "\n".join(sorted(keys)[:200])


@mcp.tool()
def redis_del(key: str) -> str:
    """Delete a Redis key. Returns the number of keys removed."""
    n = _redis_conn().delete(key)
    return f"Deleted {n} key(s): {key}"


# ── Ollama tool ───────────────────────────────────────────────────────────────

@mcp.tool()
def ollama_generate(prompt: str, model: str = "", system: str = "") -> str:
    """
    Send a prompt to a local Ollama instance and return the response text.
    model: Ollama model name (defaults to OLLAMA_MODEL env var or 'qwen3-coder:30b').
    system: optional system message prepended to the conversation.
    """
    import httpx  # lazy import
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    resolved_model = model or os.environ.get("OLLAMA_MODEL", "qwen3-coder:30b")
    payload: dict = {
        "model": resolved_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    try:
        resp = httpx.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except httpx.HTTPError as exc:
        return f"Ollama error: {exc}"


# ── Semantic card search ──────────────────────────────────────────────────────

@mcp.tool()
def card_search(query: str, limit: int = 10) -> str:
    """
    Search cards by natural-language description using Ollama embeddings + pgvector.
    Falls back to a simple full-text ILIKE search when pgvector is unavailable.
    query: natural-language description of the card effect (e.g. 'exert to add twilight').
    limit: max number of results to return.
    """
    import httpx  # lazy import
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    embed_model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    conn = _pg_conn()
    try:
        # Try pgvector semantic search first
        try:
            import httpx as _httpx
            resp = _httpx.post(
                f"{base_url}/api/embeddings",
                json={"model": embed_model, "prompt": query},
                timeout=30,
            )
            resp.raise_for_status()
            embedding = resp.json()["embedding"]
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT title, card_type, culture, game_text
                    FROM cards
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (vec_str, limit),
                )
                rows = cur.fetchall()
                if rows:
                    lines = []
                    for title, card_type, culture, game_text in rows:
                        lines.append(f"**{title}** [{card_type}, {culture}]\n{game_text}")
                    return "\n\n".join(lines)
        except Exception:
            pass  # fall through to ILIKE
        # Fallback: keyword ILIKE search
        terms = [f"%{t}%" for t in query.split()[:6]]
        like_clause = " AND ".join("game_text ILIKE %s" for _ in terms)
        sql = f"""
            SELECT title, card_type, culture, game_text
            FROM cards
            WHERE {like_clause}
            LIMIT %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, terms + [limit])
            rows = cur.fetchall()
        if not rows:
            return "(no cards found)"
        lines = []
        for title, card_type, culture, game_text in rows:
            lines.append(f"**{title}** [{card_type}, {culture}]\n{game_text}")
        return "\n\n".join(lines)
    finally:
        conn.close()


# ── Godot headless runner ─────────────────────────────────────────────────────

@mcp.tool()
def godot_run(scene_or_script: str, args: str = "", timeout: int = 30) -> str:
    """
    Run a Godot scene or GDScript in headless mode and return stdout/stderr.
    scene_or_script: workspace-relative path to a .tscn or .gd file.
    args: additional CLI arguments passed to Godot.
    timeout: max seconds to wait (default 30).
    """
    godot_bin = os.environ.get("GODOT_BIN", "godot")
    target = _safe_path(scene_or_script)
    cmd = [godot_bin, "--headless", "--quit", str(target)]
    if args:
        cmd += args.split()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:10_000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Godot process timed out after {timeout}s"
    except FileNotFoundError:
        return f"Godot binary not found: {godot_bin!r}. Set GODOT_BIN env var."


# ── Build tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def make_target(target: str, cwd: str = "build") -> str:
    """
    Run a make target from the build directory (or a workspace-relative cwd).
    target: the make target name (e.g. 'agent_update', 'wiki').
    cwd: directory containing the makefile, relative to workspace root (default: 'build').
    """
    work_dir = _safe_path(cwd)
    result = subprocess.run(
        ["make", target],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    out = (result.stdout + result.stderr).strip()
    return out[:10_000] if out else "(no output)"


@mcp.tool()
def run_pytest(path: str = "", args: str = "-v") -> str:
    """
    Run pytest in the workspace and return a structured pass/fail summary.
    path: workspace-relative path to test file or directory (default: whole workspace).
    args: additional pytest arguments (default: '-v').
    """
    target = str(_safe_path(path)) if path else str(WORKSPACE)
    cmd = ["python3", "-m", "pytest", target] + args.split()
    result = subprocess.run(
        cmd,
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (result.stdout + result.stderr).strip()
    return out[:10_000] if out else "(no output)"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="sse")
