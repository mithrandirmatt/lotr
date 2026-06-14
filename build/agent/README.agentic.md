# Agentic Local LLM Tuning (RX 7900 XTX)

This guide provides a practical path to get stronger local coding-agent behavior from a 24GB AMD RX 7900 XTX setup.

## Goals

- Improve planning and deep reasoning behavior
- Improve tool-use compliance for Copilot-style workflows
- Improve coding/troubleshooting quality across repo languages

## What This Pipeline Adds

- Hardware/runtime profile: `build/agent/profiles/rx7900xtx-agentic.json`
- Curated corpus generation from repo instructions, skills, and code contexts
- Profile-based Ollama `Modelfile` generation wired to `.github/copilot-instructions.md`

## Build Targets

All commands below are written for the main dev container. From the workspace root on the host, run them through `build/docker/docker.ps1`.

Open an interactive dev-container shell:

```powershell
./build/docker/docker.ps1 run -GpuVariant rocm
```

Build/update the main dev image with ROCm userland first:

```powershell
./build/docker/docker.ps1 build -GpuVariant rocm
```

Run a one-off command in the dev container without starting the app services:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agentic_build"
```

Run a one-off command in the dev container while also booting the usual workspace services:

```powershell
./build/docker/docker.ps1 run -CommandArg "cd /workspace/build && make -f makefile agentic_build"
```

Agent-safe default: use `./build/docker/docker.ps1 exec "..."` for build, test, Python, Node, and make commands so the command runs in the dev container but does not restart the web services or open the browser.

Interactive shell recipe:

```powershell
./build/docker/docker.ps1 run
```

Run the complete roll-up (base + agentic + LoRA) in one command:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agent_build"
```

Optional overrides:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile agentic_build \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_BASE_MODEL=qwen2.5-coder:7b \
  BASE_MODEL=llama3-8b \
  QUANTIZATION=4bit"
```

Install just the profile model into Ollama:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile ollama-install-agentic AGENT_BASE_MODEL=qwen2.5-coder:7b"
```

## Recommended Local Models (7900 XTX)

- Dev-container LoRA default: `qwen2.5-coder:7b`
- Heavier inference-only coding: `qwen2.5-coder:14b`
- Heavier reasoning: `qwen2.5:32b` (lower throughput)
- Use quantized formats that fit VRAM and context needs.

## Opus-like Behavior Strategy

You will get the largest gains by combining:

1. Strong base model for coding/reasoning
2. High-quality system prompt and policy stack
3. Curated repository corpus focused on tooling/workflows
4. Lower-temperature inference defaults for consistency
5. Explicit verification/troubleshooting workflows

This repo currently prepares corpus + runtime profile and installs a policy-aligned model variant.
Full weight fine-tuning (LoRA/SFT/DPO) can be added later on top of this scaffold.

## LoRA Fine-Tuning Pipeline (ROCm)

This repo now includes a practical LoRA stage for local specialization:

- Train adapter: `build/agent/build.finetune.py`
- Generate adapter Modelfile: `build/agent/build.modelfile.py --adapter_path ...`
- Install LoRA model in Ollama: `make -f makefile ollama-install-lora`

Run full LoRA pipeline:

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile lora_build \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_BASE_MODEL=qwen2.5-coder:7b \
  AGENT_HF_BASE_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct"
```

Force ROCm wheel selection for training venv (optional, usually auto-detected):

```powershell
./build/docker/docker.ps1 exec "cd /workspace/build && make -f makefile lora_build \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_TORCH_VARIANT=rocm"
```

Install dependencies for LoRA stage (inside the target):

- `build/agent/requirements-lora.txt`

Notes:

- LoRA quality depends heavily on corpus quality and base model choice.
- The dev-container defaults are intentionally conservative for a single 24GB GPU: 7B base, sequence length 2048, LoRA rank 16, gradient accumulation 16.
- Start with 1 epoch; iterate with better samples before raising epochs.
- Treat 14B LoRA as an opt-in override after validating memory headroom in your container.
- Keep system prompt and tool-policy alignment stable for best agentic behavior.

## Outputs

- Corpus: `do/agent/models/training/rx7900xtx-agentic-corpus.jsonl`
- Metadata: `do/agent/models/training/rx7900xtx-agentic-metadata.json`
- Modelfile: `do/agent/models/Modelfile.rx7900xtx-agentic`
- Ollama model name: `lotr-agentic-rx7900xtx-agentic`
