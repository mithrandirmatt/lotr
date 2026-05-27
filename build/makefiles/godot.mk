
# =============================================================================
# godot.mk -- Godot 4 project targets
#
# Assumes make is run from inside the lotr-dev container, where the Godot
# headless binary is available at /usr/local/bin/godot (in PATH).
#
# To override the binary (e.g. Windows native Godot):
#   make godot_run GODOT_BIN=/path/to/godot.exe
#
# Targets:
#   godot_run    -- run project headless (smoke-test: opens, logs, then quits)
#   godot_test   -- run headless tests (swap --quit for test runner later)
#   godot_export -- export Linux/X11 release binary to build/do/godot/
# =============================================================================

.PHONY: godot_play godot_play_docker godot_run godot_test godot_export

GODOT_PROJECT    := $(REPO_ROOT)/gotdot
GODOT_BIN        ?= godot
GODOT_EXPORT_DIR := $(REPO_ROOT)/build/do/godot

# ---------------------------------------------------------------------------
# godot_play: open a window.
# Requires DISPLAY to be set -- automatically available when launched via
# docker.ps1 run on a host with WSLg (Windows 11 / Win10 21H2+).
#
# Runs the FastAPI server directly inside the dev container (uvicorn in the
# background) then launches Godot. Cleans up the server process on exit.
#
# Alternative (Docker-in-Docker): if you need the server running as its own
# container, launch the dev shell with the Docker socket mounted:
#   docker.ps1 run -MountDockerSocket
# then run: make godot_play_docker
# ---------------------------------------------------------------------------
SERVER_PID_FILE := /tmp/lotr-server.pid
SERVER_LOG      := /tmp/lotr-server.log

godot_play:
	$(call log_build,Starting LOTR server on port 8000...)
	@cd $(REPO_ROOT)/server && \
	    echo "[BUILD] Starting server..." && \
	    python3 -m uvicorn server.app:app \
	        --host 127.0.0.1 --port 8000 \
	        --log-level debug \
	        > $(SERVER_LOG) 2>&1 & \
	    echo $$! > $(SERVER_PID_FILE)
	@sleep 2
	@SERVER_PID=$$(cat $(SERVER_PID_FILE)); \
	if kill -0 $$SERVER_PID 2>/dev/null; then \
	    echo "[OK] Server running (PID=$$SERVER_PID)."; \
	else \
	    echo "[WARNING] Server failed to start. Check logs:"; \
	    echo "  - /tmp/pip-install.log"; \
	    echo "  - /tmp/server-import.log"; \
	    echo "  - $(SERVER_LOG)"; \
	    if [ -f $(SERVER_LOG) ]; then cat $(SERVER_LOG); fi; \
	fi
	$(call log_build,Starting Godot project with display...)
	$(GODOT_BIN) --rendering-driver opengl3 --path $(GODOT_PROJECT) || true
	$(call log_ok,Godot exited. Stopping server...)
	@SERVER_PID=$$(cat $(SERVER_PID_FILE)); \
	kill $$SERVER_PID 2>/dev/null || true
	@rm -f $(SERVER_PID_FILE)

# ---------------------------------------------------------------------------
# godot_play_docker: like godot_play but starts the server as a Docker
# container. Requires the dev container was launched with -MountDockerSocket:
#   docker.ps1 run -MountDockerSocket
# ---------------------------------------------------------------------------
godot_play_docker:
	$(call log_build,Starting lotr-server container on port 8000...)
	@docker rm -f lotr-server 2>/dev/null || true
	@docker run -d \
	    --name lotr-server \
	    --network lotr-net \
	    -p 8000:8000 \
	    lotr-server
	@sleep 2
	$(call log_build,Starting Godot project with display...)
	$(GODOT_BIN) --rendering-driver opengl3 --path $(GODOT_PROJECT) || true
	$(call log_ok,Godot exited. Stopping server container...)
	@docker stop lotr-server 2>/dev/null || true
	@docker rm lotr-server 2>/dev/null || true

# ---------------------------------------------------------------------------
# godot_run: launch the project headless (smoke test / CI)
# ---------------------------------------------------------------------------
godot_run:
	$(call log_build,Running Godot project headless...)
	$(GODOT_BIN) --headless --path $(GODOT_PROJECT) --quit
	$(call log_ok,Godot run complete.)

# ---------------------------------------------------------------------------
# godot_test: run headless tests
# Replace --quit with a GUT or custom test-runner scene path when tests exist.
# ---------------------------------------------------------------------------
godot_test:
	$(call log_build,Running Godot tests headless...)
	$(GODOT_BIN) --headless --path $(GODOT_PROJECT) --quit
	$(call log_ok,Godot tests passed.)

# ---------------------------------------------------------------------------
# godot_export: export a Linux/X11 release binary
# Requires export templates to be installed in the image (done in Dockerfile).
# Requires an export_presets.cfg to be present in the Godot project.
# ---------------------------------------------------------------------------
godot_export:
	$(call log_build,Exporting Godot project to $(GODOT_EXPORT_DIR)...)
	@mkdir -p $(GODOT_EXPORT_DIR)
	$(GODOT_BIN) --headless --path $(GODOT_PROJECT) \
	    --export-release "Linux/X11" $(GODOT_EXPORT_DIR)/lotr-tcg.x86_64
	$(call log_ok,Export complete: $(GODOT_EXPORT_DIR)/lotr-tcg.x86_64)
