---
name: lotr-reinforcement-lotr
---
# LotR Reinforcement Notes

This file is for lessons that are specific to the LotR repository, its game rules, its build system, its model setup, or its runtime environment.

## Use this file for
- Game mechanics and rules behavior.
- Server or API implementation details.
- Docker, WSL2, or GPU setup that is unique to this repo.
- Model configuration, LoRA setup, Ollama proxy behavior, or repo-specific training pipelines.
- Directory conventions, build targets, or workspace patterns that only matter here.

## Entry template
- Date:
- Trigger:
- Learning:
- Evidence:
- Impact:

## Entries

- Date: 2026-07-23
- Trigger: User reported local LLM chat gave "Sorry, no response was returned."
- Learning: `scripts/ollama_proxy.py` (port 11436) and the `lotr-headroom` container
  (port 8787) are DEPRECATED. Copilot now talks to Ollama directly on port 11434 -
  see `.vscode/settings.json` (`github.copilot.chat.languageModel.ollama.serverUrl`).
  Do not start the proxy or chase port 11436 when troubleshooting. Separately, the
  actual "no response returned" symptom reproduces directly against Ollama (no proxy
  involved) with reasoning/"thinking" models when `max_tokens` is too small: the model
  spends its whole budget on the hidden `reasoning` field and returns an empty
  `content` string with `finish_reason:"length"`.
- Evidence: `Get-NetTCPConnection -LocalPort 11436` showed nothing listening (expected,
  not a bug). Direct `POST http://localhost:11434/v1/chat/completions` to
  `lotr-agentic-rx7900xtx-agentic-qwen35-262k:latest` with `max_tokens:16` returned
  `content:""`, `finish_reason:"length"`; the same request with `max_tokens:800`
  returned `content:"OK"`, `finish_reason:"stop"`. Follow-up: tried disabling thinking
  via Modelfile `SYSTEM` `/no_think`, user-turn `/no_think`, and `"think":false` on
  `/v1/chat/completions` -- all three had **no effect** (model reads `/no_think` as
  literal text; `think:false` is silently ignored on the OpenAI-compat endpoint in
  Ollama 0.32.1). `"think":false` on the **native** `/api/chat` endpoint DOES work
  (confirmed: instant `content:"OK"`, no `reasoning` field). Copilot's ollama BYOM
  calls `/v1/chat/completions`, so thinking cannot currently be disabled for this
  model via direct connection -- `max_tokens`/`num_predict` headroom is the only
  confirmed working lever.
- Impact: Full details and remediation steps captured in
  `.github/copilot-helper.md` ("Troubleshooting the Ollama / Copilot Call Stack") and
  `/memories/repo/dev-environment-quirks.md`.
- Replaces or refines:
- Status:

## Current focus areas
- Card and turn-structure behavior.
- Deck and format validation rules.
- Dev-container and Docker workflows.
- AMD/ROCm model and inference configuration.
- Agent-specific repository conventions.

## Writing rules
- Keep entries short and specific.
- Prefer one lesson per entry.
- Merge repeated lessons into one canonical note.
- If the note is project-specific but also teaches a generic technique, keep the LotR details here and capture the general rule in the generic file.
