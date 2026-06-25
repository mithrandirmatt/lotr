# Active and Completed Tasks

Last updated: 2026-06-22

## CRITICAL TASKS IN PROGRESS

### CONFIG-LLM-8K-CONTEXT — Expand LoRA training context from 1K to 8K tokens
- **Status**: IN-PROGRESS
- **Blocker**: Requires test validation on 7900 XTX
- **Steps**:
  - [x] Step 1: Updated `max_seq_length` in profile from 1024 → 8192
  - [x] Step 2: Adjusted `grad_accum` from 16 → 8 (effective batch)
  - [x] Step 3: Set `device_map` to "cuda" (explicit GPU allocation)
  - [x] Step 4: Disabled quantization, enabled gradient checkpointing
  - [x] Step 5: Updated optimizer to `adamw_8bit_rocm` (ROCm-native)
  - [ ] Step 6: Test training startup (verify VRAM allocation, no OOM)
  - [ ] Step 7: Verify training logs show >80% VRAM usage
  - [ ] Step 8: Run full training epoch on small dataset
- **Expected completion**: 2026-06-22T22:00
- **Verification command**:
  ```bash
  ./build/docker/docker.ps1 exec "cd /workspace && python build/agent/build.train.py --model qwen25-coder-7b --quantization Q5_K_M --data_dir build/agent/data --profile rx7900xtx-agentic 2>&1 | tee training.log"
  # Check logs for: "VRAM utilization", "seq_length: 8192", "grad_accum: 8"
  ```
- **Rollback**: `git checkout build/agent/profiles/rx7900xtx-agentic.json build/agent/models/qwen25-coder-7b.json`
- **Files modified**:
  - [rx7900xtx-agentic.json](build/agent/profiles/rx7900xtx-agentic.json)
  - [qwen25-coder-7b.json](build/agent/models/qwen25-coder-7b.json)

### CONFIG-GPU-VRAM-RAM — Force LLM training to VRAM not RAM
- **Status**: IN-PROGRESS (part of above task)
- **Changes made**:
  - `device_map: "auto"` → `device_map: "cuda"` (forces GPU allocation, blocks CPU fallback)
  - `load_in_4bit: true` → `false` (disable quantization that forces RAM staging)
  - `gradient_checkpointing: true` (reduces VRAM peak by ~30%)
  - `torch_dtype: "float16"` (better ROCm support than float32)
- **Expected VRAM profile**:
  - Model weights: ~13-14 GB (7B params at fp16)
  - Activations + gradients: ~6-8 GB (with gradient checkpointing)
  - Total: ~20-22 GB (leaving 2-4 GB headroom on 24GB VRAM)
- **Success indicator**: `rocm-smi` shows >80% VRAM in use during training, RAM usage minimal

### CONFIG-TASK-VERIFICATION — Define task verification workflow
- **Status**: COMPLETED (2026-06-22T18:30)
- **Created**:
  - [workflow-task-verification.md](.github/agent/workflows/workflow-task-verification.md)
  - Task definition format with acceptance criteria and rollback
  - Verification checklist and failure handling procedures
  - Artifact retention policy (30 days)
- **Usage**:
  - All new tasks must follow this format
  - Reference example: CONFIG-CTX-EXPAND-001 in verification workflow doc
  - Agents should fail fast if pre_check fails

## PENDING TASKS (Waiting on Above)

### CONFIG-INFERENCE-CTX — Match inference context to training
- **Status**: QUEUED (waits on CONFIG-LLM-8K-CONTEXT)
- **Action**: Once training works with 8K, optional increase runtime `num_ctx` from 64K to 128K if VRAM permits
- **Note**: Inference already has 64K context, which exceeds training 8K; this is OK (training context is not a ceiling for inference)

## COMPLETED (This Session)

### WORKFLOW-TASK-VERIFY-001 — Create task verification framework
- **Completed**: 2026-06-22T18:30
- **Details**: Workflow document created with:
  - Task definition YAML format
  - Verification checklist
  - Failure handling and rollback procedures
  - Artifact retention policies (30-day minimum)
- **File**: [.github/agent/workflows/workflow-task-verification.md](.github/agent/workflows/workflow-task-verification.md)

## CONTEXT REFERENCE

### Why 8K Context for Training?
- **Previous**: 1024 tokens (very limiting for code samples)
- **New**: 8192 tokens (8x larger, fits more API docs + code examples)
- **Inference**: Remains at 65536 tokens (training context is not a limit for inference)
- **Why not larger?**:
  - Memory: 8K×1 batch + grad checkpointing fits in 24GB VRAM
  - 16K+ would require batch size reduction or CPU offloading (defeats GPU optimization)
  - 8K is sweet spot for LoRA coding task fine-tuning

### Why Disable Quantization During Training?
- **Quantization (4-bit, 8-bit)**: Designed for inference (speed/memory), not training
- **Training needs**: Full precision to compute accurate gradients
- **Solution**: Use full fp16 (half-precision) instead of 4-bit/8-bit
  - Supported by ROCm and modern AMD GPUs
  - Gradient checkpointing reduces memory 30% without quality loss
  - Result: Better training quality than quantized-then-trained models

### VRAM vs RAM Allocation
- **Problem**: With `device_map: "auto"`, PyTorch tries to be "smart" but often falls back to CPU/RAM
- **Solution**: Explicit `device_map: "cuda"` forces VRAM-only allocation, fails fast if insufficient
- **Verification**: Run `rocm-smi` during training; should show >80% VRAM (not RAM swapping)

---

## Verification Steps (Run These)

After making config changes, run in container:

```bash
# Test 1: Confirm config changes
docker exec lotr-server python -c "import json; c=json.load(open('build/agent/profiles/rx7900xtx-agentic.json')); print(f\"Context: {c['lora']['max_seq_length']}, Device: {c['lora']['device_map']}\")"

# Expected output: Context: 8192, Device: cuda

# Test 2: Start training (will OOM or succeed)
docker exec lotr-server bash -c "cd /workspace && python build/agent/build.train.py --model qwen25-coder-7b --quantization Q5_K_M --data_dir build/agent/data --profile rx7900xtx-agentic 2>&1 | tee /tmp/train-startup.log"

# Test 3: Check GPU allocation (run in separate terminal during training)
docker exec lotr-server rocm-smi --showmeminfo

# Expected: GPU memory showing >15GB in use, not system RAM

# Test 4: Full training epoch
docker exec lotr-server python build/agent/build.train.py \
  --model qwen25-coder-7b \
  --quantization Q5_K_M \
  --data_dir build/agent/data \
  --profile rx7900xtx-agentic 2>&1 | tee build/docker/logs/training-full.log
```

## Rollback Instructions

If tests fail, rollback all changes:

```bash
git checkout build/agent/profiles/rx7900xtx-agentic.json build/agent/models/qwen25-coder-7b.json
# Verify rollback:
git diff
```

Then analyze the error log and file a new task with the specific failure mode.
