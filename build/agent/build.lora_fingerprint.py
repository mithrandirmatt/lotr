import argparse
import hashlib
from pathlib import Path

from model_config import load_model_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute deterministic LoRA input fingerprint")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--model_config", default=None)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--hf_base_model", default="")
    parser.add_argument("--allow_cpu", default="0")
    parser.add_argument("--torch_variant", default="auto")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _update_file_hash(hasher: "hashlib._Hash", path: Path) -> None:
    """Hash file path and content efficiently without per-file metadata."""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)



def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    corpus_path = Path(args.corpus).resolve()
    output_path = Path(args.output).resolve()

    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)
    _ = model_cfg

    profile_path = repo_root / "build" / "agent" / "profiles" / f"{args.profile}.json"
    requirements_path = repo_root / "build" / "agent" / "requirements-lora.txt"
    finetune_path = repo_root / "build" / "agent" / "build.finetune.py"

    files = [profile_path, corpus_path, requirements_path, finetune_path]
    if model_cfg_path:
        files.append(model_cfg_path)

    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(f"Missing fingerprint input file: {file_path}")

    hasher = hashlib.sha256()
    hasher.update(f"PROFILE={args.profile}\n".encode("utf-8"))
    hasher.update(f"MODEL_CONFIG={args.model_config or ''}\n".encode("utf-8"))
    hasher.update(f"HF_BASE_MODEL={args.hf_base_model or ''}\n".encode("utf-8"))
    hasher.update(f"ALLOW_CPU={args.allow_cpu}\n".encode("utf-8"))
    hasher.update(f"TORCH_VARIANT={args.torch_variant}\n".encode("utf-8"))

    for file_path in files:
        _update_file_hash(hasher, file_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(hasher.hexdigest() + "\n", encoding="utf-8")
    print(f"LoRA fingerprint written to: {output_path}")


if __name__ == "__main__":
    main()