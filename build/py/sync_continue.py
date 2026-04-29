#!/usr/bin/env python3
"""
sync_continue.py

Reads project reference MD files and regenerates the systemMessage
in ~/.continue/config.yaml so the Continue agent always has up-to-date
project context without needing to call read_file at runtime.

Usage (run from repo root):
    python3 build/py/sync_continue.py
    python3 build/py/sync_continue.py --dry-run
"""

import argparse
import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Inside Docker, ~/.continue is mounted at /host-continue
_docker_continue = Path("/host-continue/config.yaml")
CONTINUE_CONFIG = _docker_continue if _docker_continue.exists() else Path.home() / ".continue" / "config.yaml"

GAME_PLAN_PATH      = REPO_ROOT / "assets/reference/agent/game-plan.md"
TODO_PATH           = REPO_ROOT / "assets/reference/agent/todo.md"
RULES_REF_PATH      = REPO_ROOT / "assets/reference/agent/rules-reference.md"
COPILOT_INSTR_PATH  = REPO_ROOT / ".github/copilot-instructions.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_todo_sections(todo_text: str) -> tuple[str, str, str]:
    """Return (in_progress, todo, done) section text."""
    sections = {"in_progress": "", "todo": "", "done": ""}
    current = None
    lines_by_section: dict[str, list[str]] = {"in_progress": [], "todo": [], "done": []}

    for line in todo_text.splitlines():
        if re.match(r"^## In Progress", line, re.IGNORECASE):
            current = "in_progress"
        elif re.match(r"^## Todo", line, re.IGNORECASE):
            current = "todo"
        elif re.match(r"^## Done", line, re.IGNORECASE):
            current = "done"
        elif current:
            lines_by_section[current].append(line)

    return (
        "\n".join(lines_by_section["in_progress"]).strip(),
        "\n".join(lines_by_section["todo"]).strip(),
        "\n".join(lines_by_section["done"]).strip(),
    )


def extract_phase_table(game_plan_text: str) -> str:
    """Extract the Development Phases table from game-plan.md."""
    in_table = False
    lines = []
    for line in game_plan_text.splitlines():
        if "## Development Phases" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("## ") and "Development Phases" not in line:
                break
            lines.append(line)
    return "\n".join(lines).strip()


def extract_mission(game_plan_text: str) -> str:
    """Extract the Mission Statement paragraph."""
    lines = game_plan_text.splitlines()
    capture = False
    result = []
    for line in lines:
        if "## Mission Statement" in line:
            capture = True
            continue
        if capture:
            if line.startswith("## "):
                break
            result.append(line)
    return "\n".join(result).strip()


_MCP_TOOLS = (
    "read_file, write_file, list_directory, search_files, "
    "git_status, git_log, git_diff, git_add, git_commit, run_command, "
    "memory_set, memory_get, memory_list, memory_delete, "
    "task_list, task_add, task_complete, task_move_to_in_progress, "
    "agent_send, agent_receive, agent_queue_status, "
    "pg_schema, pg_query, pg_execute, "
    "redis_get, redis_set, redis_keys, redis_del, "
    "ollama_generate, card_search, "
    "godot_run, make_target, run_pytest"
)

TOOL_RULE = (
    f"TOOL USE IS MANDATORY. You have MCP tools available: {_MCP_TOOLS}. "
    "When asked to read a file you MUST call read_file. "
    "When asked to edit or write a file you MUST call write_file with the complete new file content. "
    "NEVER say you cannot modify files - use write_file instead. "
    "File paths must be workspace-relative (e.g. build/docker/.bash_aliases). "
    "Use memory_set/memory_get to persist facts across sessions. "
    "Use task_* tools to update todo.md. "
    "Use agent_send/agent_receive to coordinate between agents via the handoff queue."
)


def build_system_message(game_plan: str, todo: str) -> str:
    mission = extract_mission(game_plan)
    phase_table = extract_phase_table(game_plan)
    in_progress, todo_text, _ = extract_todo_sections(todo)

    windows_repo = str(REPO_ROOT).replace("/", "\\")

    in_progress_block = in_progress if in_progress.strip() else "(nothing currently in progress)"
    todo_block = todo_text if todo_text.strip() else "(no pending tasks)"

    msg = f"""You are a repository-aware worker agent for the LotR TCG Digital Game project.

IMPORTANT: The project task list and phase information are provided directly below in this system prompt. You already have this information — do NOT attempt to read todo.md or any other file to answer questions about current tasks or project status. Answer directly from the content below.

## Mission
{mission}

## Development Phases
{phase_table}

## Current Tasks (from todo.md — already loaded, do not re-fetch)

### In Progress
{in_progress_block}

### Next Tasks (Todo)
{todo_block}

## Reference File Paths (use read_file only when asked for details beyond what is above)
- Task tracker:    {windows_repo}\\assets\\reference\\agent\\todo.md
- Game plan:       {windows_repo}\\assets\\reference\\agent\\game-plan.md
- LotR TCG rules:  {windows_repo}\\assets\\reference\\agent\\rules-reference.md
- Godot docs:      {windows_repo}\\assets\\reference\\godot-docs\\
- Guidelines:      {windows_repo}\\.github\\copilot-instructions.md

## Tool Preferences
Use read_file, file_search, grep_search for workspace exploration.
Only use run_terminal_command for build/test/git operations.
Keep changes minimal and style-consistent. Do not refactor unless asked.
Never expose secrets. Ask before destructive operations."""

    return msg


def indent_block(text: str, indent: str = "      ") -> str:
    """Indent a multiline string for embedding in YAML literal block scalar."""
    return "\n".join(indent + line if line.strip() else "" for line in text.splitlines())


def update_config(config_path: Path, system_message: str, dry_run: bool) -> None:
    config_text = config_path.read_text(encoding="utf-8")

    # Strategy 1: existing systemMessage literal block scalar (4-space indent)
    sm_pattern = re.compile(
        r"(    systemMessage: \|\n)((?:(?:      .*|)\n)*)",
        re.MULTILINE,
    )
    indented_sm = indent_block(system_message) + "\n"
    replacement_sm = f"    systemMessage: |\n{indented_sm}"

    # Strategy 2: replace the first item in a top-level rules: list.
    # The first rule holds the system/context message.
    rules_first_pattern = re.compile(
        r"(?m)^(rules:\n)(  -[ \t].*?)(\n  -[ \t]|\n[a-zA-Z])",
        re.DOTALL,
    )
    indented_rules = "\n".join(
        "    " + line if line.strip() else ""
        for line in system_message.splitlines()
    )
    replacement_first_item = f"  - |\n{indented_rules}"

    # Also keep the second rule (tool-list) in sync.
    # It is the first `>-` scalar that mentions "TOOL USE IS MANDATORY".
    tool_rule_pattern = re.compile(
        r"(  - >-\n)((?:    .*\n)*)",
        re.MULTILINE,
    )
    indented_tool = "\n".join("    " + line for line in TOOL_RULE.splitlines()) + "\n"
    replacement_tool_item = f"  - >-\n{indented_tool}"

    if sm_pattern.search(config_text):
        new_config = sm_pattern.sub(lambda _: replacement_sm, config_text)
    elif rules_first_pattern.search(config_text):
        m = rules_first_pattern.search(config_text)
        new_config = (
            config_text[: m.start()]
            + m.group(1)
            + replacement_first_item
            + m.group(3)
            + config_text[m.end() :]
        )
    else:
        print(
            f"[WARNING] sync_continue: could not find 'systemMessage: |' or 'rules:' block"
            f" in {config_path} — skipping (not an error).",
            file=sys.stderr,
        )
        return

    # Update the tool-list rule if present
    if tool_rule_pattern.search(new_config):
        new_config = tool_rule_pattern.sub(replacement_tool_item, new_config, count=1)

    if dry_run:
        print("=== DRY RUN: new systemMessage would be ===")
        print(system_message)
        print("===========================================")
        print("=== DRY RUN: new tool rule would be ===")
        print(TOOL_RULE)
        return

    config_path.write_text(new_config, encoding="utf-8")
    print(f"Updated systemMessage and tool rule in {config_path}")


def main():
    parser = argparse.ArgumentParser(description="Sync Continue agent config from project MD files.")
    parser.add_argument("--dry-run", action="store_true", help="Print result without writing")
    args = parser.parse_args()

    for path in [GAME_PLAN_PATH, TODO_PATH, CONTINUE_CONFIG]:
        if not path.exists():
            print(f"ERROR: required file not found: {path}", file=sys.stderr)
            sys.exit(1)

    game_plan = read_text(GAME_PLAN_PATH)
    todo = read_text(TODO_PATH)

    system_message = build_system_message(game_plan, todo)
    update_config(CONTINUE_CONFIG, system_message, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
