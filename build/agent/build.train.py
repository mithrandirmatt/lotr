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
    for idx, file_path in enumerate(files, start=1):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            continue
        if not content:
            continue
        corpus_rows.append(_format_sample(repo_root, file_path, content))
        sys.stdout.write(f"\r[Progress: {idx}/{len(files)}] Building corpus...")
        sys.stdout.flush()
    print("\nCorpus build complete.")

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
    }
    metadata_path = training_dir / f"{args.profile}-metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

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