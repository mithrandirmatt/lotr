
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
GODOT_CACHE_DIR  := $(GODOT_EXPORT_DIR)/.cache
GODOT_STAMP_TOOL := $(REPO_ROOT)/build/py/wiki/cache_stamp.py
GODOT_EXPORT_STAMP := $(GODOT_CACHE_DIR)/godot_export.stamp.json
# stat mode for inputs: gotdot/assets contains thousands of card PNGs synced
# from wiki_game_asset_creation -- full content hashing would be too slow.
GODOT_STAMP_CHECK_FLAGS := --verbose --trust-output-stamp --input-mode stat --output-mode stat
GODOT_STAMP_UPDATE_FLAGS := --input-mode stat --output-mode stat
GODOT_PROGRESS_TOOL := $(REPO_ROOT)/build/py/tools/stream_progress.py

# ---------------------------------------------------------------------------
# godot_play: open a window.
# Requires DISPLAY to be set -- automatically available when launched via
# docker.ps1 run on a host with WSLg (Windows 11 / Win10 21H2+).
#
# Runs the FastAPI server directly inside the dev container (uvicorn in the
# background) then launches Godot. Cleans up the server process on exit.
#
# Alternative (Docker-in-Docker): if you need the server running as its own
# container, launch the dev shell (the Docker socket is mounted by default;
# pass -NoMountDockerSocket to opt out):
#   docker.ps1 run
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
	$(GODOT_BIN) --rendering-driver opengl3 --maximized --path $(GODOT_PROJECT) || true
	$(call log_ok,Godot exited. Stopping server...)
	@SERVER_PID=$$(cat $(SERVER_PID_FILE)); \
	kill $$SERVER_PID 2>/dev/null || true
	@rm -f $(SERVER_PID_FILE)

# ---------------------------------------------------------------------------
# godot_play_docker: like godot_play but starts the server as a Docker
# container. Requires the dev container's Docker socket to be mounted
# (mounted by default; pass -NoMountDockerSocket to docker.ps1 to opt out).
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
	$(GODOT_BIN) --rendering-driver opengl3 --maximized --path $(GODOT_PROJECT) || true
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
#
# NOTE: stdbuf -oL -eL forces line-buffered stdout/stderr. Godot's own C
# runtime fully-buffers output when stdout isn't a TTY (i.e. always, when
# piped through `make`), so without this the export can appear "stuck" for
# minutes at a time even with --output-sync=line at the make level -- Godot
# just hasn't flushed its internal buffer yet. stdbuf forces a flush per line
# so progress (asset imports, savepack steps) streams in real time.
#
# NOTE: the final "savepack" phase (packing every project file into the
# .pck) prints one `savepack: step N: Storing File: ...` line per file, but
# N is the *phase* number and does not increment per file -- with thousands
# of card images this looks identical to a hang even though it's actively
# streaming real lines. stream_progress.py wraps the pipeline to emit a
# "[progress] N files processed (elapsed Xs)" heartbeat to stderr so it's
# clear packing is still moving. It never touches the piped command's exit
# status -- that's captured explicitly via the $$? > file dance below (POSIX
# sh has no PIPESTATUS, so the exit code must be saved before the pipe).
#
# Cached via cache_stamp.py (stat mode -- gotdot/assets holds thousands of
# card PNGs, so full content hashing is skipped for speed): re-exports only
# when project.godot, export_presets.cfg, scenes/, scripts/, or assets/
# change since the last successful export.
# ---------------------------------------------------------------------------
godot_export:
	$(call log_info,Checking cache for $@...)
	@mkdir -p $(GODOT_EXPORT_DIR) $(GODOT_CACHE_DIR)
	@cd $(REPO_ROOT) && if python3 $(GODOT_STAMP_TOOL) check $(GODOT_STAMP_CHECK_FLAGS) \
		--label godot_export \
		--stamp $(GODOT_EXPORT_STAMP) \
		--input gotdot/project.godot \
		--input gotdot/export_presets.cfg \
		--input gotdot/scenes \
		--input gotdot/scripts \
		--input gotdot/assets \
		--output build/do/godot/lotr-tcg.x86_64 \
		--output build/do/godot/lotr-tcg.pck ; then \
		echo "[INFO] Skipping godot_export (input/output checksums unchanged)"; \
	else \
		echo "[INFO] Cache miss for godot_export; running build step"; \
		printf "\033[1;33m[BUILD]\t%s\033[0m\n" "godot_export..."; \
		exit_stamp="$(GODOT_CACHE_DIR)/godot_export.exitcode.$$$$"; \
		( stdbuf -oL -eL $(GODOT_BIN) --headless --path $(GODOT_PROJECT) \
		    --export-release "Linux/X11" $(GODOT_EXPORT_DIR)/lotr-tcg.x86_64 ; \
		  echo $$? > "$$exit_stamp" ) | \
		python3 $(GODOT_PROGRESS_TOOL) --match "Storing File:" --label "files packed"; \
		godot_exit=$$(cat "$$exit_stamp"); rm -f "$$exit_stamp"; \
		if [ "$$godot_exit" -ne 0 ]; then exit "$$godot_exit"; fi; \
		python3 $(GODOT_STAMP_TOOL) update $(GODOT_STAMP_UPDATE_FLAGS) \
			--label godot_export \
			--stamp $(GODOT_EXPORT_STAMP) \
			--input gotdot/project.godot \
			--input gotdot/export_presets.cfg \
			--input gotdot/scenes \
			--input gotdot/scripts \
			--input gotdot/assets \
			--output build/do/godot/lotr-tcg.x86_64 \
			--output build/do/godot/lotr-tcg.pck ; \
	fi
	$(call log_ok,Export complete: $(GODOT_EXPORT_DIR)/lotr-tcg.x86_64)

