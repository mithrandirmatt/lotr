import argparse
import os
import subprocess
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from model_config import load_model_config, resolve_base_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge a trained LoRA adapter and export GGUF")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--model_config", default=None)
    parser.add_argument("--base_model", default=None)
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--merged_dir", required=True)
    parser.add_argument("--output_gguf", required=True)
    parser.add_argument("--llama_cpp_dir", required=True)
    return parser.parse_args()


def _ensure_llama_cpp(llama_cpp_dir: Path) -> Path:
    if not llama_cpp_dir.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/ggerganov/llama.cpp.git", str(llama_cpp_dir)],
            check=True,
        )

    candidates = [
        llama_cpp_dir / "convert_hf_to_gguf.py",
        llama_cpp_dir / "tools" / "convert_hf_to_gguf.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"convert_hf_to_gguf.py not found in {llama_cpp_dir}")


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


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    adapter_dir = Path(args.adapter_dir).resolve()
    merged_dir = Path(args.merged_dir).resolve()
    output_gguf = Path(args.output_gguf).resolve()
    llama_cpp_dir = Path(args.llama_cpp_dir).resolve()
    offload_dir = merged_dir / "offload"

    if not adapter_dir.exists():
        raise FileNotFoundError(f"Adapter directory not found: {adapter_dir}")

    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)
    _, cfg_hf_model = resolve_base_models(model_cfg)
    base_model = args.base_model or cfg_hf_model or "Qwen/Qwen2.5-Coder-7B-Instruct"

    print(f"Repo root: {repo_root}")
    print(f"Profile: {args.profile}")
    if model_cfg_path:
        print(f"Model config: {model_cfg_path}")
    print(f"Base model: {base_model}")
    print(f"Adapter dir: {adapter_dir}")
    print(f"Merged dir: {merged_dir}")
    print(f"Offload dir: {offload_dir}")
    print(f"Output GGUF: {output_gguf}")

    use_cuda = torch.cuda.is_available() and os.environ.get("LOTR_LORA_EXPORT_USE_CUDA") == "1"
    dtype = torch.float16 if use_cuda else torch.float32
    model_kwargs = {
        "dtype": dtype,
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if use_cuda:
        gpu_total_bytes = torch.cuda.get_device_properties(0).total_memory
        cpu_available_bytes = _read_available_cpu_bytes()
        gpu_budget = _bytes_to_gib_string(gpu_total_bytes, reserve_gib=4, floor_gib=1)
        cpu_budget = _bytes_to_gib_string(cpu_available_bytes, reserve_gib=8, floor_gib=8)
        max_memory = {0: gpu_budget, "cpu": cpu_budget}
        model_kwargs["device_map"] = "auto"
        model_kwargs["max_memory"] = max_memory
        model_kwargs["offload_folder"] = str(offload_dir)
        model_kwargs["offload_state_dict"] = True
        print(f"Max memory: {max_memory}")
    else:
        cpu_available_bytes = _read_available_cpu_bytes()
        cpu_budget = _bytes_to_gib_string(cpu_available_bytes, reserve_gib=8, floor_gib=8)
        # Keep auto placement even in CPU mode so Accelerate can spill to disk
        # via offload_folder when RAM pressure rises during shard loading.
        model_kwargs["device_map"] = "auto"
        model_kwargs["max_memory"] = {"cpu": cpu_budget}
        model_kwargs["offload_folder"] = str(offload_dir)
        model_kwargs["offload_state_dict"] = True
        print(f"CPU-only merge selected; max memory: {{'cpu': '{cpu_budget}'}}")

    offload_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)
    peft_model = PeftModel.from_pretrained(base, str(adapter_dir), is_trainable=False, offload_dir=str(offload_dir))
    merged = peft_model.merge_and_unload()

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)

    converter = _ensure_llama_cpp(llama_cpp_dir)
    output_gguf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(converter),
            str(merged_dir),
            "--outfile",
            str(output_gguf),
            "--outtype",
            "f16",
        ],
        check=True,
    )

    print(f"GGUF export completed: {output_gguf}")


if __name__ == "__main__":
    main()