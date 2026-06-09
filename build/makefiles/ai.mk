## AI helpers

.PHONY: ai_list ai_gpu_check ollama_cap_model ai_headroom

# OLLAMA_BASE: Ollama endpoint reachable from inside the dev container.
# lotr-ai:11434 is the container-to-container address on lotr-net.
# Override with: make ollama_cap_model OLLAMA_BASE=http://localhost:11434
OLLAMA_BASE      ?= http://lotr-ai:11434
OLLAMA_SRC_MODEL ?= sorc/qwen3.5-claude-4.6-opus:latest
OLLAMA_CAP_MODEL ?= sorc/qwen3.5-claude-4.6-opus:copilot

# ollama_cap_model: create a VS Code Copilot-optimised variant of the model.
# num_ctx=32768  -- tells VS Code the context window is 32k so it compresses
#                   conversation history at ~21k tokens (66%) automatically.
# /no_think      -- disables Qwen3 thinking blocks (saves tokens before answering).
# num_predict=2048 -- prevents runaway output ("Response too long" errors).
ollama_cap_model:
	$(call log_build,Creating Copilot model $(OLLAMA_CAP_MODEL) via $(OLLAMA_BASE)...)
	@printf '{"model":"%s","from":"%s","system":"Think concisely if needed. Use at most 2 thinking blocks per response.","parameters":{"num_ctx":32768,"num_predict":2048}}' \
	    "$(OLLAMA_CAP_MODEL)" "$(OLLAMA_SRC_MODEL)" | \
	    curl -sSL --fail-with-body -X POST "$(OLLAMA_BASE)/api/create" \
	        -H 'Content-Type: application/json' \
	        -d @-
	$(call log_ok,Done. Use model: $(OLLAMA_CAP_MODEL))

# ai_list: list Ollama models visible to the running Ollama container
# Uses the WSL distro 'lotr-docker-service' to invoke docker so the same
# environment used by `build/docker/docker.ps1` is respected.
ai_list:
	@echo "Listing Ollama models from Docker..."
	@/workspace/build/docker/scripts/ai_list.sh

# ai_gpu_check: verify the lotr-ai container is using the GPU, not CPU.
# Shows rocm-smi GPU utilisation and the Ollama /api/ps layer split.
# Requires the lotr-ai container to be running.
ai_gpu_check:
	$(call log_build,Checking GPU status inside lotr-ai container...)
	@docker exec lotr-ai python3 /app/test_gpu.py 2>&1 || true
	$(call log_ok,GPU check complete.)

# ai_headroom: show the local headroom proxy dashboard URL and live stats.
# Headroom runs inside lotr-docker-service on port 8787.
# Open the dashboard in a browser: http://localhost:8787/dashboard
HEADROOM_URL ?= http://lotr-headroom:8787

ai_headroom:
	$(call log_build,Headroom proxy dashboard...)
	@echo ""
	@echo "  Browser panel : http://localhost:8787/dashboard"
	@echo "  Stats endpoint: http://localhost:8787/stats"
	@echo ""
	@curl -sSL --max-time 3 "$(HEADROOM_URL)/stats" 2>/dev/null | python3 -c "import sys,json; raw=sys.stdin.read().strip(); d=json.loads(raw) if raw else None; r=d.get('requests',{}) if d else None; t=d.get('tokens',{}) if d else None; print('  Requests  :',r.get('total','?')) or print('  Tokens in :',t.get('input','?')) or print('  Tokens out:',t.get('output','?')) or print('  Saved     :',t.get('saved','?')) or print('  Savings % :',str(t.get('savings_percent','?'))+'%') if d else print('  (proxy not running -- start with: docker.ps1 run)')"
	@echo ""
	$(call log_ok,Done.)


ai_npm_install:
	$(call log_build,Installing npm dependencies for VS Code extension...)
	@cd .vscode/extensions/ai && npm install
	$(call log_ok,Done.)

## ---------------------------------------------------------------------------
## Local LLM index & helper
## ---------------------------------------------------------------------------

# Rebuild the repo embeddings and start the interactive helper.
# Usage: ``make ai:update``
ai_update:
	@echo "Rebuilding repository embeddings…"
	python3 ../scripts/embed_repo.py
	@echo "Starting LLM helper…"
	# Run in background so make exits immediately
		nohup python3 ../scripts/llm_helper.py > /dev/null 2>&1 &
	@echo "LLM helper running (PID $$!). Use Ctrl+C to stop."
