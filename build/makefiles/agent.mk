
# =============================================================================
# agent.mk -- agent sync targets
#
# agent_update:
#   Prepares all agent files ready to commit. No git operations are performed.
#   1. Flatten each .github/agents/*.agent.md profile (resolve includes:) into
#      .github/agents/generated/ via build/py/gen_agents.py
# =============================================================================

.PHONY: agent_update agent_check sync_continue

# ---------------------------------------------------------------------------
# agent_update: regenerate all flattened agent profiles (commit-ready)
# ---------------------------------------------------------------------------
agent_update:
	$(call log_build,Generating flattened agent profiles...)

	$(MAKE) sync_copilot sync_continue

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