
# =============================================================================
# agent.mk -- agent sync targets
#
# agent_update:
#   Prepares all agent files ready to commit. No git operations are performed.
#   1. Flatten each .github/agents/*.agent.md profile (resolve includes:) into
#      .github/agents/generated/ via build/py/gen_agents.py
# =============================================================================

.PHONY: agent_update agent_check sync_continue

# Default iterations for model benchmarking (can be overridden by calling `make bench_models ITERATIONS=5`)
ITERATIONS ?= 3

# ---------------------------------------------------------------------------
# agent_update: regenerate all flattened agent profiles (commit-ready)
# ---------------------------------------------------------------------------
agent_update:
	$(call log_build,Generating flattened agent profiles...)

	$(MAKE) sync_copilot

	$(call log_ok,Agent profiles ready in .github/agents/generated/)

# ---------------------------------------------------------------------------
# agent_check: dry-run -- show what would be generated without writing files
# ---------------------------------------------------------------------------
agent_check:
	$(call log_info,Dry-run: checking agent profiles...)
	cd $(REPO_ROOT) && python3 build/py/gen_agents.py --dry-run

# ---------------------------------------------------------------------------
# sync_continue: update ~/.continue/config.yaml systemMessage from MD files
# ~/.continue is mounted as /host-continue inside the container.
# ---------------------------------------------------------------------------
sync_continue:
	$(call log_build,Syncing Continue agent config from project MD files...)
	cd $(REPO_ROOT) && python3 build/py/sync_continue.py
	$(call log_ok,Continue config updated.)

# ---------------------------------------------------------------------------
# sync_copilot: regenerate all flattened agent profiles (commit-ready)
# ---------------------------------------------------------------------------
sync_copilot:
	$(call log_build,Syncing Copilot agent config from project MD files...)
	cd $(REPO_ROOT) && python3 build/py/gen_agents.py
	$(call log_ok,Copilot config updated.)

# ---------------------------------------------------------------------------
# bench_models: token counting + model benchmark
# ---------------------------------------------------------------------------
bench_models:
	$(call log_build,Running token-count summary and model benchmark...)
	@cd $(REPO_ROOT) && python3 build/py/tools/token_count.py --cards gotdot/assets/data/card_database.json --summary
	@cd $(REPO_ROOT) && \
	if [ -z "$(MODEL)" -a -z "$(CMD_TEMPLATE)" ]; then \
		echo "MODEL and CMD_TEMPLATE not set; skipping model benchmark."; \
		echo "To run benchmarks set MODEL and PROMPT, e.g.: make bench_models MODEL=my-model PROMPT='Hello'"; \
	else \
		if [ -z "$(PROMPT)" -a -z "$(PROMPT_FILE)" ]; then \
			echo "Provide PROMPT or PROMPT_FILE when MODEL/CMD_TEMPLATE is set"; exit 1; \
		fi; \
		python3 build/py/tools/bench_model.py --model "$(MODEL)" --prompt "$(PROMPT)" --iterations $(if $(ITERATIONS),$(ITERATIONS),3); \
	fi
	$(call log_ok,Finished $@.)