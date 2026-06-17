import argparse
import os
import shutil
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
    parser.add_argument("--outtype", default="f16")
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


def _find_quantize_tool(llama_cpp_dir: Path) -> Path | None:
    candidates = [
        llama_cpp_dir / "build" / "bin" / "llama-quantize",
        llama_cpp_dir / "build" / "bin" / "quantize",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _ensure_quantize_tool(llama_cpp_dir: Path) -> Path:
    existing = _find_quantize_tool(llama_cpp_dir)
    if existing is not None:
        return existing

    build_dir = llama_cpp_dir / "build"
    print("llama-quantize not found; attempting to build llama.cpp quantize tool...")
    subprocess.run(["cmake", "-S", str(llama_cpp_dir), "-B", str(build_dir)], check=True)

    for target in ("llama-quantize", "quantize"):
        try:
            subprocess.run(["cmake", "--build", str(build_dir), "--target", target, "-j"], check=True)
        except subprocess.CalledProcessError:
            continue
        existing = _find_quantize_tool(llama_cpp_dir)
        if existing is not None:
            return existing

    raise FileNotFoundError(
        "Unable to locate or build llama.cpp quantize tool. "
        "Expected llama-quantize or quantize under llama.cpp/build/bin/."
    )


def _normalize_quant_outtype(outtype: str) -> str:
    return outtype.strip().upper()


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
    print(f"GGUF outtype: {args.outtype}")
    print("Adapter apply is internal to export; GGUF is the deployment artifact.")

    use_cuda = torch.cuda.is_available() and os.environ.get("LOTR_LORA_EXPORT_USE_CUDA") == "1"
    # Keep CPU export memory footprint reasonable for 14B merges.
    dtype = torch.float16
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
        # Avoid Accelerate offload/meta hooks in CPU mode; PEFT adapter attach can
        # crash in _update_offload with Qwen module prefixes when disk hooks exist.
        model_kwargs["device_map"] = {"": "cpu"}
        model_kwargs["low_cpu_mem_usage"] = False
        print("CPU-only merge selected; loading base model fully on CPU (no disk offload hooks).")

    offload_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=True)
    base = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)
    print("Applying LoRA adapter to base model for GGUF export...")

    use_disk_offload = "offload_folder" in model_kwargs
    peft_kwargs = {
        "is_trainable": False,
        "device_map": model_kwargs.get("device_map"),
        "max_memory": model_kwargs.get("max_memory"),
    }
    if use_disk_offload:
        # PEFT/Accelerate versions vary on whether they expect offload_dir or
        # offload_folder; provide both to keep adapter dispatch compatible.
        peft_kwargs["offload_dir"] = str(offload_dir)
        peft_kwargs["offload_folder"] = str(offload_dir)

    try:
        peft_model = PeftModel.from_pretrained(base, str(adapter_dir), **peft_kwargs)
    except KeyError as exc:
        if not use_disk_offload:
            raise
        print(f"Disk-offload adapter attach failed: {exc}")
        print("Retrying adapter attach without disk offload metadata...")

        del base
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        retry_kwargs = dict(model_kwargs)
        retry_kwargs.pop("offload_folder", None)
        retry_kwargs.pop("offload_state_dict", None)
        retry_kwargs.pop("max_memory", None)
        retry_kwargs["device_map"] = {"": "cpu"}
        retry_kwargs["low_cpu_mem_usage"] = False
        base = AutoModelForCausalLM.from_pretrained(base_model, **retry_kwargs)
        peft_model = PeftModel.from_pretrained(base, str(adapter_dir), is_trainable=False)

    merged = peft_model.merge_and_unload()

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_dir, safe_serialization=True)
    tokenizer.save_pretrained(merged_dir)

    converter = _ensure_llama_cpp(llama_cpp_dir)
    output_gguf.parent.mkdir(parents=True, exist_ok=True)
    converter_supported = {"f32", "f16", "bf16", "q8_0", "tq1_0", "tq2_0", "auto"}
    requested_outtype = str(args.outtype).strip().lower()

    if requested_outtype in converter_supported:
        subprocess.run(
            [
                sys.executable,
                str(converter),
                str(merged_dir),
                "--outfile",
                str(output_gguf),
                "--outtype",
                requested_outtype,
            ],
            check=True,
        )
    else:
        # q4_k_m (and similar) are not supported by convert_hf_to_gguf.py in this
        # llama.cpp version. Export f16 first, then quantize using llama-quantize.
        tmp_f16 = output_gguf.parent / f"{output_gguf.stem}.tmp-f16.gguf"
        print(
            "Requested outtype is not supported by convert_hf_to_gguf.py; "
            f"falling back to two-step export: f16 -> {requested_outtype}."
        )
        subprocess.run(
            [
                sys.executable,
                str(converter),
                str(merged_dir),
                "--outfile",
                str(tmp_f16),
                "--outtype",
                "f16",
            ],
            check=True,
        )

        quantize_tool = _ensure_quantize_tool(llama_cpp_dir)

        quant_outtype = _normalize_quant_outtype(requested_outtype)
        subprocess.run(
            [
                str(quantize_tool),
                str(tmp_f16),
                str(output_gguf),
                quant_outtype,
            ],
            check=True,
        )
        tmp_f16.unlink(missing_ok=True)

    print(f"GGUF export completed: {output_gguf}")

    keep_merged = os.environ.get("LOTR_LORA_EXPORT_KEEP_MERGED") == "1"
    if keep_merged:
        print(f"Keeping merged model directory for debugging: {merged_dir}")
    else:
        shutil.rmtree(merged_dir, ignore_errors=True)
        print(f"Removed transient merged model directory: {merged_dir}")


if __name__ == "__main__":
    main()