#!/usr/bin/env python3
"""
gen_agents.py

Flatten .github/agents/*.agent.md files into .github/agents/generated/.

For each source agent profile that declares an `includes:` list in its YAML
frontmatter, this script reads each listed file, deep-merges the YAML content
into the source profile, then writes the self-contained result to the
generated/ directory.  Profiles without `includes:` are copied verbatim.

Usage (run from the repo root):
    python3 build/py/gen_agents.py
    python3 build/py/gen_agents.py --dry-run
"""

import argparse
import copy
import os
import re
import sys

# ---------------------------------------------------------------------------
# Optional yaml import — if PyYAML is not installed, fall back to simple copy
# ---------------------------------------------------------------------------
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


AGENTS_DIR   = ".github/agents"
GENERATED_DIR = os.path.join(AGENTS_DIR, "generated")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def parse_frontmatter(text):
    """Return (dict, body_str) or (None, full_text) if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m or not HAS_YAML:
        return None, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, text
    body = text[m.end():]
    return data, body


def render_frontmatter(data, body):
    """Reconstruct the file with YAML frontmatter + body."""
    fm = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{fm}---\n{body}"


def deep_merge(base, override):
    """Recursively merge override into base (modifies base in-place)."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            deep_merge(base[key], val)
        elif key in base and isinstance(base[key], list) and isinstance(val, list):
            # Extend lists, avoiding duplicates
            for item in val:
                if item not in base[key]:
                    base[key].append(item)
        else:
            base[key] = val
    return base


def resolve_includes(data, source_path):
    """
    Pop the `includes:` list from data, load each file relative to the
    source file's directory, and merge their content into data.
    Returns the merged data dict.
    """
    includes = data.pop("includes", None)
    if not includes:
        return data

    source_dir = os.path.dirname(os.path.abspath(source_path))
    merged = copy.deepcopy(data)

    for rel_path in includes:
        abs_path = os.path.normpath(os.path.join(source_dir, rel_path))
        if not os.path.isfile(abs_path):
            print(f"  [WARNING] included file not found: {abs_path}", file=sys.stderr)
            continue
        with open(abs_path, encoding="utf-8") as fh:
            content = fh.read()
        inc_data, _ = parse_frontmatter(content)
        if inc_data:
            deep_merge(merged, inc_data)

    return merged


def process_agent(source_path, generated_path, dry_run=False):
    """Flatten one agent file and write to generated_path."""
    with open(source_path, encoding="utf-8") as fh:
        text = fh.read()

    data, body = parse_frontmatter(text)

    if data is None:
        # No frontmatter or yaml unavailable — copy verbatim
        result = text
    else:
        data = resolve_includes(data, source_path)
        result = render_frontmatter(data, body)

    if dry_run:
        print(f"  [DRY-RUN] would write {generated_path}")
        return

    os.makedirs(os.path.dirname(generated_path), exist_ok=True)
    with open(generated_path, "w", encoding="utf-8") as fh:
        fh.write(result)
    print(f"  wrote {generated_path}")


def main():
    parser = argparse.ArgumentParser(description="Flatten agent profiles into generated/")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done without writing files")
    args = parser.parse_args()

    if not HAS_YAML:
        print("[WARNING] PyYAML not installed — agent files will be copied verbatim (includes not resolved)")

    agent_files = [
        f for f in os.listdir(AGENTS_DIR)
        if f.endswith(".agent.md") and os.path.isfile(os.path.join(AGENTS_DIR, f))
    ]

    if not agent_files:
        print(f"No *.agent.md files found in {AGENTS_DIR}")
        return

    for filename in sorted(agent_files):
        source_path    = os.path.join(AGENTS_DIR, filename)
        generated_path = os.path.join(GENERATED_DIR, filename)
        print(f"Processing {source_path} ...")
        process_agent(source_path, generated_path, dry_run=args.dry_run)

    print("Done.")


if __name__ == "__main__":
    main()
