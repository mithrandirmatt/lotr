import argparse
import json
import os
from pathlib import Path
from typing import Any

from model_config import load_model_config, resolve_base_models, resolve_lora

# Text-only SFT does not require torchvision; keep parity with build.finetune.py's
# ROCm-safe defaults.
os.environ.setdefault("TRANSFORMERS_NO_TORCHVISION", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "garbage_collection_threshold:0.8,max_split_size_mb:128")
os.environ.setdefault("PYTORCH_NO_HIP_MEMORY_CACHING", "1")

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import transformers.modeling_utils as modeling_utils
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)
from trl import DataCollatorForCompletionOnlyLM


class MetricsExportCallback(TrainerCallback):
    """Callback to export training metrics (loss, learning rate) to JSON."""

    def __init__(self, output_path: Path):
        self.output_path = Path(output_path)
        self.metrics_history: list[dict] = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and ("loss" in logs or "learning_rate" in logs):
            entry = {"step": state.global_step, "epoch": state.epoch}
            if "loss" in logs:
                entry["loss"] = logs["loss"]
            if "learning_rate" in logs:
                entry["learning_rate"] = logs["learning_rate"]
            self.metrics_history.append(entry)

    def on_train_end(self, args, state, control, **kwargs):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "training_steps": state.global_step,
            "training_epochs": state.epoch,
            "metrics": self.metrics_history,
        }
        self.output_path.write_text(json.dumps(output, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        print(f"\n[INFO] Training metrics exported to: {self.output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SFT-train a LoRA adapter on chat/reasoning-distillation data with response-only loss masking "
        "(see build.sft_corpus.py to produce the input corpus)."
    )
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--model_config", default="qwen35-9b")
    parser.add_argument("--base_model", default=None)
    parser.add_argument("--corpus", default=None, help="SFT JSONL with {'messages': [...]} rows")
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--epochs", type=float, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--grad_accum", type=int, default=None)
    parser.add_argument("--learning_rate", type=float, default=None)
    parser.add_argument("--warmup_ratio", type=float, default=None)
    parser.add_argument("--max_seq_length", type=int, default=None)
    parser.add_argument(
        "--response_template",
        default=None,
        help="Substring marking the start of the assistant turn, used for completion-only loss masking. "
        "Defaults to the model config's chat_response_template, or Qwen's '<|im_start|>assistant\\n'.",
    )
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


def load_sft_corpus(corpus_path: Path) -> list[dict]:
    rows: list[dict] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            messages = item.get("messages")
            if isinstance(messages, list) and len(messages) >= 2:
                rows.append({"messages": messages})
    if not rows:
        raise RuntimeError(
            f"No SFT training samples found in corpus: {corpus_path}. "
            "Run build.sft_corpus.py first to generate it."
        )
    return rows


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


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _disable_rocm_allocator_warmup_for_quantized_load() -> None:
    original = getattr(modeling_utils, "caching_allocator_warmup", None)
    if original is None:
        return

    def _rocm_safe_warmup(*args: Any, **kwargs: Any) -> None:
        # HF allocator warmup can trip hipErrorInvalidValue on ROCm during
        # quantized shard loading. Skipping the warmup is slower but stable.
        return None

    modeling_utils.caching_allocator_warmup = _rocm_safe_warmup


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    profile = load_profile(repo_root, args.profile)
    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)
    _, cfg_hf_model = resolve_base_models(model_cfg)
    base_model = args.base_model or cfg_hf_model or "Qwen/Qwen3.5-9B"
    lora_cfg = resolve_lora(profile, model_cfg)

    corpus_path = (
        Path(args.corpus).resolve()
        if args.corpus
        else repo_root / "do" / "agent" / "models" / "training" / f"{args.profile}-sft-corpus.jsonl"
    )
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else repo_root / "do" / "agent" / "models" / "lora" / f"{args.profile}-sft"
    )

    epochs = args.epochs if args.epochs is not None else float(lora_cfg.get("epochs", 1))
    batch_size = args.batch_size if args.batch_size is not None else int(lora_cfg.get("batch_size", 1))
    grad_accum = args.grad_accum if args.grad_accum is not None else int(lora_cfg.get("grad_accum", 8))
    learning_rate = args.learning_rate if args.learning_rate is not None else float(lora_cfg.get("learning_rate", 1e-4))
    warmup_ratio = args.warmup_ratio if args.warmup_ratio is not None else float(lora_cfg.get("warmup_ratio", 0.03))
    max_seq_length = args.max_seq_length if args.max_seq_length is not None else int(lora_cfg.get("max_seq_length", 4096))
    response_template = args.response_template or model_cfg.get("chat_response_template", "<|im_start|>assistant\n")

    target_modules = lora_cfg.get("target_modules", "all-linear")

    print(f"Repo root: {repo_root}")
    print(f"Profile: {args.profile}")
    if model_cfg_path:
        print(f"Model config: {model_cfg_path}")
    print(f"Base model: {base_model}")
    print(f"SFT corpus: {corpus_path}")
    print(f"Output: {output_dir}")
    print(f"Response template (completion-only masking): {response_template!r}")

    training_device = resolve_training_device()
    print(f"Training device: {training_device}")

    if training_device != "cuda" and not args.allow_cpu:
        raise RuntimeError(
            "No GPU backend detected by torch; refusing CPU fallback by default to avoid OOM kills. "
            "Enable GPU/ROCm in the dev container, or rerun with --allow_cpu (recommended only for smaller models)."
        )

    sft_rows = load_sft_corpus(corpus_path)

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def render_text(row: dict) -> dict:
        text = tokenizer.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        return {"text": text}

    dataset = Dataset.from_list(sft_rows).map(render_text, remove_columns=["messages"])

    load_in_4bit = _parse_bool(lora_cfg.get("load_in_4bit"), default=(training_device == "cuda"))
    load_in_8bit = _parse_bool(lora_cfg.get("load_in_8bit"), default=False)
    use_quantized = training_device == "cuda" and (load_in_4bit or load_in_8bit)
    torch_dtype = torch.bfloat16 if training_device == "cuda" else torch.float32

    model_kwargs: dict[str, Any] = {
        "dtype": torch_dtype,
        "low_cpu_mem_usage": True,
    }
    is_rocm = bool(getattr(torch.version, "hip", None))

    if use_quantized:
        if is_rocm:
            torch_dtype = torch.float16
            model_kwargs["dtype"] = torch_dtype
            _disable_rocm_allocator_warmup_for_quantized_load()
            model_kwargs["low_cpu_mem_usage"] = False
            print("ROCm detected: using FP16 and disabling Transformers allocator warmup for quantized load stability.")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=load_in_4bit,
            load_in_8bit=load_in_8bit,
            bnb_4bit_quant_type=str(lora_cfg.get("bnb_4bit_quant_type", "nf4")),
            bnb_4bit_use_double_quant=_parse_bool(lora_cfg.get("bnb_4bit_use_double_quant"), default=True),
            bnb_4bit_compute_dtype=torch_dtype,
        )
        model_kwargs["quantization_config"] = bnb_config
        device_map_cfg = lora_cfg.get("device_map", "auto")
        if is_rocm:
            # bitsandbytes quantized ROCm modules can fail on a later model.to("cuda")
            # with hipErrorInvalidValue. Place the quantized shards directly on the
            # accelerator during load and skip the post-load model.to hop.
            if str(device_map_cfg).lower() == "auto":
                model_kwargs["device_map"] = {"": 0}
            else:
                model_kwargs["device_map"] = str(device_map_cfg)
        else:
            model_kwargs["device_map"] = str(device_map_cfg)

    try:
        model = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)
    except Exception as exc:
        if use_quantized:
            if is_rocm:
                raise RuntimeError(
                    "ROCm quantized model loading failed on this stack. The current Transformers/bitsandbytes "
                    "path is not loading this model reliably under ROCm in the dev container. "
                    "Try disabling quantized loading by setting load_in_4bit=false in the model/profile config."
                ) from exc
            raise RuntimeError(
                "Failed to load quantized base model for SFT. "
                "Ensure bitsandbytes is installed in the training venv and supported on this build. "
                "You can temporarily disable quantized loading by setting load_in_4bit=false in the model/profile config."
            ) from exc
        raise
    model.config.use_cache = False

    if use_quantized:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    elif training_device == "cuda":
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

    requested_optim = str(lora_cfg.get("optim", "paged_adamw_8bit" if use_quantized else "adamw_torch"))
    if is_rocm and requested_optim.startswith("paged_adamw"):
        requested_optim = "adamw_torch"
        print("ROCm detected: overriding optimizer to adamw_torch for stability.")

    # transformers >=5.x dropped the `warmup_ratio` kwarg from TrainingArguments
    # (only `warmup_steps` remains). Replicate the old warmup_ratio behavior by
    # computing the equivalent absolute step count ourselves.
    steps_per_epoch = max(1, -(-len(tokenized) // (batch_size * grad_accum)))
    total_training_steps = max(1, int(steps_per_epoch * epochs))
    warmup_steps = max(0, int(total_training_steps * warmup_ratio))

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        logging_steps=10,
        save_strategy="epoch",
        bf16=training_device == "cuda" and not is_rocm,
        fp16=training_device == "cuda" and is_rocm,
        gradient_checkpointing=True,
        optim=requested_optim,
        use_cpu=training_device != "cuda",
        dataloader_pin_memory=not is_rocm,
        report_to="none",
    )

    collator = DataCollatorForCompletionOnlyLM(response_template=response_template, tokenizer=tokenizer)

    print(f"\n[INFO] SFT Training Configuration:")
    print(f"  Base model: {base_model}")
    print(f"  Target modules: {target_modules}")
    print(f"  Epochs: {epochs}, Batch size: {batch_size}, Grad accum: {grad_accum}")
    print(f"  Learning rate: {learning_rate}, Warmup ratio: {warmup_ratio} ({warmup_steps} steps of {total_training_steps})")
    print(f"  Samples: {len(tokenized)}")
    print()

    if training_device == "cuda" and is_rocm:
        torch.cuda.set_device(0)
        _ = torch.empty(1, device="cuda")
        torch.cuda.empty_cache()

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
        callbacks=[MetricsExportCallback(output_dir / "training-metrics.json")],
    )

    trainer.train()

    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    metadata = {
        "profile": args.profile,
        "model_config": model_cfg.get("id") if model_cfg else None,
        "base_model": base_model,
        "corpus": str(corpus_path),
        "output_dir": str(output_dir),
        "epochs": epochs,
        "batch_size": batch_size,
        "grad_accum": grad_accum,
        "learning_rate": learning_rate,
        "warmup_ratio": warmup_ratio,
        "warmup_steps": warmup_steps,
        "max_seq_length": max_seq_length,
        "target_modules": target_modules,
        "response_template": response_template,
        "load_in_4bit": load_in_4bit,
        "load_in_8bit": load_in_8bit,
        "device_map": model_kwargs.get("device_map"),
        "training_mode": "sft-completion-only-masking",
    }
    (output_dir / "lora-metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"SFT LoRA adapter training complete: {output_dir}")


if __name__ == "__main__":
    main()
