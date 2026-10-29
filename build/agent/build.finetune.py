import argparse
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from model_config import load_model_config, resolve_base_models, resolve_lora

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "garbage_collection_threshold:0.8,max_split_size_mb:128")
# Work around intermittent ROCm allocator handle assertion failures in long-lived
# training processes by disabling HIP caching allocator state reuse.
os.environ.setdefault("PYTORCH_NO_HIP_MEMORY_CACHING", "1")

# flash-linear-attention's own autotuner (fla.ops.utils.cache) can select pathological
# num_warps/num_stages candidates on ROCm/RDNA3 whose AMDGCN codegen takes 100-200x
# longer than sibling candidates of the *same* kernel (observed: 85min vs 53s, and a
# 3+ hour hang) -- fla's source already documents this exact instability class for
# NVIDIA Blackwell (see prepare_wy_repr_bwd_kernel's "(see #913)" comment) but has no
# equivalent guard for AMD yet. FLA_CACHE_MODE=default + FLA_CONFIG_DIR pin the known
# fast config for the two affected kernels via build/agent/fla_configs/*.json,
# skipping the pathological candidates entirely; must be set before fla is imported
# (its cache mode is read once at module import time). This must be read from
# environment, not evaluated once here, so it can still be overridden for debugging.
os.environ.setdefault("FLA_CACHE_MODE", "default")
os.environ.setdefault("FLA_CONFIG_DIR", str(Path(__file__).resolve().parent / "fla_configs"))

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import transformers.modeling_utils as modeling_utils
from transformers import (
    AutoModelForCausalLM,
    AutoModelForMultimodalLM,
    AutoProcessor,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

# Report REAL progress (not just "still alive") through the ROCm/Triton kernel compiles
# that flash-linear-attention's Gated DeltaNet layers trigger lazily on first use. Each
# distinct kernel/config only ever needs to compile once (cached in TRITON_CACHE_DIR
# afterwards), so wrapping Triton's own compile entrypoint lets us print one line per
# kernel as it finishes, with its actual compile duration -- a cache hit prints ~0.0s,
# a genuine new ROCm compile prints its real (often 60-600s) duration. This is concrete,
# incrementing evidence of forward progress, unlike a bare "still running" heartbeat.
try:
    import triton.compiler.compiler as _triton_compiler_module

    _triton_compile_original = _triton_compiler_module.compile
    _triton_compile_count = {"n": 0}
    _triton_compile_lock = threading.Lock()

    def _traced_triton_compile(*args, **kwargs):
        with _triton_compile_lock:
            _triton_compile_count["n"] += 1
            idx = _triton_compile_count["n"]
        start = time.monotonic()
        try:
            return _triton_compile_original(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - start
            status = "cache hit" if elapsed < 1.0 else "NEW COMPILE"
            print(
                f"[TRITON COMPILE] kernel #{idx} finished in {elapsed:.1f}s ({status}).",
                flush=True,
            )

    _triton_compiler_module.compile = _traced_triton_compile
except ImportError:
    pass  # Triton not installed (e.g. CPU-only fallback venv) -- nothing to trace.

# Also hook Triton's autotuner so each kernel's candidate-config search reports a REAL
# "config X/Y (Z%)" progress fraction -- self.configs is a fixed, known-length list of
# candidates for that kernel, so this is a genuine, non-fabricated percentage (scoped to
# the current kernel's autotune search), not a guessed-at global completion percentage.
try:
    import triton.runtime.autotuner as _triton_autotuner_module

    _autotune_progress: dict = {}
    _autotune_lock = threading.Lock()
    _autotune_bench_original = _triton_autotuner_module.Autotuner._bench

    def _traced_autotune_bench(self, *args, config, **meta):
        name = self.base_fn.__name__
        total = len(self.configs)
        with _autotune_lock:
            count = _autotune_progress.get(name, 0) + 1
            if count > total:
                count = 1
            _autotune_progress[name] = count
        start = time.monotonic()
        result = _autotune_bench_original(self, *args, config=config, **meta)
        elapsed = time.monotonic() - start
        pct = int(100 * count / total) if total else 100
        print(
            f"[AUTOTUNE] {name}: config {count}/{total} ({pct}%) benched in {elapsed:.1f}s",
            flush=True,
        )
        return result

    _triton_autotuner_module.Autotuner._bench = _traced_autotune_bench
except ImportError:
    pass  # Triton not installed (e.g. CPU-only fallback venv) -- nothing to trace.

# Opt-in escape hatch: on ROCm, flash-linear-attention's Triton autotuner for the
# Qwen3.5 Gated DeltaNet backward kernel can stall for a very long time compiling
# AMDGCN candidates (ROCm codegen is far slower than CUDA/NVPTX here) before the
# first training step even starts. Setting LORA_DISABLE_FLA=1 forces transformers'
# architecture-level import check to see flash-linear-attention as unavailable,
# which makes it fall back to the plain torch_chunk_gated_delta_rule/
# torch_recurrent_gated_delta_rule implementations instead (no Triton compile at
# all for this recurrence, at the cost of slower steady-state per-step compute).
# Must be set before any Qwen3.5 model class is imported/instantiated.
if os.environ.get("LORA_DISABLE_FLA") == "1":
    import transformers.utils.import_utils as _import_utils

    _import_utils.is_flash_linear_attention_available = lambda: False
    print("[INFO] LORA_DISABLE_FLA=1: forcing plain torch fallback for Gated DeltaNet (skipping fla/Triton path).")


class MetricsExportCallback(TrainerCallback):
    """Callback to export training metrics (loss, learning rate) to JSON."""

    def __init__(self, output_path: Path):
        self.output_path = Path(output_path)
        self.metrics_history = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and ("loss" in logs or "learning_rate" in logs):
            entry = {
                "step": state.global_step,
                "epoch": state.epoch,
            }
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
    parser = argparse.ArgumentParser(description="Train a LoRA adapter from repository corpus")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--model_config", default=None)
    parser.add_argument("--base_model", default=None)
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--epochs", type=float, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--grad_accum", type=int, default=None)
    parser.add_argument("--learning_rate", type=float, default=None)
    parser.add_argument("--warmup_ratio", type=float, default=None)
    parser.add_argument("--max_seq_length", type=int, default=None)
    parser.add_argument(
        "--max_train_samples",
        type=int,
        default=None,
        help="Cap the number of corpus rows used for training (smoke-testing the pipeline without a full run).",
    )
    parser.add_argument(
        "--max_steps",
        type=int,
        default=None,
        help="Cap the number of optimizer steps, overriding --epochs (smoke-testing the pipeline without a full run).",
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


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _read_available_cpu_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1]) * 1024
    page_size = os.sysconf("SC_PAGE_SIZE")
    pages = os.sysconf("SC_PHYS_PAGES")
    return int(page_size) * int(pages)


def _bytes_to_gib_string(value: int, reserve_gib: int = 0, floor_gib: int = 1) -> str:
    gib = max(floor_gib, int(value / (1024**3)) - reserve_gib)
    return f"{gib}GiB"


def _estimate_training_memory(
    base_model: str,
    load_in_4bit: bool,
    load_in_8bit: bool,
    batch_size: int,
    grad_accum: int,
) -> tuple[float, str]:
    """Estimate GPU memory needed for training.

    Returns (estimated_gb, warning_string).

    Rough estimation:
    - Model size: base_model weights (varies by size)
    - Quantized weights: 4-bit ≈ 25% of FP32, 8-bit ≈ 50%
    - Activations + gradients: ~2x model size per effective batch
    - Optimizer states: ~2x model size for AdamW
    """

    # Rough model sizes (FP16/BF16 weights, ~2 bytes/param)
    model_sizes_gb = {
        "7b": 14,
        "8b": 16,
        "9b": 18,
        "13b": 26,
        "14b": 28,
        "30b": 60,
    }

    # Try to extract model size from name
    model_size_gb = 16  # default fallback
    for size_str, size_gb in model_sizes_gb.items():
        if size_str in base_model.lower():
            model_size_gb = size_gb
            break

    # Apply quantization
    if load_in_4bit:
        model_size_gb *= 0.25
    elif load_in_8bit:
        model_size_gb *= 0.5

    # Activation + gradient overhead (2x per effective batch)
    effective_batch = batch_size * grad_accum
    activation_overhead = model_size_gb * 2 * (effective_batch / 32)  # normalized to batch_size=32

    # Optimizer states (AdamW: 2x for momentum + variance)
    optimizer_overhead = model_size_gb * 2

    total_estimate_gb = model_size_gb + activation_overhead + optimizer_overhead

    warning = ""
    if total_estimate_gb > 20:
        warning = f"⚠️  Estimated {total_estimate_gb:.1f}GB memory needed (24GB GPU margin thin; may OOM)"
    elif total_estimate_gb > 18:
        warning = f"⚠️  Estimated {total_estimate_gb:.1f}GB memory (leaving only {24 - total_estimate_gb:.1f}GB margin)"

    return total_estimate_gb, warning


def _disable_rocm_allocator_warmup_for_quantized_load() -> None:
    original = getattr(modeling_utils, "caching_allocator_warmup", None)
    if original is None:
        return

    def _rocm_safe_warmup(*args: Any, **kwargs: Any) -> None:
        # HF allocator warmup can trip hipErrorInvalidValue on ROCm during
        # quantized shard loading. Skipping the warmup is slower but stable.
        return None

    modeling_utils.caching_allocator_warmup = _rocm_safe_warmup


def _maybe_apply_liger_kernel(model: Any) -> bool:
    # Liger Kernel's fused linear cross-entropy fuses the LM-head projection with the loss,
    # computing it in GPU-resident chunks without ever materializing the full
    # [seq_len, vocab_size] logits tensor -- fixes the OOM without a CPU round-trip.
    # Only applies to Qwen3.5 (dense or MoE, causal or vision-language); other model
    # profiles fall through untouched.
    try:
        from transformers.models.qwen3_5.modeling_qwen3_5 import (
            Qwen3_5ForCausalLM,
            Qwen3_5ForConditionalGeneration,
        )
        from liger_kernel.transformers.monkey_patch import apply_liger_kernel_to_qwen3_5
    except ImportError:
        return False
    if not isinstance(model, (Qwen3_5ForCausalLM, Qwen3_5ForConditionalGeneration)):
        return False
    apply_liger_kernel_to_qwen3_5(model=model)
    return True


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    profile = load_profile(repo_root, args.profile)
    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)
    _, cfg_hf_model = resolve_base_models(model_cfg)
    base_model = args.base_model or cfg_hf_model or "Qwen/Qwen2.5-Coder-7B-Instruct"
    lora_cfg = resolve_lora(profile, model_cfg)

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
    if model_cfg_path:
        print(f"Model config: {model_cfg_path}")
    print(f"Base model: {base_model}")
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
    if args.max_train_samples is not None:
        dataset = dataset.select(range(min(len(dataset), args.max_train_samples)))
        print(f"Smoke-test cap: using {len(dataset)} corpus row(s) (--max_train_samples {args.max_train_samples})")

    # Vision-language checkpoints (e.g. Qwen/Qwen3.5-9B) default to the
    # text-only AutoModelForCausalLM shortcut, which silently discards the
    # vision tower on load. Setting lora_overrides.keep_vision=true trains
    # through the official AutoModelForMultimodalLM/AutoProcessor path
    # instead, keeping the vision tower intact (matches Qwen's own model-card
    # usage example). Our corpus is text-only either way, so the processor's
    # own tokenizer is used exactly like a plain AutoTokenizer below.
    keep_vision = _parse_bool(lora_cfg.get("keep_vision"), default=False)
    if keep_vision:
        processor = AutoProcessor.from_pretrained(base_model, trust_remote_code=True)
        tokenizer = processor.tokenizer
    else:
        tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_in_4bit = _parse_bool(lora_cfg.get("load_in_4bit"), default=(training_device == "cuda"))
    load_in_8bit = _parse_bool(lora_cfg.get("load_in_8bit"), default=False)
    use_quantized = training_device == "cuda" and (load_in_4bit or load_in_8bit)
    torch_dtype = torch.bfloat16 if training_device == "cuda" else torch.float32

    model_kwargs: dict[str, Any] = {
        "dtype": torch_dtype,
        "low_cpu_mem_usage": True,
        "trust_remote_code": True,
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
        if str(device_map_cfg).lower() == "auto":
            # Split the quantized model across GPU VRAM + system RAM so training
            # can use more than just the dedicated VRAM budget instead of OOMing
            # once VRAM alone is exhausted. accelerate's CPU-offload dispatch for
            # quantized ROCm loads previously crashed with hipErrorInvalidValue on
            # a later model.to("cuda") hop; that .to() hop is skipped entirely
            # here (device_map handles placement at load time), so attempt real
            # offload rather than forcing everything onto a single device.
            gpu_total_bytes = torch.cuda.get_device_properties(0).total_memory
            cpu_available_bytes = _read_available_cpu_bytes()
            gpu_budget = _bytes_to_gib_string(gpu_total_bytes, reserve_gib=2, floor_gib=1)
            cpu_budget = _bytes_to_gib_string(cpu_available_bytes, reserve_gib=4, floor_gib=4)
            model_kwargs["device_map"] = "auto"
            model_kwargs["max_memory"] = {0: gpu_budget, "cpu": cpu_budget}
            # accelerate's multi-device dispatch requires low_cpu_mem_usage=True
            # (meta-device sharded loading); the ROCm single-device branch above
            # disables it for allocator-warmup stability, but that doesn't apply
            # once we're actually splitting across devices.
            model_kwargs["low_cpu_mem_usage"] = True
            print(f"CPU+GPU offload enabled for quantized load. Max memory: {model_kwargs['max_memory']}")
        else:
            model_kwargs["device_map"] = str(device_map_cfg)
    model_cls = AutoModelForMultimodalLM if keep_vision else AutoModelForCausalLM
    try:
        model = model_cls.from_pretrained(base_model, **model_kwargs)
    except Exception as exc:
        if use_quantized:
            if is_rocm:
                raise RuntimeError(
                    "ROCm quantized model loading with CPU+GPU offload failed on this stack. "
                    "This is likely the known ROCm+bitsandbytes accelerate-dispatch instability. "
                    "You can fall back to single-device loading by setting device_map=cuda (or device_map={\"\":0}) "
                    "in the model/profile config, or disable quantized loading entirely by setting load_in_4bit=false."
                ) from exc
            raise RuntimeError(
                "Failed to load quantized base model for LoRA. "
                "Ensure bitsandbytes is installed in the training venv and supported on this build. "
                "You can temporarily disable quantized loading by setting load_in_4bit=false in the model/profile config."
            ) from exc
        raise
    model.config.use_cache = False

    liger_applied = _maybe_apply_liger_kernel(model)

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

    requested_optim = str(lora_cfg.get("optim", "paged_adamw_8bit" if use_quantized else "adamw_torch"))
    if is_rocm and requested_optim.startswith("paged_adamw"):
        # paged_adamw_8bit can be unstable on ROCm+bnb CPU backend; use torch optimizer.
        requested_optim = "adamw_torch"
        print("ROCm detected: overriding optimizer to adamw_torch for stability.")

    # transformers >=5.x dropped the `warmup_ratio` kwarg from TrainingArguments
    # (only `warmup_steps` remains). Replicate the old warmup_ratio behavior by
    # computing the equivalent absolute step count ourselves.
    if args.max_steps is not None and args.max_steps > 0:
        total_training_steps = args.max_steps
    else:
        steps_per_epoch = max(1, -(-len(tokenized) // (batch_size * grad_accum)))
        total_training_steps = max(1, int(steps_per_epoch * epochs))
    warmup_steps = max(0, int(total_training_steps * warmup_ratio))

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        max_steps=args.max_steps if args.max_steps is not None else -1,
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

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    # Estimate memory before training
    est_gb, mem_warning = _estimate_training_memory(
        base_model, _parse_bool(load_in_4bit, False), _parse_bool(load_in_8bit, False), batch_size, grad_accum
    )
    print(f"\n[INFO] Training Configuration:")
    print(f"  Base model: {base_model}")
    print(f"  Epochs: {epochs}, Batch size: {batch_size}, Grad accum: {grad_accum}")
    print(f"  Learning rate: {learning_rate}, Warmup ratio: {warmup_ratio} ({warmup_steps} steps of {total_training_steps})")
    print(f"  Est. GPU memory: {est_gb:.1f} GB")
    if mem_warning:
        print(f"  {mem_warning}")
    print()

    if training_device == "cuda" and is_rocm:
        # Force HIP context + allocator initialization before Trainer creates its
        # first device tensor to avoid intermittent HIPCachingAllocator asserts.
        torch.cuda.set_device(0)
        _ = torch.empty(1, device="cuda")
        torch.cuda.empty_cache()

    if liger_applied:
        print(
            "[INFO] Liger Kernel's fused linear cross-entropy is active for this Qwen3.5 model -- "
            "the LM head + loss are computed in GPU-resident chunks without ever materializing the "
            "full-vocab logits tensor, avoiding the earlier OOM with no CPU round-trip."
        )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
        callbacks=[MetricsExportCallback(output_dir / "training-metrics.json")],
    )

    if is_rocm and os.environ.get("LORA_DISABLE_FLA") != "1":
        print(
            "[INFO] ROCm + flash-linear-attention (fla) is active for Qwen3.5's Gated DeltaNet layers. "
            "The progress bar below will NOT move at all during the first backward pass while Triton "
            "compiles the ROCm (AMDGCN) kernels for this shape -- this has taken up to ~45-60 minutes "
            "on a fresh cache the first time (expected, not a hang). Watch for '[TRITON COMPILE] "
            "kernel #N finished in ...s' lines below -- each one is a real kernel finishing (NEW COMPILE "
            "= genuinely slow ROCm codegen just happened; cache hit = instant, already compiled). "
            f"Compiled kernels are cached to TRITON_CACHE_DIR "
            f"({os.environ.get('TRITON_CACHE_DIR', '<unset, defaults to ~/.triton/cache>')}), so this "
            "compile only needs to happen once per unique shape/config; subsequent runs reuse the cache "
            "and start immediately. Set LORA_DISABLE_FLA=1 to skip this compile (uses a slower, more "
            "memory-hungry torch fallback instead)."
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
        "load_in_4bit": load_in_4bit,
        "load_in_8bit": load_in_8bit,
        "device_map": model_kwargs.get("device_map"),
    }
    (output_dir / "lora-metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"LoRA adapter training complete: {output_dir}")


if __name__ == "__main__":
    main()
