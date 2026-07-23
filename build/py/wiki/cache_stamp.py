#!/usr/bin/env python3
"""Section-level checksum stamps for wiki build steps.

This utility supports two modes:
- check: return exit code 0 when a section can be skipped.
- update: write/update stamp after successful section completion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _iter_files(paths: list[str]) -> Iterable[Path]:
    for raw in sorted(set(paths)):
        p = Path(raw)
        if not p.exists():
            continue
        if p.is_file():
            yield p
            continue
        for root, _, files in os.walk(p):
            root_path = Path(root)
            for file_name in sorted(files):
                yield root_path / file_name


def _hash_paths(paths: list[str], verbose: bool = False, mode: str = "content") -> str:
    """Hash files/trees as a single digest.

    Modes:
    - content: hash path + full file content (slowest, strongest)
    - stat: hash path + file size + mtime_ns (fast, good for large trees)
    """
    digest = hashlib.sha256()

    # First pass: collect all files (sorted order)
    files_to_hash = []
    for fpath in _iter_files(paths):
        files_to_hash.append(fpath)

    if verbose and files_to_hash:
        action = "hashing" if mode == "content" else "scanning metadata for"
        print(f"  {action} {len(files_to_hash)} files...")

    if mode == "stat":
        # NOTE: directory-level aggregation (e.g. just the top dir's mtime)
        # is intentionally NOT used here even though it would be faster --
        # overwriting an existing file in place (same filename, new content)
        # updates that file's own mtime but does NOT bump its parent
        # directory's mtime on Linux, so a real content change could be
        # silently missed (false cache hit). Instead we keep full per-file
        # granularity but parallelize the stat() syscalls: this workload is
        # I/O-latency bound (especially over WSL2/9p bind mounts where each
        # syscall has real round-trip latency), not CPU bound, so threads
        # (which release the GIL during stat()) give a large wall-clock
        # speedup for large trees without changing the hash algorithm,
        # digest order, or correctness -- existing stamps remain valid.
        stat_results: dict[int, os.stat_result] = {}
        max_workers = min(32, max(4, (os.cpu_count() or 4) * 4))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {
                pool.submit(fpath.stat): idx for idx, fpath in enumerate(files_to_hash)
            }
            done = 0
            for future in as_completed(future_to_idx):
                stat_results[future_to_idx[future]] = future.result()
                done += 1
                if verbose and len(files_to_hash) > 100 and done % 100 == 0:
                    print(f"\r    {done}/{len(files_to_hash)}...", end="", flush=True)

        # Apply results in sorted-path order so the digest stays
        # deterministic regardless of thread completion order.
        for idx, fpath in enumerate(files_to_hash):
            digest.update(f"{fpath.as_posix()}\n".encode("utf-8"))
            stat = stat_results[idx]
            digest.update(f"{stat.st_size}:{stat.st_mtime_ns}\n".encode("utf-8"))
    else:
        for idx, fpath in enumerate(files_to_hash):
            if verbose and len(files_to_hash) > 100 and idx % 100 == 0:
                print(f"\r    {idx}/{len(files_to_hash)}...", end="", flush=True)

            digest.update(f"{fpath.as_posix()}\n".encode("utf-8"))
            with fpath.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)

    if verbose and files_to_hash and len(files_to_hash) > 100:
        print(f"\r    {len(files_to_hash)}/{len(files_to_hash)} done")

    return digest.hexdigest()


def _all_outputs_exist(outputs: list[str]) -> bool:
    return all(Path(path).exists() for path in outputs)


def _load_stamp(stamp_path: Path) -> dict | None:
    if not stamp_path.exists():
        return None
    try:
        with stamp_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def cmd_check(
    stamp: Path,
    inputs: list[str],
    outputs: list[str],
    label: str,
    verbose: bool = False,
    input_mode: str = "content",
    output_mode: str = "content",
    trust_output_stamp: bool = False,
) -> int:
    stamp_data = _load_stamp(stamp)
    if not stamp_data:
        print(f"[cache] {label}: no stamp file")
        return 1

    if not _all_outputs_exist(outputs):
        print(f"[cache] {label}: output missing")
        return 1

    if verbose:
        print(f"  computing input checksum...")
    current_input_checksum = _hash_paths(inputs, verbose=verbose, mode=input_mode)
    current_output_tree_checksum = ""
    if not trust_output_stamp:
        if verbose:
            print(f"  computing output checksum...")
        current_output_tree_checksum = _hash_paths(outputs, verbose=verbose, mode=output_mode)

    stamp_input_checksum = str(stamp_data.get("input_checksum", ""))
    stamp_output_checksum = str(stamp_data.get("output_checksum", ""))
    stamp_output_tree_checksum = str(stamp_data.get("output_tree_checksum", ""))

    if current_input_checksum != stamp_input_checksum:
        print(f"[cache] {label}: input checksum changed")
        return 1

    # Completion marker contract: output_checksum mirrors input_checksum only after success.
    if stamp_output_checksum != stamp_input_checksum:
        print(f"[cache] {label}: previous run incomplete")
        return 1

    if not trust_output_stamp and current_output_tree_checksum != stamp_output_tree_checksum:
        print(f"[cache] {label}: output checksum changed")
        return 1

    print(f"[cache] {label}: cache hit")
    return 0


def cmd_update(
    stamp: Path,
    inputs: list[str],
    outputs: list[str],
    label: str,
    verbose: bool = False,
    input_mode: str = "content",
    output_mode: str = "content",
) -> int:
    if not _all_outputs_exist(outputs):
        print(f"[cache] {label}: cannot stamp, output missing")
        return 1

    if verbose:
        print(f"  computing input checksum...")
    input_checksum = _hash_paths(inputs, verbose=verbose, mode=input_mode)
    if verbose:
        print(f"  computing output checksum...")
    output_tree_checksum = _hash_paths(outputs, verbose=verbose, mode=output_mode)

    stamp.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": label,
        "input_checksum": input_checksum,
        "output_checksum": input_checksum,
        "output_tree_checksum": output_tree_checksum,
        "inputs": inputs,
        "outputs": outputs,
        "input_mode": input_mode,
        "output_mode": output_mode,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with stamp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    print(f"[cache] {label}: stamp updated")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Checksum stamps for wiki build sections")
    parser.add_argument("mode", choices=["check", "update"])
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--input", dest="inputs", action="append", default=[])
    parser.add_argument("--output", dest="outputs", action="append", default=[])
    parser.add_argument("--label", default="section")
    parser.add_argument("--verbose", "-v", action="store_true", help="show hashing progress")
    parser.add_argument("--input-mode", choices=["content", "stat"], default="content")
    parser.add_argument("--output-mode", choices=["content", "stat"], default="content")
    parser.add_argument(
        "--trust-output-stamp",
        action="store_true",
        help="skip output tree hashing during check when stamp/output existence are valid",
    )
    args = parser.parse_args()

    stamp = Path(args.stamp)
    inputs = [os.path.abspath(path) for path in args.inputs]
    outputs = [os.path.abspath(path) for path in args.outputs]

    if args.mode == "check":
        return cmd_check(
            stamp,
            inputs,
            outputs,
            args.label,
            verbose=args.verbose,
            input_mode=args.input_mode,
            output_mode=args.output_mode,
            trust_output_stamp=args.trust_output_stamp,
        )
    return cmd_update(
        stamp,
        inputs,
        outputs,
        args.label,
        verbose=args.verbose,
        input_mode=args.input_mode,
        output_mode=args.output_mode,
    )


if __name__ == "__main__":
    raise SystemExit(main())
