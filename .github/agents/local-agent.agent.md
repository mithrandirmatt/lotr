---
name: local-agent
display_name: local-agent
description: "Local wrapper agent — uses local Ollama and a validated JSON action schema to run safe tools."
includes:
  - ../agent/local-wrapper/prompts.md
---

Use this agent when you want an offline, auditable wrapper around local models.
It relies on the scripts in `.github/agent/local-wrapper` and expects an Ollama
HTTP endpoint to be reachable via `OLLAMA_URL`.
