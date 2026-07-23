# Server build & run targets
DOCKER_REGISTRY ?= docker.io/yourname
DOCKER_TAG ?= latest

server_build_wheel:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && \
	if [ ! -d .venv ]; then python3 -m venv .venv; fi && \
	. .venv/bin/activate && \
	python -m pip install --upgrade pip build wheel setuptools && \
	python -m build
	$(call log_ok,Finished $@.)

# NOTE: INSTALL_STAMP intentionally lives outside REPO_ROOT (which is a host
# bind mount that persists across container recreations). The dev container
# itself is ephemeral (--rm), so installed site-packages do NOT persist, but a
# stamp file under $(REPO_ROOT) would -- causing `server_install_dev` to be
# skipped as "already done" in a fresh container that has no pytest/deps
# installed at all (surfaces as "pytest: not found" in server_test). Keeping
# the stamp in /root/.cache ties its lifetime to the container instead.
INSTALL_STAMP := /root/.cache/lotr-server-install-stamp

$(INSTALL_STAMP): $(REPO_ROOT)/server/pyproject.toml
	$(call log_build,server_install_dev...)
	@mkdir -p $(dir $(INSTALL_STAMP))
	@cd $(REPO_ROOT)/server && python3 -m pip install --break-system-packages --root-user-action=ignore -q -e .[tests]
	@touch $(INSTALL_STAMP)
	$(call log_ok,Finished server_install_dev.)

server_install_dev: $(INSTALL_STAMP)

server_docker_build:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && docker build -t lotr-server:$(DOCKER_TAG) .
	$(call log_ok,Finished $@.)

server_docker_compose_up:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server/docker && docker compose up -d --build
	$(call log_ok,Finished $@.)

server_run:
	$(call log_build,$@...)
	@cd $(REPO_ROOT) && docker run --rm -p 8000:8000 lotr-server:$(DOCKER_TAG)
	$(call log_ok,Finished $@.)

server_run_dev: $(INSTALL_STAMP)
	$(call log_build,$@...)
	@pkill -f "server.cli" 2>/dev/null || true; pkill -f "uvicorn" 2>/dev/null || true; sleep 0.5
	@cd $(REPO_ROOT)/server && python3 -m server.cli --dev
	$(call log_ok,Finished $@.)

server_stop_compose:
	@cd $(REPO_ROOT)/server/docker && docker compose down || true

server_docker_push:
	$(call log_build,$@...)
	@docker tag lotr-server:$(DOCKER_TAG) $(DOCKER_REGISTRY)/lotr-server:$(DOCKER_TAG)
	@docker push $(DOCKER_REGISTRY)/lotr-server:$(DOCKER_TAG)
	$(call log_ok,Finished $@.)

server_test:
	$(call log_build,$@...)
	@cd $(REPO_ROOT)/server && pytest -q
	$(call log_ok,Finished $@.)

server_all: server_build_wheel server_docker_build

# ============================================================
# lotr-server -- server container management
#
# This section adds targets for managing the server Docker container.
# The server container is automatically started by the godot_play target.
# ============================================================

.PHONY: server_container_start server_container_stop server_container_status

SERVER_CONTAINER := lotr-server
SERVER_IMAGE := lotr-server
SERVER_PORT := 8000

# ---------------------------------------------------------------------------
# server_container_start: build and start the server container
# ---------------------------------------------------------------------------
server_container_start:
	$(call log_build,Building server container...)
	@docker build -t $(SERVER_IMAGE) build/docker/
	$(call log_build,Starting server container...)
	@docker run -d \
	    --name $(SERVER_CONTAINER) \
	    --restart unless-stopped \
	    -p $(SERVER_PORT):$(SERVER_PORT) \
	    $(SERVER_IMAGE)
	$(call log_ok,Server container started successfully.)
	$(call log_ok,Server is running at http://localhost:$(SERVER_PORT))

# ---------------------------------------------------------------------------
# server_container_stop: stop and remove the server container
# ---------------------------------------------------------------------------
server_container_stop:
	$(call log_build,Stopping server container...)
	@docker stop $(SERVER_CONTAINER) 2>/dev/null || true
	@docker rm $(SERVER_CONTAINER) 2>/dev/null || true
	$(call log_ok,Server container stopped and removed.)

# ---------------------------------------------------------------------------
# server_container_status: check if server is running
# ---------------------------------------------------------------------------
server_container_status:
	@docker ps -a --filter "name=$(SERVER_CONTAINER)" --format "{{.Status}}"
	@if docker ps -q --filter "name=$(SERVER_CONTAINER)" | grep -q .; then \
		$(call log_ok,Server is running.); \
		$(call log_build,Health check:); \
		curl -s http://localhost:$(SERVER_PORT)/health 2>/dev/null || $(call log_warn,Health check failed (server may not be ready yet)); \
	else \
		$(call log_warn,Server is not running.); \
	fi

# ---------------------------------------------------------------------------
# server_container_logs: view server logs
# ---------------------------------------------------------------------------
server_container_logs:
	$(call log_build,Server logs:)
	@docker logs --tail 100 $(SERVER_CONTAINER)

