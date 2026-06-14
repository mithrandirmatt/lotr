# Top-level convenience wrapper.
# Allows running `make <target>` from repo root by delegating to build/makefile.

.DEFAULT_GOAL := help

help:
	@echo "LotR build wrapper"
	@echo "Examples:"
	@echo "  make agent_build"
	@echo "  make lora_build"
	@echo "  make agentic_build"

%:
	@$(MAKE) -C build -f makefile $@
