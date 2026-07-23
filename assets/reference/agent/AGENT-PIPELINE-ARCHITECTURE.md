# Comprehensive Agent Pipeline Architecture

**Date**: 2026-06-27
**Version**: 1.0
**Scope**: Complete LOTR agent system for agentic coding assistance

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Training Infrastructure](#training-infrastructure)
4. [Reasoning & Deep Thinking Frameworks](#reasoning--deep-thinking-frameworks)
5. [Agent Capabilities & Domains](#agent-capabilities--domains)
6. [Guidance & Instruction Layers](#guidance--instruction-layers)
7. [Corpus & Knowledge Base](#corpus--knowledge-base)
8. [Execution Context & Runtimes](#execution-context--runtimes)
9. [Performance Optimization](#performance-optimization)
10. [Gaps & Improvement Roadmap](#gaps--improvement-roadmap)

---

## Executive Summary

The LOTR agent pipeline is a **multi-layered, hierarchical system** designed to produce highly capable agentic LLMs optimized for:

- **Software development tasks** (coding, debugging, architecture)
- **Project planning & execution** (feature design, task breakdown)
- **Troubleshooting & root-cause analysis** (systematic debugging)
- **Repository maintenance** (code review, testing, deployment)
- **Deep reasoning** (planning, architectural decisions, trade-off analysis)

### Key Characteristics

| Aspect | Description |
|--------|-------------|
| **Hardware Target** | AMD RX 7900 XTX (24GB VRAM) |
| **Base Models** | Qwen 2.5 Coder 7B/14B (dense), Qwen 3 30B MOE |
| **Reasoning Enhancement** | Opus 1.5 (thinking pipeline), chain-of-thought reasoning |
| **Training Method** | LoRA fine-tuning on curated repository code & guidance |
| **Instruction Layers** | 4-layer hierarchical guidance (bootstrap → rules → workflows → base prompts) |
| **Corpus Source** | Repository code, documentation, workflows, skills, instructions |
| **Fingerprinting** | SHA256-based caching for training acceleration |
| **Deployment** | Local inference via Ollama + Copilot-style tool integration |

---

## System Architecture

### 1. Multi-Layer Instruction Stack

The agent behavior is governed by a **4-layer priority hierarchy**:

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: BOOTSTRAP (Startup Gate)                       │
│ - File: .github/agent/BOOTSTRAP.md                      │
│ - Purpose: Deterministic startup validation            │
│ - Checks: rules, workflow, context, tool mapping       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Layer 2: CANONICAL RULES (Non-negotiable Policy)        │
│ - File: .github/agent/rules.md                          │
│ - Priority: HIGHEST (overrides all other guidance)      │
│ - Scope: Tool usage, file operations, safety,          │
│         execution context, security                     │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Layer 3: COPILOT INSTRUCTIONS (Repository Guidance)     │
│ - File: .github/copilot-instructions.md                 │
│ - Scope: Project-specific guidelines, conventions,      │
│         build context, dev container rules              │
│ - Includes: Workflows, tool mapping, reasoning patterns │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Layer 4: BASE PROMPTS (Model Conditioning)              │
│ - File: .github/agent/base.prompts.md                   │
│ - Scope: Cross-runtime behavior, expectations,         │
│         verification patterns, path conventions         │
└─────────────────────────────────────────────────────────┘
```

### 2. Workflow Routing System

Agents use deterministic routing to select mandatory workflows:

```
User Request
    │
    ▼
┌─────────────────────────────────┐
│ BOOTSTRAP (startup gate)        │
│ Load rules & validate context   │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ WORKFLOW SELECTION               │
│ workflow-orchestration-baseline  │
│ Match against WORKFLOW-INDEX    │
└────────────┬────────────────────┘
             │
    ┌────────┴──────────┬──────────┬─────────┬──────────┐
    │                   │          │         │          │
    ▼                   ▼          ▼         ▼          ▼
troubleshoot        planning    new-feat  server-infra  game-logic
(root-cause)       (design)    (impl)    (deploy)      (godot)
    │                   │          │         │          │
    └───────────────────┴──────────┴─────────┴──────────┘
                        │
                        ▼
                   PREFLIGHT GATE
                 (pre-action checks)
                        │
                        ▼
                    EXECUTION
```

### 3. Core Components

```
┌─────────────────────────────────────────────────────────┐
│ AGENT PIPELINE COMPONENTS                               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ INSTRUCTION LAYER                                  │  │
│ │ ├─ Bootstrap Gate (startup validation)             │  │
│ │ ├─ Rules Engine (policy enforcement)               │  │
│ │ ├─ Workflow Router (task classification)           │  │
│ │ └─ Reasoning Guide (critical thinking)             │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ TRAINING INFRASTRUCTURE                            │  │
│ │ ├─ Corpus Generation (code + guidance collection) │  │
│ │ ├─ Fingerprinting (SHA256 caching)                │  │
│ │ ├─ LoRA Training (profile-based specialization)   │  │
│ │ ├─ Memory Estimation (OOM prevention)             │  │
│ │ ├─ Metrics Export (convergence tracking)          │  │
│ │ └─ Model Merging & Export (GGUF quantization)     │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ REASONING FRAMEWORKS                               │  │
│ │ ├─ Thinking Pipeline (Opus → Qwen feedback loop) │  │
│ │ ├─ Chain-of-Thought (step-by-step reasoning)      │  │
│ │ ├─ ReAct Pattern (reason → act → observe)         │  │
│ │ ├─ Root-Cause Analysis (systematic debugging)     │  │
│ │ └─ Verification Loop (pre & post checks)          │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ TOOL INTEGRATION LAYER                             │  │
│ │ ├─ Workspace Tools (read/search/edit files)       │  │
│ │ ├─ Shell/Task Execution (build, test, git)        │  │
│ │ ├─ Container Orchestration (dev environment)      │  │
│ │ └─ Copilot-style API (VS Code integration)        │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ KNOWLEDGE BASES                                    │  │
│ │ ├─ Repository Corpus (curated training data)      │  │
│ │ ├─ Workflow Specifications (task templates)        │  │
│ │ ├─ Skills Documentation (patterns & practices)     │  │
│ │ ├─ Project Guidelines (.github/agent/)            │  │
│ │ └─ Reference Materials (architecture, decisions)   │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Training Infrastructure

### 1. Corpus Generation Pipeline

**Purpose**: Automatically collect and prepare training data from repository.

**Process**:

```
Repository Files
    │
    ├─ Profile include_globs (select relevant files)
    ├─ Profile exclude_globs (filter out noise)
    │
    ▼
┌────────────────────────────────────────────┐
│ File Selection & Filtering                 │
│ - Instructions (.github/agent/*.md)        │
│ - Build scripts (build/agent/*.py)         │
│ - Workflow specs (.github/agent/workflows/)│
│ - Code examples (server/, frontend/, etc.)│
│ - Documentation (README.md, guides)        │
└────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────┐
│ Sample Formatting                          │
│ Each file becomes instructional sample:    │
│                                            │
│ <instruction>Learn from codebase</instr>  │
│ <source>path/to/file.py</source>          │
│ <answer>[full file content]</answer>      │
└────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────┐
│ Corpus Validation & Analysis               │
│ - Sample count                             │
│ - Total size                               │
│ - Token estimates (≈1 token per 4 chars)  │
│ - Extreme size detection (warnings)        │
│ - Distribution analysis                    │
└────────────────────────────────────────────┘
    │
    ▼
Output: training-data.jsonl + metadata.json
```

**Key Files**:
- Generator: `build/agent/build.train.py`
- Output: `do/agent/models/training/*.jsonl`
- Metadata: `do/agent/models/training/*-metadata.json`
- Cache: `do/agent/models/cache/*/lora-train.sha256*`

### 2. LoRA Training Pipeline

**Purpose**: Fine-tune base model on curated corpus to specialize agent behavior.

**Architecture**:

```
Fingerprint Check
    │
    ├─ Input hash: corpus + profile + finetune script + config
    ├─ Cached hash: previous training fingerprint
    │
    ├─ Match? ──YES──> SKIP TRAINING
    │                  (reuse cached adapter)
    │
    └─ NO ──>
          │
          ▼
    ┌────────────────────────────────────────┐
    │ Memory Estimation                      │
    │ - Model size (GB) lookup table         │
    │ - Quantization adjustment (4/8-bit)   │
    │ - Batch size × grad_accum overhead     │
    │ - Optimizer state (AdamW = 2×)         │
    │ - Activation memory (2× per batch)     │
    │ => Total GPU memory estimate           │
    │ => WARN if > 20GB (margin thin)       │
    │ => WARN if > 18GB (risky)             │
    └────────────────────────────────────────┘
          │
          ▼
    ┌────────────────────────────────────────┐
    │ Model Loading & LoRA Setup             │
    │ - Load base model (quantized)          │
    │ - Attach LoRA adapters to:             │
    │   * q_proj, k_proj, v_proj, o_proj    │
    │   * gate_proj, up_proj, down_proj     │
    │ - Freeze base, train adapter only      │
    │ - Rank: 16, Alpha: 32, Dropout: 0.05 │
    └────────────────────────────────────────┘
          │
          ▼
    ┌────────────────────────────────────────┐
    │ Training Loop                          │
    │ - Corpus: 759 samples (7.5MB, 1.95M tokens)
    │ - Epochs: 1, Batch: 1, Grad accum: 8 │
    │ - LR: 0.0001, Warmup: 3%             │
    │ - Checkpoint every 47 steps            │
    │ - Metrics: loss, learning_rate        │
    │ - Optimizer: AdamW 8-bit              │
    └────────────────────────────────────────┘
          │
          ▼
    ┌────────────────────────────────────────┐
    │ Training Outputs                       │
    │ - Adapter weights: 155MB               │
    │ - Checkpoints: full training state     │
    │ - Metrics: training-metrics.json       │
    │ - Fingerprint: sha256 of inputs        │
    └────────────────────────────────────────┘
```

**Key Files**:
- Fingerprinting: `build/agent/build.lora_fingerprint.py`
- Training: `build/agent/build.finetune.py`
- Output: `do/agent/models/lora/rx7900xtx-agentic/`
- Caching: `do/agent/models/cache/rx7900xtx-agentic/`

### 3. GGUF Export Pipeline

**Purpose**: Merge trained adapter into base model and export for inference.

**Features**:
- Fingerprinting: Skip merge/export if adapter unchanged
- Quantization: Export at Q5_K_M for inference efficiency
- Caching: Saved fingerprints prevent redundant exports (30-60 min saves)

**Key Files**:
- Export: `build/agent/build.lora_export_gguf.py`
- Fingerprinting: `build/agent/build.gguf_fingerprint.py`
- Output: GGUF model for Ollama deployment

### 4. Hardware Profile System

**Purpose**: Capture GPU-specific optimizations and model selections.

**Profile Structure** (`build/agent/profiles/*.json`):

```json
{
  "gpu": {
    "name": "AMD Radeon RX 7900 XTX",
    "vram_gb": 24,
    "recommended_quantization": "Q5_K_M (inference); full precision with gradient checkpointing (training)"
  },
  "runtime": {
    "num_ctx": 131072,  // 128K context window
    "num_predict": 4096,
    "temperature": 0.2,  // Deterministic for coding
    "top_k": 40,
    "top_p": 0.9
  },
  "lora": {
    "batch_size": 1,
    "grad_accum": 8,
    "max_seq_length": 8192,  // Training sequence limit
    "lora_r": 16,
    "lora_alpha": 32,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
  },
  "model_preferences": {
    "balanced": ["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
    "reasoning_heavy": ["hf.co/mradermacher/ERNIE-21B..."]
  }
}
```

---

## Reasoning & Deep Thinking Frameworks

### 1. Thinking Pipeline (Opus + Execution Model)

**Architecture**: Two-model reasoning system combining thinking + execution.

```
User Input
    │
    ▼
┌──────────────────────────────────────────┐
│ Opus 1.5 (Thinking Model)                │
│ Parameters: 0.88B                        │
│ VRAM: 2GB                                │
│ Task: Generate reasoning traces          │
│ Output format:                           │
│   <|thinking|>                          │
│     Step-by-step analysis...           │
│     Key insights, trade-offs            │
│   </|thinking|>                         │
│   [Final summary/directive]             │
└──────────────────────────────────────────┘
    │
    ▼ (extract thinking + confidence score)
    │
┌──────────────────────────────────────────┐
│ Confidence Assessment                    │
│ Confidence >= 0.8?                       │
│                                          │
│ YES ──────────────────────┐             │
│                            │ (PROCEED)  │
│ NO ────────────┐          │             │
│                 │ (RETRY)  │             │
│          Round limit?      │             │
│          (max 3 rounds)    │             │
│                 │          │             │
│          NO <───┘          │             │
│          YES ──────────────┘             │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ System Prompt Injection                  │
│ "Based on this analysis:"                │
│ [Opus thinking content]                  │
│ "Please provide your response:"          │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ Qwen 14B/7B (Execution Model)            │
│ Generates response using thinking       │
│ context to improve quality               │
│ Only Qwen response shown to user         │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ Trace Logging                            │
│ Save complete trace for debugging        │
│ - All thinking stages                    │
│ - Confidence scores                      │
│ - Key insights per round                 │
│ - Final response                         │
│ Location: build/do/agent/thinking_traces/│
└──────────────────────────────────────────┘
```

**Key Implementation**: `build/agent/thinking_pipeline.py`

### 2. Chain-of-Thought Reasoning (CoT)

**Pattern**: Agent breaks multi-step problems into explicit reasoning steps.

**Used in Workflows**:
- `workflow-troubleshooting.md`: Root-cause analysis requires step-by-step investigation
- `workflow-planning.md`: Feature design requires exploration of approaches
- `workflow-new-feature.md`: Implementation requires sequential task breakdown

**Example** (from reasoning.md):
```
Phase 1: Clarify Intent
  └─ What does the user want?

Phase 2: Identify Constraints
  └─ What rules/patterns apply?

Phase 3: Gather Context
  └─ What existing code/docs exist?

Phase 4: Plan Steps
  └─ How do I sequence this?

Phase 5: Verify Requirements
  └─ Do I understand success criteria?

Phase 6: Execute Methodically
  └─ One step at a time with verification
```

### 3. ReAct Pattern (Reason → Act → Observe)

**Pattern**: Interleave reasoning with tool use and observation of results.

**Workflow** (from preflight gates):

```
Thought: "What action should I take?"
  ↓
Action: (execute tool/command)
  ↓
Observation: (read result, verify output)
  ↓
Thought: "Did this work? What's next?"
  ↓ (Loop until task complete)
```

**Example**:
```
Thought: "Need to understand the file structure"
  Action: list_dir(src/)
  Observation: [index.ts, utils.ts, components/]
Thought: "Now need to check imports"
  Action: read_file(src/index.ts)
  Observation: [imports read, dependencies identified]
Thought: "Ready to implement change"
  Action: replace_string_in_file(...)
  Observation: [edit verified, file correct]
Thought: "Done"
```

### 4. Systematic Debugging (Root-Cause Analysis)

**Framework** (from workflow-troubleshooting.md):

```
Phase 1: Root Cause Investigation
  1A. Read error messages completely
  1B. Note file paths, line numbers, error codes
  1C. Search for exact error in codebase
  1D. Reproduce the issue deterministically
  1E. Isolate the failure: narrowest scope, single condition

Phase 2: Hypothesis Formation
  2A. What are 2-3 hypotheses for the root cause?
  2B. Which is most likely given the evidence?
  2C. Can you predict the consequences of each?

Phase 3: Verification
  3A. Design a test to verify each hypothesis
  3B. Execute test and observe results
  3C. Which hypothesis matches observation?

Phase 4: Implementation
  4A. Fix the root cause (not the symptom)
  4B. Test the fix
  4C. Check for side effects

Phase 5: Prevention
  5A. Why wasn't this caught earlier?
  5B. How can we prevent it in the future?
  5C. Add test coverage if appropriate
```

### 5. Verification Loops

**Pre-Action Checks** (from PREFLIGHT.md):

```
Before Every Action:
  □ Policy Check: Conflicts with rules.md?
  □ Workflow Check: Consistent with current stage?
  □ Environment Check: Correct container/host?
  □ Safety Check: No secrets exposed?
  □ Tool Check: Right tool for this task?
```

**Post-Action Verification**:

```
After Every Edit:
  □ Read file back and verify intent
  □ Check surrounding context
  □ Confirm no unintended changes

After Every Execution:
  □ Record exit code
  □ Capture key output
  □ Verify against expected success

After Complex Tasks:
  □ Run tests/validation
  □ Check for side effects
  □ Document any issues discovered
```

---

## Agent Capabilities & Domains

### 1. Core Development Domains

| Domain | Capabilities | Supported Workflows |
|--------|-------------|-------------------|
| **Coding** | Implement features, fix bugs, refactor | new-feature, troubleshooting |
| **Debugging** | Root-cause analysis, systematic investigation | troubleshooting |
| **Testing** | Write/update tests, verify coverage | task-verification |
| **Architecture** | Design decisions, trade-offs, documentation | planning |
| **DevOps** | Container management, deployment configs | server-infrastructure |
| **Game Dev** | Godot scripts (GDScript), asset management | generate-game-logic |

### 2. Agent Reasoning Capabilities

| Capability | Implementation | Training Focus |
|------------|----------------|---------------|
| **Deep Reasoning** | Opus thinking pipeline | Multi-stage problem analysis |
| **Planning** | Workflow-planning.md patterns | Design before code |
| **Troubleshooting** | Systematic debugging workflow | Root-cause analysis |
| **Verification** | Pre/post-action gate validation | Quality gates at each step |
| **Tool Compliance** | Copilot-style tool integration | Proper tool selection and usage |
| **Context Awareness** | Repository-aware guidance layers | Constraint and policy respect |

### 3. Specialized Reasoning Tracks

**For Complex Planning**: Use reasoning-heavy model configs
- `qwen25-coder-14b-with-opus-thinking`
- `qwen3-30b-a3b-moe`

**For Balanced Tasks**: Standard model configs
- `qwen25-coder-7b` (lightweight)
- `qwen25-coder-14b` (recommended default)

---

## Guidance & Instruction Layers

### 1. Primary Guidance Documents

| File | Purpose | Priority | Scope |
|------|---------|----------|-------|
| `.github/agent/BOOTSTRAP.md` | Startup validation | 1 (first) | Before ANY action |
| `.github/agent/rules.md` | Canonical policy | 1 (override) | Always applies |
| `.github/copilot-instructions.md` | Project guidance | 2 (default) | Repository-specific |
| `.github/agent/reasoning.md` | Critical thinking | 2 (prereq) | Before each task |
| `.github/agent/PREFLIGHT.md` | Pre-action gates | 2 (prereq) | Before each action |

### 2. Workflow Specifications

**Available Workflows**:
- `workflow-orchestration-baseline.md` — Task routing entry point
- `workflow-troubleshooting.md` — Root-cause analysis
- `workflow-planning.md` — Feature design before code
- `workflow-new-feature.md` — Feature implementation
- `workflow-task-verification.md` — Testing & validation
- `workflow-server-infrastructure.md` — Deployment & DevOps
- `workflow-generate-game-logic.md` — Godot/game development
- `workflow-llm-context-vram-optimization.md` — Memory optimization
- `WORKFLOW-INDEX.md` — Quick routing index

### 3. Tool & Capability Mapping

**Workspace Tools** (preferred for file operations):
- `file_search()` — Find files by pattern
- `grep_search()` — Text search in files
- `read_file()` — Read file content
- `create_file()` — Create new file
- `replace_string_in_file()` — Edit file
- `list_dir()` — Browse directory

**Execution Tools**:
- `run_in_terminal()` — Run shell commands (build, test, git)
- `run_task()` — Run VS Code tasks
- `container-tools_get-config()` — Container command routing

**Build/Make System**:
- `make prepare-corpus` — Generate training corpus
- `make lora-train` — Fine-tune on corpus
- `make lora-export-gguf` — Merge & export model

---

## Corpus & Knowledge Base

### 1. Corpus Contents

**Training Data Source** (from profile include_globs):

```
Guidance & Instructions (40% emphasis):
├─ .github/copilot-instructions.md
├─ .github/agent/rules.md
├─ .github/agent/**/*.md (workflows, bootstrap, reasoning)
└─ assets/reference/agent/**/*.md (architecture docs)

Build System & Automation (25% emphasis):
├─ build/agent/**/*.py (training scripts, fingerprinting, etc.)
├─ build/makefiles/agent.mk (orchestration)
└─ build/agent/profiles/*.json (configurations)

Code Examples (20% emphasis):
├─ server/**/*.py (backend implementation examples)
├─ frontend/admin-panel/src/**/*.{ts,tsx,js,jsx,css}
└─ gotdot/scripts/**/*.gd (game logic)

Documentation (15% emphasis):
├─ README.md (project overview)
└─ assets/reference/**/*.md (architecture, decisions)
```

### 2. Corpus Characteristics

**Corpus Statistics** (from training run):
- **Samples**: 759
- **Total Size**: 7.5 MB
- **Average per Sample**: 10,300 bytes
- **Size Range**: 190 - 224,669 bytes
- **Estimated Tokens**: 1,954,575 (~1 token per 4 chars)
- **Outliers**: 9 samples with extreme sizes (flagged as warnings)

### 3. Knowledge Categories

| Category | Focus | Examples |
|----------|-------|----------|
| **Reasoning Patterns** | How to think through problems | BOOTSTRAP, reasoning.md, workflows |
| **Tool Compliance** | Proper tool usage for Copilot | base.prompts.md, rules.md |
| **Domain Knowledge** | Project-specific patterns | Server code, frontend code, game scripts |
| **Process Guidance** | Step-by-step workflows | All workflow-*.md files |
| **Configuration** | Model/profile specifications | *.json model configs, profiles |

---

## Execution Context & Runtimes

### 1. Development Container

**Environment**: WSL2 + Docker
- **Container Image**: `lotr-dev:latest` (ROCm-enabled)
- **Base OS**: Ubuntu 24.04
- **GPU Support**: AMD ROCm 7.2 (RX 7900 XTX optimization)
- **Python**: 3.12 + venv
- **Framework Stack**: PyTorch (ROCm), Transformers, PEFT, Accelerate

**Runtime Setup**:
```powershell
# Start development container
./build/docker/docker.ps1 exec "cd /workspace/build && make prepare-corpus"

# Or interactive shell
./build/docker/docker.ps1 run
```

### 2. Tool Integration

**Copilot-Style Execution**:
- Agent has access to Copilot runtime tools (read, search, edit, execute)
- Tools are mapped to capabilities (workspace tools, shell execution, task runners)
- Container/host boundary is explicit: dev commands in container only

### 3. Build System Integration

**Make Targets** (run inside container):
```bash
make prepare-corpus          # Generate training corpus
make lora-fingerprint        # Compute input fingerprints
make lora-train              # Train LoRA adapter
make lora-export-gguf        # Merge & export for inference
make agent_build             # Run all above in sequence
```

---

## Performance Optimization

### 1. Fingerprinting & Caching

**Strategy**: SHA256-based input hashing to skip redundant work.

**Cached Steps**:
- **Corpus Preparation**: If profile/selection rules unchanged, reuse corpus
- **Training**: If corpus/config/adapter path unchanged, reuse trained weights
- **GGUF Export**: If adapter/base model/quantization unchanged, skip merge/export

**Impact**:
- Corpus: ~5 minutes saved per redundant run
- Training: ~30-60 minutes saved per skip
- Export: ~10-30 minutes saved per skip

**Implementation**:
- `build/agent/build.lora_fingerprint.py` — Compute training input hash
- `build/agent/build.gguf_fingerprint.py` — Compute export input hash
- `build/py/wiki/cache_stamp.py` — Generic caching utility

### 2. Memory Estimation

**Pre-Training Check**: Estimate GPU memory before launching training.

**Formula**:
```
estimated_gb = model_size_gb
              + (model_size_gb * 2 * effective_batch_size / 32)  # activations
              + (model_size_gb * 2)  # optimizer state (AdamW)

where effective_batch_size = batch_size * grad_accum
```

**Warnings**:
- `> 20GB`: "Thin margin (only 4GB buffer)"
- `> 18GB`: "Risky (only 6GB buffer, may OOM)"

**Result**: Prevents silent OOM failures; alerts user upfront.

### 3. Corpus Validation

**Pre-Training Analysis**:
- Sample count and distribution
- Extreme sizes (< 100 bytes or > 100KB) flagged as warnings
- Token estimates for training planning

**Output Example**:
```
[INFO] Corpus Analysis:
  Samples: 759
  Total size: 7.5 MB
  Est. tokens: 1,954,575
  ⚠️ Found 9 extreme samples (< 100 bytes or > 100KB)
```

### 4. Hashing Optimization

**Efficient Directory Hashing**:
- Two-pass collection (list files, then hash)
- Single digest per directory (no per-file metadata)
- Progress updates every 100 files (not per-file spam)
- Result: Same correctness, ~10× faster than naive approach

---

## Gaps & Improvement Roadmap

### Current Strengths

✅ **Comprehensive Reasoning Framework**
- Bootstrap → Rules → Workflows → Base Prompts hierarchy
- Systematic debugging workflow with root-cause focus
- Planning workflow with design-before-code emphasis
- Verification loops at every stage

✅ **Training Infrastructure**
- Fingerprinting prevents redundant training (30-60 min saves)
- Memory estimation prevents silent OOM failures
- Corpus analysis and validation
- Multiple model configurations for different task types

✅ **Tool Compliance**
- Copilot-style tool integration layer
- Workspace tools prioritized over shell
- Clear container/host boundary enforcement
- Safety gates for destructive operations

### Identified Gaps

#### Gap 1: Project Execution Observability

**Issue**: No metrics on how well agents execute actual project tasks.

**Missing Components**:
- [ ] Task completion tracking (success rate, time to completion)
- [ ] Error classification (tool errors, reasoning errors, environment errors)
- [ ] Agent reasoning trace logging (what reasoning was done?)
- [ ] Performance metrics by task type (troubleshooting vs. implementation)
- [ ] Failure analysis (why did agent fail on this task?)

**Improvement**: Add task instrumentation layer

```
Task Execution Flow:
├─ Task Start → Log goal, requirements, estimated complexity
├─ Reasoning Phase → Log reasoning traces, CoT steps
├─ Action Phase → Log each tool invocation, result
├─ Verification Phase → Log pass/fail criteria checks
└─ Task End → Log completion status, total time, any errors
```

**Benefits**:
- Identify which reasoning patterns work best
- Detect common failure modes
- Track agent improvement over time
- Data for future training corpus

#### Gap 2: Multi-Model Collaboration Framework

**Issue**: Only Opus + Execution pairs; no framework for multi-model task decomposition.

**Missing Components**:
- [ ] Task routing to specialized models (reasoning vs. coding vs. testing)
- [ ] Model selection criteria (when to use 7B vs. 14B vs. 30B MOE)
- [ ] Output validation between models (confidence scores, semantic validation)
- [ ] Fallback patterns (if model fails, what's next?)

**Improvement**: Add model orchestration layer

```
Task → Router
  ├─ Complex reasoning? → Opus + Qwen
  ├─ Simple implementation? → Qwen 7B
  ├─ Architecture/design? → Qwen 14B or MOE
  └─ Verification? → Specialized validator model
```

#### Gap 3: Advanced Reasoning Patterns Not Yet Explored

**Missing Patterns**:
- [ ] **Tree of Thought (ToT)**: Explore multiple reasoning branches, select best path
- [ ] **Iterative Refinement**: Multi-round improvement with feedback
- [ ] **Analogical Reasoning**: "This is like [similar problem], solution is [pattern]"
- [ ] **Constraint Propagation**: Working backward from success criteria
- [ ] **Debate/Consensus**: Multiple agents debate solution, reach consensus

**Potential**: Significantly improve reasoning quality for complex problems

#### Gap 4: Corpus Diversity & Specialization

**Current State**:
- Corpus focused on agentic patterns (reasoning, tool use, workflows)
- Limited diversity in programming domains (backend heavy, frontend light)
- Game logic (Godot/GDScript) underrepresented

**Improvements Needed**:
- [ ] Add more frontend/UI examples (React patterns, CSS best practices)
- [ ] Add game logic examples (more Godot scripts, state machines, physics)
- [ ] Add testing/QA patterns (test design, edge cases, assertions)
- [ ] Add performance optimization examples (profiling, caching, algorithms)
- [ ] Add security/hardening examples (input validation, SQL injection prevention)

**Impact**: Better specialization for non-agentic tasks

#### Gap 5: Tool Use & Integration Depth

**Current State**:
- Tools available but patterns not deeply embedded in training
- Limited examples of tool selection reasoning
- Fallback patterns not well documented

**Improvements Needed**:
- [ ] Add tool selection reasoning examples to corpus
- [ ] Document tool fallback patterns explicitly
- [ ] Add error recovery examples (when tool fails, what next?)
- [ ] Include tool capability/limitation documentation in training
- [ ] Add examples of tool composition (chaining tools)

**Example Training Material**:
```
<instruction>Learn tool selection reasoning</instruction>
<source>tool-selection-patterns.md</source>
<answer>
# Tool Selection Decision Tree

When need to read files:
├─ Single known file? → read_file()
├─ Search across many files? → grep_search() or file_search()
├─ Browse structure? → list_dir()

When need to edit:
├─ Create new? → create_file()
├─ Modify existing? → replace_string_in_file()
├─ Multiple edits? → multi_replace_string_in_file()

Fallback patterns:
├─ Tool unavailable? → grep_search() is universal for search
├─ No read tool? → Use run_in_terminal with cat/type
├─ Performance issue? → Batch operations, don't loop
</answer>
```

#### Gap 6: Troubleshooting Specialized Training

**Current State**:
- Troubleshooting workflow is documented
- Limited troubleshooting examples in training corpus

**Improvements Needed**:
- [ ] Add troubleshooting case studies (real bugs + solutions)
- [ ] Document error message interpretation patterns
- [ ] Add root-cause analysis examples (false paths avoided, correct path found)
- [ ] Include performance debugging examples
- [ ] Add environment-specific issue examples

**Training Material to Add**:
```
Troubleshooting Cases:
├─ Case: Container networking issue
│  ├─ Error message analysis
│  ├─ Root-cause investigation steps
│  ├─ Hypotheses considered
│  └─ Solution and prevention
├─ Case: Out-of-memory failure (we just experienced this!)
├─ Case: Configuration mismatch
└─ Case: Integration issue across services
```

#### Gap 7: Planning & Architecture Decision Capture

**Current State**:
- Planning workflow is documented
- Limited architectural decision examples

**Improvements Needed**:
- [ ] Add architectural decision records (ADRs) to training
- [ ] Document trade-off analysis patterns
- [ ] Include performance/scalability considerations
- [ ] Add failure mode analysis (what could go wrong?)
- [ ] Include cost/complexity analysis examples

**Training Material to Add**:
```
Architecture Decision Record Format:
├─ Problem statement
├─ Context and constraints
├─ Proposed solutions (2-3 options)
├─ Trade-offs (pros/cons of each)
├─ Decision rationale
├─ Consequences (expected outcomes)
└─ Alternative paths (if decision proves wrong)
```

### Improvement Priority Matrix

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Task observability & metrics | High | Medium | **HIGH** |
| Advanced reasoning patterns (ToT, etc.) | High | High | **HIGH** |
| Corpus domain expansion (frontend, game, testing) | Medium | Medium | **MEDIUM** |
| Multi-model orchestration framework | Medium | High | **MEDIUM** |
| Tool use pattern training | Medium | Low | **MEDIUM** |
| Troubleshooting case studies | Medium | Medium | **MEDIUM** |
| Architecture decision capture | Low | Medium | **LOW** |

---

## Recommendations for LLM Training Enhancement

### 1. Immediate Actions (High-Impact, Low-Effort)

**A. Expand Troubleshooting Examples**
- Add 5-10 real troubleshooting cases from your project history
- Document root-cause paths taken and avoided
- Include error messages, investigation steps, solution
- File: `assets/reference/agent/troubleshooting-cases.md`

**B. Tool Use Pattern Training**
- Document tool selection decision trees
- Add examples of tool chaining and fallbacks
- Include performance patterns (batch vs. loop)
- File: `assets/reference/agent/tool-use-patterns.md`

**C. Task Instrumentation**
- Add logging around task execution phases
- Capture reasoning traces and decisions
- Log tool invocations and results
- Create dashboard to visualize patterns

### 2. Medium-Term Actions (High-Impact, Medium-Effort)

**A. Corpus Domain Expansion**
- Systematically add frontend code examples
- Add game logic (Godot) examples
- Add testing/QA pattern examples
- Add performance optimization case studies

**B. Advanced Reasoning Framework**
- Research & experiment with Tree of Thought
- Implement multi-branch exploration
- Add confidence-weighted path selection
- Measure quality improvement vs. baseline

**C. Multi-Model Orchestration**
- Design task router (which model for which task?)
- Implement model selection criteria
- Add inter-model validation layer
- Test task decomposition strategies

### 3. Long-Term Vision (Sustained Excellence)

**A. Continuous Learning Loop**
- Instrument agent task execution
- Analyze failure modes systematically
- Identify patterns in successful vs. failed tasks
- Use insights to improve training corpus and guidance

**B. Specialized Agent Variants**
- Debugging-focused agent (troubleshooting expertise)
- Architecture-focused agent (planning, design)
- Testing-focused agent (test design, QA)
- DevOps-focused agent (deployment, infrastructure)

**C. Reasoning Framework Evolution**
- Blend multiple reasoning patterns (CoT + ToT + ReAct)
- Context-aware pattern selection (when to use what)
- Confidence/uncertainty quantification
- Graceful degradation when confident reasoning fails

---

## Maintenance & Updates

### Regular Tasks

**Weekly**:
- Monitor training pipeline stability
- Check for fingerprinting cache effectiveness
- Review agent task completion rates (once instrumented)

**Monthly**:
- Review error logs and failure patterns
- Update corpus with new domain examples
- Experiment with new reasoning patterns
- Performance benchmarking

**Quarterly**:
- Major corpus refresh (seasonal relevance)
- Model configuration tuning (adjust batch sizes, LR, etc.)
- Workflow updates based on learned patterns
- Infrastructure optimization (caching effectiveness)

### Making Updates to Agent Guidance

**When adding/modifying workflows**:
1. Update relevant workflow file in `.github/agent/workflows/`
2. Update `WORKFLOW-INDEX.md` routing table
3. Add new corpus examples demonstrating pattern
4. Document decision in architecture decisions file
5. Re-generate corpus and retrain (optional but recommended)

**When updating base instructions**:
1. Edit `.github/agent/base.prompts.md` or `.github/copilot-instructions.md`
2. Include clear rationale in commit message
3. Test with sample agent tasks
4. Update corpus if pattern is fundamental
5. Re-train if guidance significantly changes

---

## Conclusion

The LOTR agent pipeline represents a **sophisticated, multi-layered system** for producing highly capable agentic LLMs. Current implementation excels at:

- Hierarchical guidance and policy enforcement
- Deterministic task routing and workflow selection
- Deep reasoning frameworks (thinking pipeline, CoT, ReAct)
- Efficient training with fingerprinting and caching
- Clear tool compliance and execution boundaries

The identified gaps present opportunities for **sustained improvement**:

- Task observability for continuous learning
- Advanced reasoning patterns (ToT, multi-branch exploration)
- Corpus domain expansion for broader capabilities
- Multi-model orchestration for task specialization
- Specialized agent variants for specific domains

By systematically addressing these gaps, the agent system can evolve into an **autonomous, self-improving development partner** that combines reasoning depth, tool mastery, and domain expertise.

---

**End of Document**
Document Version: 1.0 | Last Updated: 2026-06-27
