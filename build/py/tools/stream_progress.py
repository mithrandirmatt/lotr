#!/usr/bin/env python3
"""Line-passthrough filter that adds periodic progress heartbeats.

Some build steps (notably Godot's `--export-release`, which prints one
`savepack: step N: Storing File: ...` line per packed file without ever
incrementing N) stream plenty of real output but give no numeric sense of
progress -- watching thousands of "step 101" lines scroll by looks
indistinguishable from a hang. This filter sits between such a command and
the terminal: every input line is echoed unchanged (so the full log is still
captured), and every time --match-pattern occurs (or every --every-seconds,
whichever comes first) a "[progress] N matched lines (elapsed Xs)" line is
printed to stderr so it doesn't get mixed into a redirected log file.

Usage:
    some_noisy_command | python3 stream_progress.py --match "Storing File:"

Exit code always mirrors whether stdin was read successfully (0); this tool
never affects the exit status of the piped command -- callers must capture
that separately (e.g. by writing $? to a file before the pipe).
"""

from __future__ import annotations

import argparse
import re
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--match",
        required=True,
        help="Regex; lines matching this increment the progress counter.",
    )
    parser.add_argument(
        "--every-count",
        type=int,
        default=100,
        help="Print a heartbeat after this many matched lines (default: 100).",
    )
    parser.add_argument(
        "--every-seconds",
        type=float,
        default=5.0,
        help="Also print a heartbeat if this many seconds pass since the last one (default: 5).",
    )
    parser.add_argument(
        "--label",
        default="lines processed",
        help="Trailing description used in the heartbeat message (default: 'lines processed').",
    )
    args = parser.parse_args()

    pattern = re.compile(args.match)
    start = time.monotonic()
    last_heartbeat = start
    count = 0

    for raw_line in sys.stdin:
        sys.stdout.write(raw_line)
        sys.stdout.flush()

        if pattern.search(raw_line):
            count += 1
            now = time.monotonic()
            due_by_count = count % args.every_count == 0
            due_by_time = (now - last_heartbeat) >= args.every_seconds
            if due_by_count or due_by_time:
                elapsed = now - start
                print(
                    f"[progress] {count} {args.label} (elapsed {elapsed:.0f}s)",
                    file=sys.stderr,
                    flush=True,
                )
                last_heartbeat = now

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
