## AI helpers

# ai_list: list Ollama models visible to the running Ollama container
# Uses the WSL distro 'lotr-docker-service' to invoke docker so the same
# environment used by `build/docker/docker.ps1` is respected.
ai_list:
	@echo "Listing Ollama models from Docker..."
	@/workspace/build/docker/scripts/ai_list.sh

