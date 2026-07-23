import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

from model_config import load_model_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare repository corpus/profile artifacts for agentic model training")
    parser.add_argument("--model", required=True)
    parser.add_argument("--quantization", required=True)
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--reasoning_dataset", default=None)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--model_config", default=None)
    return parser.parse_args()


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def _load_profile(profile_path: Path) -> dict:
    if not profile_path.exists():
        return {
            "name": "default-agentic",
            "description": "Fallback profile",
            "include_globs": ["**/*.md"],
            "exclude_globs": ["**/node_modules/**", "**/.git/**", "**/.venv/**"],
            "gpu": {"name": "generic", "vram_gb": 16},
        }
    with profile_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _collect_files(repo_root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    matches: set[Path] = set()
    skip_dir_names = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".tox",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
    }

    roots: set[Path] = set()
    for pattern in include_globs:
        parts = pattern.replace("\\", "/").split("/")
        static_parts: list[str] = []
        for part in parts:
            if any(ch in part for ch in "*?["):
                break
            static_parts.append(part)
        base = repo_root.joinpath(*static_parts) if static_parts else repo_root
        if base.exists() and base.is_dir():
            roots.add(base)
        elif base.exists() and base.is_file():
            roots.add(base.parent)

    if not roots:
        roots = {repo_root}

    for scan_root in sorted(roots):
        for root, dirs, files in os.walk(scan_root):
            rel_root = Path(root).relative_to(repo_root).as_posix()
            if rel_root == ".":
                rel_root = ""

            dirs[:] = [
                d for d in dirs
                if d not in skip_dir_names and not _matches((f"{rel_root}/{d}" if rel_root else d), exclude_globs)
            ]

            for filename in files:
                rel_path = f"{rel_root}/{filename}" if rel_root else filename
                rel_path = rel_path.replace("\\", "/")
                if _matches(rel_path, exclude_globs):
                    continue
                if _matches(rel_path, include_globs):
                    matches.add(repo_root / rel_path)

    return sorted(matches)


def _format_sample(repo_root: Path, file_path: Path, content: str) -> dict:
    rel = file_path.relative_to(repo_root).as_posix()
    return {
        "path": rel,
        "text": (
            "<instruction>Read repository policy, skills, and implementation patterns for agentic coding.</instruction>\n"
            f"<source>{rel}</source>\n"
            f"<answer>\n{content}\n</answer>"
        ),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _analyze_corpus(rows: list[dict]) -> dict:
    """Analyze corpus for quality and size statistics."""
    if not rows:
        return {
            "total_samples": 0,
            "total_bytes": 0,
            "avg_bytes_per_sample": 0,
            "min_bytes": 0,
            "max_bytes": 0,
            "estimated_tokens": 0,
        }

    byte_counts = []
    total_bytes = 0
    for row in rows:
        text = row.get("text", "")
        byte_count = len(text.encode("utf-8"))
        byte_counts.append(byte_count)
        total_bytes += byte_count

    # Rough token estimation: ~1 token per 4 characters
    estimated_tokens = total_bytes // 4

    stats = {
        "total_samples": len(rows),
        "total_bytes": total_bytes,
        "avg_bytes_per_sample": total_bytes // len(rows) if rows else 0,
        "min_bytes": min(byte_counts) if byte_counts else 0,
        "max_bytes": max(byte_counts) if byte_counts else 0,
        "estimated_tokens": estimated_tokens,
    }

    # Warn about problematic samples
    outliers = [i for i, bc in enumerate(byte_counts) if bc < 100 or bc > 100000]
    if outliers:
        stats["warnings"] = f"Found {len(outliers)} samples with extreme sizes (< 100 bytes or > 100KB)"

    return stats


def main() -> None:
    args = _parse_args()
    repo_root = Path(args.data_dir).resolve()
    profile_path = repo_root / "build" / "agent" / "profiles" / f"{args.profile}.json"
    profile = _load_profile(profile_path)
    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)

    print(f"Preparing training corpus for model={args.model} quantization={args.quantization}")
    print(f"Repository root: {repo_root}")
    print(f"Profile: {profile.get('name', args.profile)}")

    include_globs = profile.get("include_globs", ["**/*.md"])
    exclude_globs = profile.get("exclude_globs", ["**/.git/**", "**/node_modules/**", "**/.venv/**"])
    files = _collect_files(repo_root, include_globs, exclude_globs)
    print(f"Selected {len(files)} files from profile include/exclude rules")

    corpus_rows: list[dict] = []
    extreme_samples = []
    for idx, file_path in enumerate(files, start=1):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            continue
        if not content:
            continue
        content_bytes = len(content.encode("utf-8"))

        # Track extreme samples for review (truncate very large files to prevent tokenization OOM)
        if content_bytes > 100000:
            rel_path = file_path.relative_to(repo_root).as_posix()
            extreme_samples.append({
                "path": rel_path,
                "size_bytes": content_bytes,
                "reason": "too large (> 100KB)",
                "action": "truncated to 80KB"
            })
            # Truncate to 80KB max for large data files
            content = content[:80000]

        corpus_rows.append(_format_sample(repo_root, file_path, content))
        sys.stdout.write(f"\r[Progress: {idx}/{len(files)}] Building corpus...")
        sys.stdout.flush()
    print(f"\nCorpus build complete (processed {len(files)} files).")

    if args.reasoning_dataset:
        reasoning_path = Path(args.reasoning_dataset)
        if reasoning_path.exists() and reasoning_path.is_file():
            try:
                reasoning_content = reasoning_path.read_text(encoding="utf-8").strip()
                if reasoning_content:
                    corpus_rows.append(
                        {
                            "path": reasoning_path.as_posix(),
                            "text": (
                                "<instruction>Practice deep reasoning and explicit planning.</instruction>\n"
                                f"<source>{reasoning_path.as_posix()}</source>\n"
                                f"<answer>\n{reasoning_content}\n</answer>"
                            ),
                        }
                    )
                    print(f"Added reasoning dataset: {reasoning_path}")
            except UnicodeDecodeError:
                print(f"Warning: reasoning dataset is not UTF-8 decodable: {reasoning_path}")

    training_dir = repo_root / "do" / "agent" / "models" / "training"
    corpus_path = training_dir / f"{args.profile}-corpus.jsonl"
    _write_jsonl(corpus_path, corpus_rows)

    # Analyze corpus
    corpus_stats = _analyze_corpus(corpus_rows)
    print(f"\n[INFO] Corpus Analysis:")
    print(f"  Samples: {corpus_stats['total_samples']}")
    print(f"  Total size: {corpus_stats['total_bytes'] / (1024*1024):.1f} MB")
    print(f"  Avg per sample: {corpus_stats['avg_bytes_per_sample']:.0f} bytes")
    print(f"  Size range: {corpus_stats['min_bytes']}-{corpus_stats['max_bytes']} bytes")
    print(f"  Est. tokens: {corpus_stats['estimated_tokens']:,} (@ 4 chars/token)")
    if "warnings" in corpus_stats:
        print(f"  ⚠️  {corpus_stats['warnings']}")

    # Report extreme samples (truncated, not skipped)
    if extreme_samples:
        print(f"\n[INFO] Extreme Samples (truncated to fit in training):")
        for sample in extreme_samples:
            print(f"  • {sample['path']} ({sample['size_bytes']:,} bytes, {sample['reason']})")

    metadata = {
        "model": args.model,
        "quantization": args.quantization,
        "profile": args.profile,
        "profile_path": profile_path.as_posix(),
        "model_config": model_cfg.get("id") if model_cfg else None,
        "model_config_path": model_cfg_path.as_posix() if model_cfg_path else None,
        "samples": len(corpus_rows),
        "gpu": profile.get("gpu", {}),
        "runtime": profile.get("runtime", {}),
        "corpus_stats": corpus_stats,
        "extreme_samples": extreme_samples,
        "extreme_samples_note": "Very large files (> 100KB) truncated to 80KB to prevent tokenization OOM. Most extreme samples should be prevented by profile exclude_globs.",
    }
    metadata_path = training_dir / f"{args.profile}-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    # Write extreme samples report for manual review
    if extreme_samples:
        report_path = training_dir / f"{args.profile}-extreme-samples.txt"
        with report_path.open("w", encoding="utf-8") as f:
            f.write(f"Extreme Samples Report for {args.profile}\n")
            f.write(f"Generated at corpus build time\n")
            f.write(f"Total extreme: {len(extreme_samples)}\n\n")
            f.write("Files truncated to 80KB max for training:\n\n")
            for sample in extreme_samples:
                f.write(f"{sample['path']}\n")
                f.write(f"  Size: {sample['size_bytes']:,} bytes\n")
                f.write(f"  Reason: {sample['reason']}\n")
                f.write(f"  Action: Truncated to 80KB\n\n")
        print(f"\nExtreme samples report written to: {report_path}")

    # Keep downstream targets unblocked until full finetune integration lands.
    model_path = repo_root / "do" / "agent" / "models" / f"lotr-{args.model}-{args.quantization}.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as handle:
        handle.write(b"GGUF\x03\x00\x00\x00")
        handle.write(b"\x00" * 1024 * 1024)

    print(f"Corpus written to: {corpus_path}")
    print(f"Metadata written to: {metadata_path}")
    print(f"Placeholder GGUF written to: {model_path}")


if __name__ == "__main__":
    main()