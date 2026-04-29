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

    # Match the existing systemMessage literal block scalar
    pattern = re.compile(
        r"(    systemMessage: \|\n)((?:(?:      .*|)\n)*)",
        re.MULTILINE
    )

    indented = indent_block(system_message) + "\n"
    replacement = f"    systemMessage: |\n{indented}"

    if pattern.search(config_text):
        new_config = pattern.sub(lambda _: replacement, config_text)
    else:
        print("ERROR: Could not find 'systemMessage: |' block in config.yaml", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("=== DRY RUN: new systemMessage would be ===")
        print(system_message)
        print("===========================================")
        return

    config_path.write_text(new_config, encoding="utf-8")
    print(f"Updated systemMessage in {config_path}")


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
