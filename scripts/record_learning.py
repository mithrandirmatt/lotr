#!/usr/bin/env python3
"""
record_learning.py — Record an agent learning to the training corpus.

Usage:
    python3 record_learning.py --trigger [TRAINING|CORRECTION|RELEARN] \
        --category [lotr|generic] \
        --learning "Learning statement (1-2 sentences)" \
        --evidence "file path or task reference" \
        --reusable "Why this helps in future work" \
        [--status "new|correction to X|refresh of X"]

Examples:
    python3 record_learning.py --trigger TRAINING --category lotr \
        --learning "Docker exec commands normalize to run -NoDevServices" \
        --evidence "build/docker/docker.ps1 line ~50" \
        --reusable "Helps predict container behavior in agent scripts"

    python3 record_learning.py --trigger CORRECTION --category generic \
        --learning "Always read files AFTER edits to verify intent, not before" \
        --evidence "Recent task where edit was corrupted undetected" \
        --reusable "Prevents silent data loss in file operations" \
        --status "correction to 'verify code changes' rule"
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path


def validate_args(args) -> tuple[bool, str]:
    """Validate command-line arguments."""
    valid_triggers = {'TRAINING', 'CORRECTION', 'RELEARN'}
    valid_categories = {'lotr', 'generic'}

    if args.trigger not in valid_triggers:
        return False, f"Invalid trigger: {args.trigger}. Must be one of {valid_triggers}."
    if args.category not in valid_categories:
        return False, f"Invalid category: {args.category}. Must be 'lotr' or 'generic'."
    if not args.learning or len(args.learning) < 10:
        return False, "Learning statement must be at least 10 characters."
    if not args.evidence or len(args.evidence) < 5:
        return False, "Evidence reference must be at least 5 characters."
    if not args.reusable or len(args.reusable) < 10:
        return False, "Reusable explanation must be at least 10 characters."
    return True, ""


def find_reinforcement_file(category: str) -> Path:
    """Return the path to the appropriate reinforcement file."""
    if category == 'lotr':
        return Path('assets/reference/agent/reinforcement-lotr.md')
    else:
        return Path('assets/reference/agent/reinforcement-generic.md')


def check_duplicate(file_path: Path, learning: str) -> bool:
    """Check if a similar learning already exists in the file."""
    if not file_path.exists():
        return False
    content = file_path.read_text(encoding='utf-8')
    # Simple check: if the first 20 words of the learning appear in the file, consider it a duplicate
    key_phrase = ' '.join(learning.split()[:20])
    return key_phrase.lower() in content.lower()


def format_entry(args) -> str:
    """Format the learning entry."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    lines = [
        f"- **Date:** {date_str}",
        f"- **Trigger:** {args.trigger}",
        f"- **Learning:** {args.learning}",
        f"- **Evidence:** {args.evidence}",
        f"- **Why reusable:** {args.reusable}",
    ]
    if args.status:
        lines.append(f"- **Status:** {args.status}")
    return '\n'.join(lines)


def record_learning(args) -> bool:
    """Record the learning to the appropriate file."""
    valid, error_msg = validate_args(args)
    if not valid:
        print(f"Error: {error_msg}", file=sys.stderr)
        return False

    file_path = find_reinforcement_file(args.category)

    if not file_path.exists():
        print(f"Error: Reinforcement file not found: {file_path}", file=sys.stderr)
        print(f"  Expected location: {file_path.resolve()}", file=sys.stderr)
        return False

    if check_duplicate(file_path, args.learning):
        print("Warning: A similar learning may already exist in this file.", file=sys.stderr)
        print("  Please review the file before recording to avoid duplicates.", file=sys.stderr)
        response = input("  Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            return False

    entry = format_entry(args)

    # Append entry to file with a separator
    try:
        with file_path.open('a', encoding='utf-8') as f:
            f.write('\n\n')
            f.write(entry)
            f.write('\n')
        print(f"✓ Learning recorded to {file_path}")
        print(f"\nEntry:\n{entry}")
        return True
    except Exception as e:
        print(f"Error writing to {file_path}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Record an agent learning to the training corpus."
    )
    parser.add_argument(
        '--trigger',
        required=True,
        help="Trigger type: TRAINING, CORRECTION, or RELEARN"
    )
    parser.add_argument(
        '--category',
        required=True,
        help="Category: lotr (project-specific) or generic (broadly applicable)"
    )
    parser.add_argument(
        '--learning',
        required=True,
        help="Concise learning statement (1-2 sentences)"
    )
    parser.add_argument(
        '--evidence',
        required=True,
        help="Evidence reference (file path, task, error, etc.)"
    )
    parser.add_argument(
        '--reusable',
        required=True,
        help="Explanation of why this is reusable or generally useful"
    )
    parser.add_argument(
        '--status',
        default=None,
        help="Optional status (e.g., 'correction to X' or 'refresh of X')"
    )

    args = parser.parse_args()
    success = record_learning(args)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
