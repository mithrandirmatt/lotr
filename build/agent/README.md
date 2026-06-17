# Local LLM Build Guide (build/agent)

This document describes the complete local LLM build pipeline implemented in this repository, with direct references to the source files that define behavior.

Scope:
- Containerized local build and install workflow for base, agentic, and LoRA model paths.
- RX 7900 XTX profile-driven defaults (and model config overrides).
- LoRA training, GGUF export, and Ollama installation flow.

Primary source-of-truth files:
- build/agent/agent.mk
- build/agent/build.train.py
- build/agent/build.finetune.py
- build/agent/build.modelfile.py
- build/agent/build.lora_export_gguf.py
- build/agent/build.lora_fingerprint.py
- build/agent/model_config.py
- build/agent/profiles/rx7900xtx-agentic.json
- build/agent/models/*.json
- build/agent/requirements-lora.txt
- build/makefiles/common.mk
- build/docker/docker-spec.md

## 1) High-Level Architecture

There are three build tracks:

1. Base track (placeholder/dummy GGUF scaffold for now)
- prepare-corpus -> train -> quantize -> optimize -> install base in Ollama

2. Agentic profile track
- prepare-corpus -> generate profile Modelfile -> install profile model in Ollama

3. LoRA track (actual local specialization path)
- prepare-corpus -> LoRA fingerprint gate -> LoRA train -> merge/export GGUF -> install LoRA GGUF in Ollama

Top-level rollups in build/agent/agent.mk:
- agent_build: base + agentic + LoRA full chain
- agentic_build: base install + profile Modelfile + agentic install
- lora_build: base install + LoRA train + LoRA install

## 2) Environment and Execution Model

All development commands are intended to run in the dev container, not on host Python.

Container entrypoint commands (documented in build/docker/docker-spec.md):
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 build
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 run
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile <target>"

Make inclusion chain:
- build/makefiles/common.mk includes build/agent/agent.mk
- So any make invocation using build/makefile can call agent targets.

## 3) Directory Layout and Required Inputs

Required source directories/files:
- build/agent/agent.mk
- build/agent/profiles/rx7900xtx-agentic.json
- build/agent/models/qwen25-coder-14b.json
- build/agent/models/qwen25-coder-7b.json
- build/agent/models/qwen3-30b-a3b-moe.json
- build/agent/requirements-lora.txt
- .github/copilot-instructions.md (used as SYSTEM prompt for generated Modelfiles)

Generated output root:
- do/agent/models/

Key generated artifacts under do/agent/models:
- training/<profile>-corpus.jsonl
- training/<profile>-metadata.json
- lotr-<base>-<quant>.gguf
- Modelfile.<profile>
- lora/<profile>/ (adapter_model.safetensors, adapter_config.json, tokenizer files, lora-metadata.json)
- lotr-lora-<profile>-f16.gguf
- cache/<profile>/lora-train.sha256

## 4) Configuration Resolution and Precedence

Defined in build/agent/model_config.py and consumed by training/export/modelfile scripts.

Resolution rules:
- Profile defaults come from build/agent/profiles/<profile>.json
- Model-specific overrides come from build/agent/models/<model-config>.json
- Merge behavior is deep-merge, with model overrides taking precedence over profile values.

Base model selection precedence (effective behavior):
- CLI --base_model if provided
- model config value (hf_base_model or ollama_base_model depending on script)
- hardcoded fallback in script

Examples:
- LoRA training/export use hf_base_model from model config when not overridden.
- Modelfile generation uses ollama_base_model from model config when not overridden.

## 5) Orchestration Variables (build/agent/agent.mk)

Important variables and defaults:
- AGENT_PROFILE=rx7900xtx-agentic
- AGENT_MODEL_CONFIG=qwen25-coder-14b
- MODEL_DIR=$(REPO_ROOT)/do/agent/models
- AGENT_CACHE_DIR=$(REPO_ROOT)/build/docker/cache
- AGENT_HF_CACHE_DIR=$(AGENT_CACHE_DIR)/huggingface
- AGENT_TORCH_CACHE_DIR=$(AGENT_CACHE_DIR)/torch
- AGENT_PIP_CACHE_DIR=$(AGENT_CACHE_DIR)/pip
- LLAMA_CPP_DIR=$(AGENT_CACHE_DIR)/llama.cpp
- LORA_OUTPUT_DIR=$(MODEL_DIR)/lora/$(AGENT_PROFILE)
- LORA_MERGED_DIR=$(MODEL_DIR)/lora-merged/$(AGENT_PROFILE)
- LORA_GGUF_OUTTYPE=q4_k_m (default)
- LORA_GGUF=$(MODEL_DIR)/lotr-lora-$(AGENT_PROFILE)-$(LORA_GGUF_OUTTYPE).gguf

Ollama naming:
- lotr-<base>-<quant>
- lotr-agentic-<profile>
- lotr-lora-<profile>

## 6) Stage-by-Stage Build Process

### Stage A: Corpus Preparation

Target:
- prepare-corpus

Source implementation:
- build/agent/build.train.py

What it does:
1. Loads profile include_globs/exclude_globs.
2. Walks repository and selects matching files.
3. Writes instruction-formatted JSONL corpus.
4. Writes corpus metadata JSON.
5. Writes placeholder GGUF to keep downstream base targets unblocked.

Inputs:
- profile JSON include/exclude globs
- optional model config
- repository files matched by globs

Outputs:
- do/agent/models/training/<profile>-corpus.jsonl
- do/agent/models/training/<profile>-metadata.json
- do/agent/models/lotr-<model>-<quantization>.gguf (placeholder)

### Stage B: Base Train/Quantize/Optimize (Scaffold Path)

Targets:
- train-<base>
- quantize-<quant>
- optimize-inference

Source implementation:
- build/agent/build.quantize.py
- build/agent/build.optimize.py

Current status:
- quantize and optimize scripts are placeholders/stubs.
- quantize writes a dummy GGUF header artifact.

Operational implication:
- Base model path currently acts as scaffold for workflow consistency.
- LoRA pipeline is the meaningful specialization path.

### Stage C: Python Package/Venv Setup

Implemented in multiple targets in build/agent/agent.mk.

Behavior:
- Creates/reuses build/agent/lotr_agent/venv.
- Installs editable local package build/agent/lotr_agent.
- Installs LoRA dependencies from build/agent/requirements-lora.txt.
- Uses cache directories under build/docker/cache for pip/HF/Torch.

ROCm specifics:
- Optional bitsandbytes ROCm source bootstrap path.
- ROCm torch checks/repair logic around torch._dynamo and wheel channel.

### Stage D: LoRA Fingerprint Gating

Targets:
- lora-fingerprint
- lora-train

Source implementation:
- build/agent/build.lora_fingerprint.py

Fingerprint inputs include:
- build/agent/profiles/<profile>.json
- corpus file
- build/agent/requirements-lora.txt
- build/agent/build.finetune.py
- selected model config file (if provided)
- explicit CLI knobs (profile/model_config/hf_base_model/allow_cpu/torch_variant)

Skip behavior:
- If adapter files exist and fingerprint unchanged, lora-train skips retraining.
- Cache files written to do/agent/models/cache/<profile>/.

### Stage E: LoRA Training

Target:
- lora-train-run

Source implementation:
- build/agent/build.finetune.py

What it does:
1. Resolves profile + model-config merged LoRA settings.
2. Loads corpus JSONL as Hugging Face Dataset.
3. Detects training device (CUDA/ROCm path or CPU fallback).
4. Loads base model and tokenizer.
5. Applies PEFT LoRA config (target modules, rank, alpha, dropout).
6. Trains using transformers Trainer.
7. Saves adapter + tokenizer + lora metadata to output dir.

Important behavior details:
- ROCm safety environment variables are set at startup.
- Quantized load path can use bitsandbytes config.
- Optimizer can be overridden for ROCm stability.
- CPU fallback is blocked unless --allow_cpu is explicitly set.

### Stage F: Modelfile Generation

Targets:
- profile-modelfile
- lora-modelfile

Source implementation:
- build/agent/build.modelfile.py

What it does:
- Generates Ollama Modelfile with runtime parameters and SYSTEM prompt.
- SYSTEM prompt source is .github/copilot-instructions.md.
- If adapter_path is provided, inserts ADAPTER line.

Outputs:
- do/agent/models/Modelfile.<profile>
- do/agent/models/Modelfile.<profile>.lora

### Stage G: LoRA Merge + GGUF Export

Target:
- lora-export-gguf

Source implementation:
- build/agent/build.lora_export_gguf.py

What it does:
1. Loads base HF model + adapter.
2. Attaches LoRA adapter with PEFT.
3. Merges and unloads adapter into base weights.
4. Saves merged HF model to transient merged dir.
5. Uses llama.cpp convert_hf_to_gguf.py to emit GGUF with configurable outtype.
6. Cleans merged dir by default unless LOTR_LORA_EXPORT_KEEP_MERGED=1.

GGUF outtype control:
- Controlled by make variable LORA_GGUF_OUTTYPE.
- Current default: q4_k_m.
- Passed through to exporter as --outtype and then to llama.cpp converter.

llama.cpp source/cache behavior:
- Clones https://github.com/ggerganov/llama.cpp.git only if LLAMA_CPP_DIR does not exist.
- Reuses cached clone on subsequent runs.

Current CPU/GPU export mode behavior:
- Default path is CPU-only merge unless LOTR_LORA_EXPORT_USE_CUDA=1 is set.
- CUDA path uses device_map auto + max_memory + offload folder.

### Stage H: Ollama Installation

Targets:
- ollama-install-<base>
- ollama-install-agentic
- ollama-install-lora

Behavior summary:
- Chooses configured OLLAMA_HOST when reachable.
- Falls back to local daemon when host is not reachable.
- LoRA install path now installs from GGUF artifact (not adapter import path).

## 7) Caching, Reuse, and Rebuild Triggers

### In place today

1. LoRA retrain cache gate
- Deterministic fingerprint skip in lora-train.

2. Package/cache reuse
- pip, HF, and Torch caches rooted under build/docker/cache.
- Existing venv reused unless explicit recreation flag is set.

3. llama.cpp clone reuse
- clone only if LLAMA_CPP_DIR missing.

### Not fully gated today

1. GGUF export rebuild gate
- lora-export-gguf currently runs exporter each invocation.
- There is no export fingerprint skip gate analogous to lora-train yet.

2. HF fetch behavior during export
- Export script uses AutoModelForCausalLM.from_pretrained and may fetch shards if not locally cached in the runtime environment.

## 8) Commands You Will Actually Run

From host, through dev container:

Build full workflow:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agent_build"

Build agentic profile only:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agentic_build AGENT_PROFILE=rx7900xtx-agentic AGENT_MODEL_CONFIG=qwen25-coder-14b"

Build LoRA path only:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile lora_build AGENT_PROFILE=rx7900xtx-agentic AGENT_MODEL_CONFIG=qwen25-coder-14b"

Export LoRA to GGUF only:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile lora-export-gguf AGENT_PROFILE=rx7900xtx-agentic AGENT_MODEL_CONFIG=qwen25-coder-14b"

Export LoRA to GGUF with explicit outtype override:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile lora-export-gguf AGENT_PROFILE=rx7900xtx-agentic AGENT_MODEL_CONFIG=qwen25-coder-14b LORA_GGUF_OUTTYPE=q4_k_m"

Example alternate outtypes (if supported by your converter/runtime):
- q5_k_m
- q6_k
- f16

Install LoRA GGUF into Ollama only:
- PowerShell -ExecutionPolicy Bypass -File build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile ollama-install-lora AGENT_PROFILE=rx7900xtx-agentic AGENT_MODEL_CONFIG=qwen25-coder-14b"

## 9) Required External Dependencies

Declared in build/agent/requirements-lora.txt:
- accelerate>=0.34.0
- bitsandbytes>=0.43.0
- datasets>=2.21.0
- peft>=0.12.0
- transformers>=4.44.0,<5.0.0
- trl>=0.10.1

Also used by export path (installed in target if missing):
- sentencepiece
- protobuf
- gguf

Toolchain/runtime prerequisites:
- Working dev container image with Python and ROCm userland for AMD path.
- Ollama available at configured host or local daemon fallback path.

## 10) Troubleshooting by Failure Point

1. No adapter directory for export
- Error from lora-export-gguf means LoRA training output missing.
- Verify do/agent/models/lora/<profile>/ contains adapter artifacts.

2. PEFT/Accelerate offload dispatch errors
- These occur during adapter attach in build.lora_export_gguf.py.
- Check CUDA/offload env and compatibility between peft/accelerate/transformers versions.

3. Very slow "Fetching N files" during export
- Indicates HF shard downloads from remote.
- Ensure persistent cache location in the active runtime and avoid cache-clearing targets.

4. ROCm quantized training instability
- See guardrails and overrides in build.finetune.py.
- Start with qwen25-coder-7b model config if 14b path is unstable.

5. ollama create failures on LoRA install
- inspect do/agent/models/ollama-lora-serve.log when local daemon fallback is used.

## 11) Source Material Index (Quick Navigation)

Core orchestration:
- build/agent/agent.mk
- build/makefiles/common.mk

Corpus generation:
- build/agent/build.train.py

LoRA train and metadata:
- build/agent/build.finetune.py
- build/agent/build.lora_fingerprint.py
- build/agent/requirements-lora.txt

Runtime/model resolution:
- build/agent/model_config.py
- build/agent/profiles/rx7900xtx-agentic.json
- build/agent/models/qwen25-coder-14b.json
- build/agent/models/qwen25-coder-7b.json
- build/agent/models/qwen3-30b-a3b-moe.json

Modelfile generation and policy prompt:
- build/agent/build.modelfile.py
- .github/copilot-instructions.md

LoRA export:
- build/agent/build.lora_export_gguf.py

Docker execution contract:
- build/docker/docker-spec.md

## 12) Current Implementation Notes

- The base quantize/optimize scripts are currently placeholders and produce scaffold artifacts.
- The LoRA path is the main implemented local specialization pipeline.
- LoRA training has fingerprint-based skip; GGUF export does not yet have equivalent fingerprint skip logic.
- Export defaults to CPU-only merge unless LOTR_LORA_EXPORT_USE_CUDA=1 is set.
