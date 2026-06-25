---
name: lotr-project-overview
---
# LotR Project Overview

## Mission
Build a digital Lord of the Rings TCG platform and the surrounding agentic tooling needed to develop, verify, and maintain it.

## What the repository contains
- Game rules, card data, and turn-state logic for the LotR TCG.
- Server-side application code and APIs.
- Frontend/admin tooling for managing cards, decks, and workflows.
- ML and inference assets for LoRA training, quantization, and AMD-focused runtime setup.
- Docker and WSL2-based development automation.
- Agent training and reinforcement material under `assets/reference/agent/`.

## Core subsystems
### Game domain
The project is centered on faithfully representing LotR TCG rules, formats, deck construction, turn structure, and card interactions. The game plan documents the desired product scope, and the rules reference captures the detailed card and gameplay rules the agent must respect.

### Backend and services
Python services under `server/` and related code under `lotr/` provide the application and API surface. The agent should treat these areas as the control plane for game state, rules enforcement, and supporting services.

### ML and inference
The repository includes LoRA and model-building workflows for `lotr-lora-rx7900xtx-agentic` and related models. These workflows target AMD hardware and use Ollama, custom Modelfile generation, and the local proxy path for runtime control.

### Development environment
Development is intended to happen inside the Docker/WSL2 environment created by the scripts in `build/docker/`. One-off commands should use the repository's container execution flow instead of host-side development commands.

## Directory guide
- `build/` - build automation, model assembly, training, quantization, and Docker orchestration.
- `assets/reference/agent/` - project-specific and agent-specific training corpus.
- `server/` - backend services and API entry points.
- `lotr/` - application and domain code related to the game itself.
- `frontend/` - admin UI and supporting frontend work.
- `gotdot/` - Godot-related project assets and integration.
- `scripts/` - utility scripts for embeddings, Ollama proxying, and maintenance.
- `tools/` - repository tooling such as indexing and query helpers.
- `ml-project/` - ML pipelines, experiments, and evaluation assets.

## Knowledge boundaries
- `assets/reference/agent/` is the canonical place for project knowledge, reinforcement notes, and trigger guidance.
- Stable operational rules belong in the system instructions and build tooling.
- Fast-changing lessons should be recorded in the reinforcement files rather than retraining the model immediately.
- LotR-specific facts and generic agent lessons should remain separated so they can be reviewed independently.

## Working assumptions
- The model is not expected to know this repository unless the injected docs provide that context.
- The agent should answer project questions from the injected corpus and the live workspace, not from implied memory.
- The most important training signal is a unique, evidence-backed lesson that can be reused later.
