# Agent Training Guide: Building & Maintaining Agentic LLMs

**Date**: 2026-06-27
**Version**: 1.0
**Audience**: LLM trainers, agent developers, infrastructure engineers

---

## Table of Contents

1. [Introduction](#introduction)
2. [Pre-Training Preparation](#pre-training-preparation)
3. [Training Workflow](#training-workflow)
4. [Configuration & Model Selection](#configuration--model-selection)
5. [Troubleshooting & Debugging](#troubleshooting--debugging)
6. [Performance Optimization](#performance-optimization)
7. [Maintaining Training Quality](#maintaining-training-quality)
8. [Advanced Topics](#advanced-topics)

---

## Introduction

### What This Guide Covers

This guide teaches **how to train agentic LLMs** on project-specific code and guidance to create capable coding agents. It covers:

- Setting up the training environment
- Preparing corpus (training data)
- Running LoRA fine-tuning
- Optimizing for your hardware
- Troubleshooting failures
- Maintaining and iterating on training

### Who Should Read This

- **LLM Infrastructure Owners**: Set up and maintain training pipeline
- **Agent Developers**: Understand what makes agents better
- **Data Curators**: Know how to prepare quality training data
- **Researchers**: Experiment with reasoning frameworks and model configurations

### Prerequisites

- Access to development container (WSL2 + Docker with GPU)
- Familiarity with LLM concepts (fine-tuning, LoRA, quantization)
- Understanding of Python and shell scripting
- 24GB+ GPU VRAM (or adjust batch sizes for smaller GPUs)

---

## Pre-Training Preparation

### Step 1: Understand Your Goal

**Question**: What do you want the agent to be better at?

Common goals and training approaches:

| Goal | Training Data Focus | Model Size | Expected Improvement |
|------|-------------------|-----------|----------------------|
| Better coding | Code examples, patterns, best practices | 7-14B | 15-30% quality lift |
| Better planning | Architecture docs, design decisions, specs | 14-30B | 20-40% planning quality |
| Better troubleshooting | Error patterns, root-cause analysis, debugging | 7-14B | 25-35% root-cause detection |
| Better tool use | Tool examples, error recovery, fallbacks | 7-14B | 30-40% tool compliance |
| Better reasoning | Multi-step analysis, trade-off discussions, edge cases | 14-30B | 20-50% reasoning depth |

### Step 2: Assess Your Hardware

**Your System**:
- GPU: AMD RX 7900 XTX (24GB VRAM)
- Memory ceiling: ~20GB safe, ~18GB risky, >22GB likely OOM

**Implications**:
- Batch size: 1 (large models can't fit larger batches)
- Gradient accumulation: 6-8 (effective batch size 6-8)
- Model choices: 7B/14B for dense models, 30B for MoE (lower VRAM with dynamic routing)
- Inference quantization: Q5_K_M is ideal (20% speedup vs Q6_K_M, minimal quality loss)
- Training: Full precision (fp16) with gradient checkpointing

**Memory Calculation**:
```
Model 14B in fp16: ~28GB (base 14, but bfloat16 = 28GB)
+ Gradients + Activations: ~28GB
+ Optimizer state (AdamW): ~28GB
+ Overhead: ~2GB
Total: ~86GB for training

But with LoRA (low-rank adaptation):
- Base model: 14GB (on GPU)
- LoRA adapters: <1GB
- Gradients (only adapters): <1GB
- Activations: ~14GB
- Overhead: ~2GB
Total: ~32GB (still tight on 24GB!)

Solution: Gradient checkpointing + batch size 1 + grad accum 8
```

### Step 3: Prepare Your Corpus

**What is a Corpus?**

A corpus is a collection of text examples used to teach the model new patterns. Quality matters more than quantity.

**Corpus Sources** (what to include):

```
High Priority (Must Include):
├─ Guidance documents (.github/agent/*.md)
│  └─ How you want agent to behave: reasoning, tool use, planning
├─ Project instructions (.github/copilot-instructions.md)
│  └─ Project-specific patterns and conventions
├─ Workflow specifications (workflow-*.md)
│  └─ Step-by-step task patterns
└─ Build/configuration scripts
   └─ How your project is organized and built

Medium Priority (Should Include):
├─ Reference code (server, frontend, game logic)
│  └─ Examples of "good" code in your project
├─ Documentation (README.md, architecture docs)
│  └─ High-level patterns and design decisions
└─ Skills documentation (reusable patterns)

Lower Priority (Optional):
├─ Tests (if demonstrating edge cases)
├─ Configuration (yaml, json)
└─ Minimal documentation from external sources
```

**Corpus Size Guidelines**:
- Minimum: 500-1000 samples (5-10MB text)
- Target: 2000-5000 samples (20-50MB text)
- Maximum: 10,000+ samples (100MB+ text, requires more training time)

**For LOTR Project**:
- Current corpus: 759 samples, 7.5MB, ~1.95M tokens
- Recommendation: Add 200-300 more samples to reach 1000 (good balance)
- Focus areas: Troubleshooting examples, architecture decisions, tool use patterns

### Step 4: Configure Your Training Environment

**Profile Configuration** (`build/agent/profiles/rx7900xtx-agentic.json`):

```json
{
  "gpu": {
    "name": "AMD Radeon RX 7900 XTX",
    "vram_gb": 24
  },
  "runtime": {
    "num_ctx": 131072,        // 128K context for inference
    "temperature": 0.2,        // Deterministic (good for coding)
    "top_p": 0.9
  },
  "lora": {
    "batch_size": 1,           // Don't increase, will OOM
    "grad_accum": 8,           // Effective batch size 8
    "learning_rate": 0.0001,   // Standard for fine-tuning
    "max_seq_length": 8192,    // 8K for training (vs 128K inference)
    "gradient_checkpointing": true,  // CRITICAL for memory
    "lora_r": 16,              // Rank (16-32 typical, higher=more params)
    "lora_alpha": 32,          // Alpha (typically 2x rank)
    "target_modules": [        // Which layers to fine-tune
      "q_proj", "k_proj", "v_proj", "o_proj",
      "gate_proj", "up_proj", "down_proj"
    ]
  }
}
```

**Key Parameters Explained**:
- `grad_accum`: Simulate larger batch without more VRAM (8 = like batch size 8)
- `lora_r`: Adapter rank (higher = more parameters but more VRAM, 16 is sweet spot)
- `max_seq_length`: Training sequence limit (8K saves memory vs 128K inference)
- `gradient_checkpointing`: Trade compute for memory (saves ~40% VRAM, 10% slower)

---

## Training Workflow

### Phase 1: Generate Corpus

**Purpose**: Collect and format training data from repository.

**Command**:
```bash
cd /workspace/build
make prepare-corpus \
  AGENT_PROFILE=rx7900xtx-agentic \
  BASE_MODEL=llama3-8b \
  QUANTIZATION=4bit
```

**What Happens**:
1. Reads profile include_globs (select files to use)
2. Reads profile exclude_globs (skip files)
3. Collects each file into training sample format
4. Validates corpus (sample count, size, token estimates)
5. Outputs JSONL corpus + metadata JSON

**Output Files**:
```
do/agent/models/training/
├─ rx7900xtx-agentic-corpus.jsonl  (actual training data)
├─ rx7900xtx-agentic-metadata.json (statistics)
└─ lotr-llama3-8b-4bit.gguf        (placeholder, for reference)
```

**Example Metadata Output**:
```json
{
  "model": "llama3-8b",
  "quantization": "4bit",
  "profile": "rx7900xtx-agentic",
  "samples": 759,
  "total_bytes": 7818302,
  "avg_bytes_per_sample": 10300,
  "min_bytes": 190,
  "max_bytes": 224669,
  "estimated_tokens": 1954575,
  "warnings": "Found 9 samples with extreme sizes (< 100 bytes or > 100KB)"
}
```

**Troubleshooting**:
- If corpus empty: Check profile include_globs (patterns may not match files)
- If samples too large: Extreme sizes listed in metadata, consider filtering
- If estimates wrong: Token count uses 1 token ≈ 4 chars (adjust if needed)

### Phase 2: Compute Training Fingerprint

**Purpose**: Hash training inputs to enable caching (skip if nothing changed).

**What Gets Hashed**:
- Profile configuration (lora_r, batch_size, etc.)
- Corpus content (all training data)
- LoRA requirements (accelerate, peft, transformers versions)
- Base model name and quantization
- Training script (build.finetune.py)

**Command**:
```bash
make lora-fingerprint \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_MODEL_CONFIG=qwen25-coder-14b
```

**Output**:
```
do/agent/models/cache/rx7900xtx-agentic/lora-train.sha256.new
Contents: 64-character hex string (SHA256 hash)
```

**Caching Logic**:
```
If (new hash == old hash):
  → SKIP TRAINING (reuse previous adapter weights)
  → Save 30-60 minutes
Else:
  → TRAIN (new corpus or config)
  → Update hash file
```

### Phase 3: Estimate Memory Requirements

**Purpose**: Predict GPU memory usage before training starts.

**What Gets Estimated**:
- Model size (GB in precision)
- Quantization adjustments (4-bit, 8-bit)
- Batch size × grad_accum overhead
- Optimizer state (2× model size for AdamW)
- Activation memory (2× model size typical)

**Memory Estimation Formula**:

```
estimated_vram_gb = model_size_gb
                  + (model_size_gb × 2)              [optimizer state]
                  + (model_size_gb × 0.3)            [activations w/ checkpointing]
                  + (batch_size × grad_accum × 0.5)  [batch overhead]
                  + 1.0                              [Python/framework overhead]

Example (Qwen 14B fp16):
= 28 GB (base model in fp16)
+ 56 GB (optimizer: 2×)
+ 8.4 GB (activations: 0.3×)
+ 0.5 GB (batch 1 × accum 8)
+ 1.0 GB (overhead)
= 94 GB (TOO LARGE!)

But with gradient checkpointing:
= 28 GB (base)
+ 56 GB (optimizer)
+ 2.8 GB (activations: 0.1× with checkpointing)
+ 0.5 GB (batch)
+ 1.0 GB (overhead)
= 88 GB (still too large!)

Solution: Use LoRA (only fine-tune adapters, not full model)
= 14 GB (quantized base model)
+ 1 GB (LoRA adapters)
+ 5 GB (optimizer state for adapters only)
+ 2 GB (activations)
+ 1 GB (overhead)
= 23 GB (fits on 24GB GPU!)
```

**Output Example**:
```
[INFO] Training Configuration:
  Base model: Qwen/Qwen2.5-Coder-7B-Instruct
  Epochs: 1.0, Batch size: 1, Grad accum: 8
  Learning rate: 0.0001, Warmup: 0.03
  Est. GPU memory: 49.0 GB
  ⚠️  Estimated 49.0GB memory needed (24GB GPU, margin thin; may OOM)
```

**Interpretation**:
- `< 18GB`: Safe (6GB buffer)
- `18-20GB`: Risky (thin margin)
- `> 20GB`: Likely OOM (take action)

**Actions if Over Budget**:
1. Increase gradient_checkpointing (saves ~30% VRAM)
2. Decrease grad_accum (1 × effective batch = 1, but slower training)
3. Use smaller model (7B instead of 14B)
4. Use 4-bit quantization instead of 8-bit
5. Increase max_seq_length reduction (8K→4K saves ~25%)

### Phase 4: Run Training

**Command**:
```bash
make lora-train \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_MODEL_CONFIG=qwen25-coder-14b
```

**Full Output Sequence**:
```
1. Corpus preparation (if first run)
2. Fingerprinting (compute/compare hash)
3. Cache check (skip if match)
4. Memory estimation (warn if risky)
5. Model loading (download + quantize)
6. LoRA adapter creation
7. Training loop (epoch 1, multiple steps)
   ├─ Progress bar (steps 0/95)
   ├─ Checkpoints (every 47 steps)
   └─ Metrics (loss, learning_rate)
8. Finalization (save adapter weights)
```

**Understanding Training Output**:

```
trainable params: 40,370,176 || all params: 7,655,986,688 || trainable%: 0.5273
→ Only 0.5% of params are trainable (excellent, prevents overfitting)

Map: 100%|██████████| 759/759 [00:00<00:00, 897.59 examples/s]
→ Loading training data into memory (fast, indicates good dataset loading)

Epoch 1: |████████████████████| 100%
→ Training progress (multiple passes if epochs > 1)
```

**Typical Training Time**:
- Qwen 7B: 30-45 minutes (fewer parameters)
- Qwen 14B: 60-90 minutes (more parameters)
- Depends on: GPU, corpus size, grad_accum, gradient_checkpointing

**Output Location**:
```
do/agent/models/lora/rx7900xtx-agentic/
├─ adapter_model.safetensors  (trained weights: 155MB)
├─ adapter_config.json        (LoRA configuration)
├─ training_args.bin          (training hyperparameters)
├─ trainer_state.json         (training metadata)
└─ checkpoint-N/              (intermediate checkpoints)
```

### Phase 5: Export Model for Inference

**Purpose**: Merge trained adapter into base model and export as GGUF.

**Command**:
```bash
make lora-export-gguf \
  AGENT_PROFILE=rx7900xtx-agentic \
  AGENT_MODEL_CONFIG=qwen25-coder-14b
```

**What Happens**:
1. Load base model (Qwen 14B from HF)
2. Load trained LoRA adapter
3. Merge adapters into base weights
4. Quantize to target level (Q5_K_M for inference)
5. Export as GGUF format (Ollama-compatible)

**Output**:
```
do/agent/models/lotr-qwen25-coder-14b-agentic.gguf (6-8GB)
→ Ready for Ollama deployment
→ Can be used for inference with reduced memory
```

**Key Metrics**:
- **File size**: ~20% of full model (GGUF quantization)
- **Inference speed**: 2-3x faster than full precision
- **Quality**: Minimal loss with Q5_K_M (95-97% of full precision quality)

---

## Configuration & Model Selection

### Model Comparison

| Model | Size | VRAM | Use Case | Training Time | Reasoning Quality |
|-------|------|------|----------|---------------|------------------|
| Qwen 2.5 Coder 7B | 7B | ~8GB | Balanced tasks, quick iteration | 30-45 min | Good |
| Qwen 2.5 Coder 14B | 14B | ~16GB | Complex problems, planning | 60-90 min | Very Good |
| Qwen 3 30B MOE | 30B | ~18GB (dynamic) | Expert reasoning, all tasks | 90-120 min | Excellent |
| Opus 1.5 | 0.88B | 2GB | Thinking/reasoning layer | N/A | Very Good (targeted) |

### When to Use Which

**Use Qwen 7B When**:
- Iterating quickly (short feedback loops)
- Simple coding tasks
- Limited time (training+inference faster)
- Testing new corpus changes

**Use Qwen 14B When**:
- Deploying to production
- Complex planning or debugging
- Need better multi-step reasoning
- Trade-off: 2× training time acceptable

**Use Qwen 30B MOE When**:
- Need expert-level reasoning
- Handling very complex tasks
- Sufficient GPU memory available
- Willing to accept 2× training time

**Use Opus Thinking Pipeline When**:
- Multi-stage reasoning required
- Root-cause analysis critical
- Time-sensitive but accuracy matters more
- Fallback to faster model acceptable

### LoRA Configuration Tuning

**Rank (r) Parameter**:
- Default: 16 (good balance)
- Range: 4-64
- Higher rank = more capacity but more VRAM
- Recommendations:
  - 4-8: Lightweight (quick iteration, less performance)
  - 16: **Recommended default** (balance)
  - 32-64: High capacity (more VRAM, marginal quality gain)

**Alpha Parameter**:
- Default: 2×rank (so rank 16 → alpha 32)
- Effective learning rate: alpha / rank
- With default: 32 / 16 = 2.0 (good scaling)
- Keep ratio 2:1 for consistent behavior

**Learning Rate**:
- Default: 0.0001
- Range: 0.00001 - 0.0001 for fine-tuning
- If loss doesn't decrease: increase LR (try 0.00015, 0.0002)
- If loss unstable: decrease LR (try 0.00005)

**Batch Size & Gradient Accumulation**:
- Batch size = per-device batch (keep at 1 for VRAM)
- Grad accum = effective batch = batch × accum
- Effective batch 1-4: Noisy training, quick iteration
- Effective batch 8: **Recommended** (good gradient stability)
- Effective batch 16+: Smoother training, more VRAM

**Sequence Length**:
- Default: 8192 (8K tokens)
- Inference: 131072 (128K tokens)
- Training at 8K saves 4× memory vs 128K
- Adjustment: If corpus has long samples (>8K):
  - Set max_seq_length to median + 50%
  - Or accept truncation (loss of long-context examples)

---

## Troubleshooting & Debugging

### Issue 1: Out of Memory (OOM)

**Symptom**: Training crashes with `CUDA error: out of memory` or `hipErrorOutOfMemory`

**Diagnosis**:
```bash
# Check GPU memory before training
nvidia-smi  # (NVIDIA) or rocm-smi (AMD)

# If memory is available but training still OOMs:
# → Problem is training memory calculation, not system
```

**Solutions** (in order of try):

1. **Check Memory Estimation Output**
   - If estimate showed > 20GB, that was the warning!
   - Expected OOM, need to reduce memory usage

2. **Enable Gradient Checkpointing** (saves ~30% VRAM)
   ```json
   {
     "lora": {
       "gradient_checkpointing": true
     }
   }
   ```

3. **Reduce Gradient Accumulation** (trades quality for VRAM)
   ```json
   {
     "lora": {
       "grad_accum": 4  // was 8, now 4
     }
   }
   ```

4. **Reduce Sequence Length** (saves 25% per 2K reduction)
   ```json
   {
     "lora": {
       "max_seq_length": 4096  // was 8192, now 4K
     }
   }
   ```

5. **Switch to Smaller Model**
   ```bash
   make lora-train \
     AGENT_MODEL_CONFIG=qwen25-coder-7b  # was 14b
   ```

6. **Use 4-bit Quantization** (saves ~50% model memory)
   ```bash
   make lora-train \
     QUANTIZATION=4bit  # was none
   ```

**After Adjustment**: Re-run memory estimation to confirm new budget.

### Issue 2: Training Fingerprint Not Updating

**Symptom**: Made changes to profile/corpus, but training is skipped with "cache unchanged"

**Diagnosis**:
```bash
# Check fingerprints
cat do/agent/models/cache/rx7900xtx-agentic/lora-train.sha256.new
cat do/agent/models/cache/rx7900xtx-agentic/lora-train.sha256

# If identical, cache is correct (nothing changed)
# If different, but training skipped: bug in logic
```

**Solution**: Clear fingerprint cache to force retrain

```bash
rm do/agent/models/cache/rx7900xtx-agentic/lora-train.sha256.new
rm do/agent/models/cache/rx7900xtx-agentic/lora-train.sha256

# Re-run training
make lora-train ...
```

**Why Fingerprints Are Important**:
- Detects actual changes (don't retrain if nothing changed)
- Saves 30-60 minutes per skipped training
- Once fingerprint matches, adapter weights are valid

### Issue 3: Corpus Empty or Very Small

**Symptom**: Corpus has 0-10 samples instead of expected 700+

**Diagnosis**:
```bash
# Check profile globs
cat build/agent/profiles/rx7900xtx-agentic.json | grep -A 10 include_globs
cat build/agent/profiles/rx7900xtx-agentic.json | grep -A 10 exclude_globs

# Check if files actually exist
ls -la .github/agent/
ls -la build/agent/
```

**Common Causes**:
1. **Glob patterns don't match files**
   - `.github/agent/**/*.md` won't match if files are `.markdown` or `.txt`
   - Solution: Fix glob patterns in profile

2. **Exclude globs are too aggressive**
   - `**/build/**` might exclude files you want
   - Solution: Review exclude patterns

3. **Files are being excluded by other rules**
   - Large binary files (images, etc.)
   - Solution: Add to corpus manually if needed

**Solution**: Review and adjust globs in profile:
```json
{
  "include_globs": [
    ".github/agent/**/*.md",     // Agent guidance
    "assets/reference/agent/**/*.md",  // Docs
    "build/agent/**/*.py",       // Training scripts
    "build/agent/**/*.json"      // Configs
  ],
  "exclude_globs": [
    "**/.git/**",
    "**/node_modules/**",
    "**/*.png",
    "**/*.jpg"
  ]
}
```

### Issue 4: Training Loss Not Decreasing

**Symptom**: Loss plateau (not decreasing over time)

**Diagnosis**:
```
Epoch 1: Loss 2.5 → 2.4 → 2.4 → 2.4 (stuck)
```

**Common Causes**:

1. **Learning rate too small**
   - Adjust: `0.0001 → 0.0002` (double it)

2. **Learning rate too large**
   - Loss will spike/oscillate (not plateau)
   - Adjust: `0.0001 → 0.00005` (halve it)

3. **Corpus quality issues**
   - If corpus has lots of noise (extreme sizes, etc.)
   - Solution: Review metadata, consider filtering samples

4. **Model is memorizing rather than learning**
   - Happens with small corpus + high LR
   - Solution: Lower LR or increase corpus size

5. **Corpus is too similar to base model training**
   - If examples already in base model training data
   - Solution: Add more novel/different examples

**Solution**: Adjust learning rate and retry:
```bash
# Edit profile
vim build/agent/profiles/rx7900xtx-agentic.json
# Change: "learning_rate": 0.0002

# Retrain
make lora-train AGENT_MODEL_CONFIG=qwen25-coder-14b
```

### Issue 5: Model Output Quality Worse After Training

**Symptom**: Fine-tuned model produces worse results than base model

**Causes**:

1. **Corpus contains bad examples**
   - Solution: Review and clean corpus, remove problematic samples

2. **Training overfit** (corpus too small, epochs too high)
   - Increase corpus size, reduce epochs
   - Use more aggressive LoRA dropout (0.1-0.2)

3. **Learning rate too high**
   - Destabilizes weights
   - Reduce learning rate 0.0001 → 0.00005

4. **Training not converged**
   - Decrease learning rate, increase epochs (though 1 epoch standard)

**Diagnostic**:
```bash
# Compare outputs
echo "What is a for loop?" | ollama run base-model
echo "What is a for loop?" | ollama run fine-tuned-model

# If fine-tuned is worse:
# → Likely training issue, not corpus issue
# → Reduce LR, check loss behavior
```

---

## Performance Optimization

### Caching Strategy

**Fingerprinting Benefits**:
- **Corpus regeneration**: 5 min saved if unchanged
- **Training**: 30-60 min saved if inputs unchanged
- **GGUF export**: 10-30 min saved if adapter unchanged

**Current Implementation**:
- corpus hash: profile + selection rules
- training hash: corpus + profile + finetune script + configs
- export hash: adapter + base model + quantization

**Recommendation**: Check cache effectiveness monthly
```bash
# See cache size and frequency
du -sh do/agent/models/cache/
find do/agent/models/cache -name "*.sha256" -exec wc -l {} \;
```

### Parallelization Opportunities

**Currently Sequential**:
1. Corpus generation
2. Fingerprinting
3. Training
4. Export

**Could Parallelize**:
- Multiple model configurations (7B vs 14B) on separate GPUs
- Multiple corpora (different profiles) in sequence

**Not Worth Parallelizing**:
- Steps within a single training run (dependencies)
- Fine-tuning with single GPU (no parallelization benefit)

### Batch Processing

**Effective Batching**:
- Multiple model configs in one session (CPU cache, HF hub downloads)
- Multiple corpus variations back-to-back (warm GPU)

**Example Workflow**:
```bash
# Process multiple models in sequence
make prepare-corpus
make lora-train AGENT_MODEL_CONFIG=qwen25-coder-7b
make lora-export-gguf AGENT_MODEL_CONFIG=qwen25-coder-7b

make lora-train AGENT_MODEL_CONFIG=qwen25-coder-14b
make lora-export-gguf AGENT_MODEL_CONFIG=qwen25-coder-14b

# Result: 2 fine-tuned models ready for deployment
```

---

## Maintaining Training Quality

### Quality Checklist

**Before Each Training Run**:
- [ ] Corpus verified (sample count, size reasonable)
- [ ] Memory estimation reviewed (warning level acceptable)
- [ ] Fingerprints understood (skipping expected vs. not)
- [ ] Learning rate appropriate for goal
- [ ] LoRA rank tuned for model size

**During Training**:
- [ ] Monitor loss (should decrease initially)
- [ ] Monitor GPU memory (should stay < 23GB)
- [ ] Check ETA vs. expected time

**After Training**:
- [ ] Spot-check output quality
- [ ] Compare to previous model (better or worse?)
- [ ] Log any anomalies
- [ ] Document configuration and results

### Corpus Maintenance

**Monthly Review**:
1. Check corpus composition
2. Identify underrepresented areas
3. Add new examples from recent work
4. Remove outdated/incorrect examples
5. Verify sample distribution (not too many similar)

**Quarterly Refresh**:
1. Add seasonal new guidance
2. Include resolved issues (troubleshooting examples)
3. Update architecture decision records
4. Expand tool use examples

**Annual Audit**:
1. Full corpus review
2. Remove ~10% oldest samples
3. Add ~20% new samples
4. Retrain and benchmark

### Metrics to Track

**Training Metrics**:
- Loss over time (should decrease)
- Learning rate changes
- Training time per epoch
- Memory usage peak

**Quality Metrics** (after training):
- Output length distribution
- Tool compliance (% of outputs using correct tools)
- Task success rate (if you have test set)
- Reasoning quality (subjective, but important)

**Performance Metrics**:
- Inference speed (tokens/sec with Q5_K_M)
- Memory footprint (vs. base model)
- Accuracy vs. base model

---

## Advanced Topics

### Multi-Model Orchestration

**Goal**: Use multiple models for different tasks.

**Strategy**:
```
Task Router
├─ Complex reasoning → Qwen 14B + Opus thinking
├─ Simple implementation → Qwen 7B
├─ Performance-sensitive → Qwen 7B (faster)
└─ High-stakes decisions → Qwen 30B MOE

Benefits:
├─ Speed for simple tasks (use 7B)
├─ Quality for complex tasks (use 14B+)
├─ Cost-effective (smaller models for easier problems)
└─ Flexibility (upgrade task-specific models independently)
```

**Implementation**:
1. Train multiple model configs
2. Create router (decision logic for task→model)
3. Implement inference pipeline with model selection
4. Log task type → model selection for analytics

### Iterative Improvement Loop

**Continuous Learning**:
```
1. Deploy model (v1)
2. Collect failure cases (what went wrong?)
3. Analyze failures (patterns?)
4. Add failure cases to training corpus
5. Retrain model (v2)
6. Benchmark v2 vs. v1
7. Deploy v2 if better
8. Repeat step 2
```

**Challenges**:
- Need systematic failure logging
- Privacy/safety concerns with using real logs
- Careful sampling (don't bias toward rare cases)

**Opportunities**:
- Monthly improvement cycles
- Compound improvements over time
- Data-driven iteration

### Curriculum Learning

**Idea**: Train on easy examples first, then harder ones.

**Implementation**:
```
Epoch 1: Train on simple, short examples
Epoch 2: Mix in medium complexity
Epoch 3: Include hard, long examples

Benefits:
- Faster initial convergence
- Better final results (studies show 10-20% improvement)
- More stable training

Drawback:
- Requires manual example complexity scoring
- More epochs needed (can be slow)
```

**For LOTR**:
- Scoring function: len(sample) + num_dependencies
- Sort corpus by complexity
- Shuffle slightly per epoch (not totally sequential)

### Domain-Specific Fine-Tuning

**Idea**: Train specialized models for specific domains.

**Options**:
1. **Debugging Agent**: LoRA trained heavily on troubleshooting examples
2. **Architecture Agent**: LoRA trained on design decisions, trade-offs
3. **Testing Agent**: LoRA trained on test patterns, edge cases
4. **DevOps Agent**: LoRA trained on deployment, infrastructure

**Implementation**:
```
Create corpus per domain:
├─ profiles/rx7900xtx-debugging.json
│  └─ include_globs: troubleshooting examples, error patterns
├─ profiles/rx7900xtx-architecture.json
│  └─ include_globs: design docs, ADRs, specs
├─ profiles/rx7900xtx-testing.json
│  └─ include_globs: test code, test patterns, QA docs
└─ profiles/rx7900xtx-devops.json
   └─ include_globs: deployment, infrastructure, config

Train each:
make lora-train AGENT_PROFILE=rx7900xtx-debugging
make lora-train AGENT_PROFILE=rx7900xtx-architecture
# ... etc

Deploy with router:
Task → Router → Specialized Agent
```

---

## Conclusion

This guide provides everything needed to **train and maintain agentic LLMs** on your project-specific code and guidance. Key takeaways:

1. **Preparation is critical**: Understand your goal, hardware, corpus before training
2. **Caching saves time**: Fingerprinting prevents 30-60 min wasted runs
3. **Configuration matters**: Right LR, rank, batch size dramatically affects results
4. **Monitoring prevents disasters**: Memory estimation and loss curves catch problems early
5. **Iteration improves quality**: Monthly corpus updates, quarterly audits, annual refreshes

The training pipeline is **designed for continuous improvement**: add better examples, retrain monthly, measure quality, repeat.

---

**End of Document**
Document Version: 1.0 | Last Updated: 2026-06-27
