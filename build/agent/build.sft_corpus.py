import argparse
import json
from pathlib import Path

DEFAULT_DATASETS = [
    "nohurry/Opus-4.6-Reasoning-3000x-filtered",
    "Jackrong/Qwen3.5-reasoning-700x",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and convert ShareGPT-style reasoning-distillation datasets into "
        "chat-message JSONL rows consumable by build.sft_train.py"
    )
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument(
        "--datasets",
        default=",".join(DEFAULT_DATASETS),
        help="Comma-separated list of HuggingFace Hub dataset ids (default: Opus-4.6 reasoning distillation set)",
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--cache_dir", default=None)
    parser.add_argument("--max_samples", type=int, default=None, help="Optional cap on total rows written (for smoke tests)")
    parser.add_argument(
        "--custom_examples",
        default=None,
        help="Path to a repo-authored JSONL file of {'messages': [...]} rows to merge in alongside the "
        "downloaded datasets (default: build/agent/custom_sft_examples.jsonl if present).",
    )
    return parser.parse_args()


def load_custom_examples(path: Path) -> list[dict]:
    """Load repo-authored SFT rows (hand-written behavior demonstrations, e.g. context-
    trimming discipline) so fine-tuning isn't limited to generic downloaded datasets."""
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            messages = item.get("messages")
            if isinstance(messages, list) and len(messages) >= 2:
                rows.append({"messages": messages, "source": item.get("source", "custom:local")})
    return rows


def _extract_messages(example: dict) -> list[dict] | None:
    """Normalize a dataset row into a list of {"role", "content"} chat turns.

    Handles two known schemas:
    - ShareGPT-style: {"conversation": [{"from": "human"|"gpt", "value": "..."}, ...]}
    - Flat instruction/response pairs: {"input"|"instruction"|"prompt": "...", "output"|"response": "..."}
    """
    conversation = example.get("conversation")
    if isinstance(conversation, list) and conversation:
        messages: list[dict] = []
        for turn in conversation:
            if not isinstance(turn, dict):
                continue
            role = turn.get("from") or turn.get("role")
            content = turn.get("value") or turn.get("content")
            if not role or content is None:
                continue
            role = "user" if str(role).lower() in ("human", "user") else "assistant"
            messages.append({"role": role, "content": content})
        if len(messages) >= 2:
            return messages

    prompt = example.get("input") or example.get("instruction") or example.get("prompt")
    response = example.get("output") or example.get("response")
    if prompt and response:
        return [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
    return None


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    dataset_names = [name.strip() for name in args.datasets.split(",") if name.strip()]

    output_path = (
        Path(args.output).resolve()
        if args.output
        else repo_root / "do" / "agent" / "models" / "training" / f"{args.profile}-sft-corpus.jsonl"
    )
    cache_dir = args.cache_dir

    # Imported lazily so --help works without the training venv's heavy deps installed.
    from datasets import load_dataset

    rows: list[dict] = []
    for name in dataset_names:
        print(f"Loading dataset: {name}")
        dataset = load_dataset(name, split="train", cache_dir=cache_dir)
        kept = 0
        for example in dataset:
            messages = _extract_messages(example)
            if messages:
                rows.append({"messages": messages, "source": name})
                kept += 1
        print(f"  kept {kept}/{len(dataset)} rows")

    custom_examples_path = (
        Path(args.custom_examples).resolve()
        if args.custom_examples
        else repo_root / "build" / "agent" / "custom_sft_examples.jsonl"
    )
    custom_rows = load_custom_examples(custom_examples_path)
    if custom_rows:
        print(f"Loading custom examples: {custom_examples_path} ({len(custom_rows)} rows)")

    if not rows and not custom_rows:
        raise RuntimeError("No usable rows extracted from any configured dataset.")

    if args.max_samples is not None:
        # Cap only the downloaded-dataset rows; hand-authored behavior examples are
        # few and high-signal, so always keep all of them regardless of the cap.
        rows = rows[: args.max_samples]

    rows.extend(custom_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(rows)} SFT rows to {output_path}")


if __name__ == "__main__":
    main()
