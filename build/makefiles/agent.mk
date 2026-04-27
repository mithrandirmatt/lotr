
# =============================================================================
# agent.mk -- agent sync targets
#
# agent_update:
#   Prepares all agent files ready to commit. No git operations are performed.
#   1. Flatten each .github/agents/*.agent.md profile (resolve includes:) into
#      .github/agents/generated/ via build/py/gen_agents.py
# =============================================================================

.PHONY: agent_update agent_check

# ---------------------------------------------------------------------------
# agent_update: regenerate all flattened agent profiles (commit-ready)
# ---------------------------------------------------------------------------
agent_update:
	$(call log_build,Generating flattened agent profiles...)
	cd $(REPO_ROOT) && python3 build/py/gen_agents.py
	$(call log_ok,Agent profiles ready in .github/agents/generated/)

# ---------------------------------------------------------------------------
# agent_check: dry-run -- show what would be generated without writing files
# ---------------------------------------------------------------------------
agent_check:
	$(call log_info,Dry-run: checking agent profiles...)
	cd $(REPO_ROOT) && python3 build/py/gen_agents.py --dry-run

