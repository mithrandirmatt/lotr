import argparse
import json
import os
from pathlib import Path

# Text-only LoRA training does not require torchvision. Disabling it avoids
# optional vision import paths that can fail on mismatched torchvision ops.
os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a LoRA adapter from repository corpus")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--epochs", type=float, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--grad_accum", type=int, default=None)
    parser.add_argument("--learning_rate", type=float, default=None)
    parser.add_argument("--warmup_ratio", type=float, default=None)
    parser.add_argument("--max_seq_length", type=int, default=None)
    parser.add_argument(
        "--allow_cpu",
        action="store_true",
        help="Allow CPU fallback training. This is slow and can OOM on 7B+ models.",
    )
    return parser.parse_args()


def load_profile(repo_root: Path, profile_name: str) -> dict:
    path = repo_root / "build" / "agent" / "profiles" / f"{profile_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing profile: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_corpus(corpus_path: Path) -> Dataset:
    rows: list[dict] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            text = item.get("text", "").strip()
            if text:
                rows.append({"text": text})
    if not rows:
        raise RuntimeError(f"No training samples found in corpus: {corpus_path}")
    return Dataset.from_list(rows)


def resolve_training_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    # torch ROCm builds report is_available() False when the DXG context isn't yet
    # open; try hipGetDeviceCount via ctypes as a secondary check.
    try:
        import ctypes
        hip = ctypes.CDLL("libamdhip64.so.6", use_errno=True)
        hip.hipGetDeviceCount.restype = ctypes.c_int
        hip.hipGetDeviceCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
        n = ctypes.c_int(0)
        if hip.hipGetDeviceCount(ctypes.byref(n)) == 0 and n.value > 0:
            return "cuda"  # pytorch ROCm exposes as 'cuda'
    except OSError:
        pass
    return "cpu"


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    profile = load_profile(repo_root, args.profile)
    lora_cfg = profile.get("lora", {})

    corpus_path = (
        Path(args.corpus).resolve()
        if args.corpus
        else repo_root / "do" / "agent" / "models" / "training" / f"{args.profile}-corpus.jsonl"
    )
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else repo_root / "do" / "agent" / "models" / "lora" / args.profile
    )

    epochs = args.epochs if args.epochs is not None else float(lora_cfg.get("epochs", 1))
    batch_size = args.batch_size if args.batch_size is not None else int(lora_cfg.get("batch_size", 1))
    grad_accum = args.grad_accum if args.grad_accum is not None else int(lora_cfg.get("grad_accum", 8))
    learning_rate = args.learning_rate if args.learning_rate is not None else float(lora_cfg.get("learning_rate", 1e-4))
    warmup_ratio = args.warmup_ratio if args.warmup_ratio is not None else float(lora_cfg.get("warmup_ratio", 0.03))
    max_seq_length = args.max_seq_length if args.max_seq_length is not None else int(lora_cfg.get("max_seq_length", 4096))

    target_modules = lora_cfg.get(
        "target_modules",
        ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    print(f"Repo root: {repo_root}")
    print(f"Profile: {args.profile}")
    print(f"Base model: {args.base_model}")
    print(f"Corpus: {corpus_path}")
    print(f"Output: {output_dir}")

    training_device = resolve_training_device()
    print(f"Training device: {training_device}")

    if training_device != "cuda" and not args.allow_cpu:
        raise RuntimeError(
            "No GPU backend detected by torch; refusing CPU fallback by default to avoid OOM kills. "
            "Enable GPU/ROCm in the dev container, or rerun with --allow_cpu (recommended only for smaller models)."
        )

    dataset = load_corpus(corpus_path)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if training_device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=dtype,
        low_cpu_mem_usage=False,
    )
    model.config.use_cache = False
    model.to(training_device)

    peft_config = LoraConfig(
        r=int(lora_cfg.get("lora_r", 32)),
        lora_alpha=int(lora_cfg.get("lora_alpha", 64)),
        lora_dropout=float(lora_cfg.get("lora_dropout", 0.05)),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, peft_config)
    # Required with checkpointing + LoRA so checkpointed activations keep grad flow.
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.print_trainable_parameters()

    def tokenize_batch(batch: dict) -> dict:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )

    tokenized = dataset.map(tokenize_batch, batched=True, remove_columns=["text"])

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        logging_steps=10,
        save_strategy="epoch",
        bf16=training_device == "cuda",
        fp16=False,
        gradient_checkpointing=True,
        no_cuda=training_device != "cuda",
        report_to="none",
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    trainer.train()

    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    metadata = {
        "profile": args.profile,
        "base_model": args.base_model,
        "corpus": str(corpus_path),
        "output_dir": str(output_dir),
        "epochs": epochs,
        "batch_size": batch_size,
        "grad_accum": grad_accum,
        "learning_rate": learning_rate,
        "warmup_ratio": warmup_ratio,
        "max_seq_length": max_seq_length,
    }
    (output_dir / "lora-metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"LoRA adapter training complete: {output_dir}")


if __name__ == "__main__":
    main()
