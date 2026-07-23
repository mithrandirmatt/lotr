#!/usr/bin/env python3
"""Fingerprint tracking for GGUF export.

Similar to build.lora_fingerprint.py, this tracks inputs to the GGUF export process.
If the adapter, base model, and export settings are unchanged, the export step can be skipped.

Inputs tracked:
- Adapter safetensors files (weights)
- Adapter config (architecture)
- Base model HF identifier + version metadata
- Export outtype (q4_k_m, f16, etc.)
- Export script version
"""

import argparse
import hashlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute deterministic GGUF export fingerprint")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--base_model", required=True)
    parser.add_argument("--outtype", default="f16")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _hash_directory(hasher: "hashlib._Hash", path: Path) -> None:
    """Recursively hash all files in a directory efficiently."""
    if not path.exists():
        hasher.update(b"MISSING\n")
        return

    for file_path in sorted(path.rglob("*")):
        if file_path.is_file():
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    adapter_dir = Path(args.adapter_dir).resolve()
    output_path = Path(args.output).resolve()

    if not adapter_dir.exists():
        raise FileNotFoundError(f"Adapter directory not found: {adapter_dir}")

    # Hash the export script itself (detects breaking changes in export logic)
    export_script = repo_root / "build" / "agent" / "build.lora_export_gguf.py"
    if not export_script.exists():
        raise FileNotFoundError(f"Export script not found: {export_script}")

    hasher = hashlib.sha256()

    # Include fixed inputs in hash
    hasher.update(f"BASE_MODEL={args.base_model}\n".encode("utf-8"))
    hasher.update(f"OUTTYPE={args.outtype}\n".encode("utf-8"))

    # Hash adapter directory (all weights and configs)
    hasher.update(b"ADAPTER_DIR:\n")
    _hash_directory(hasher, adapter_dir)

    # Hash export script
    hasher.update(b"EXPORT_SCRIPT:\n")
    with export_script.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(hasher.hexdigest() + "\n", encoding="utf-8")
    print(f"GGUF export fingerprint written to: {output_path}")


if __name__ == "__main__":
    main()
