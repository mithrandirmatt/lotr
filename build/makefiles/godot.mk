
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

.PHONY: godot_play godot_run godot_test godot_export

GODOT_PROJECT    := $(REPO_ROOT)/gotdot
GODOT_BIN        ?= godot
GODOT_EXPORT_DIR := $(REPO_ROOT)/build/do/godot

# ---------------------------------------------------------------------------
# godot_play: open a window.
# Requires DISPLAY to be set -- automatically available when launched via
# docker.ps1 run on a host with WSLg (Windows 11 / Win10 21H2+).
# ---------------------------------------------------------------------------
godot_play:
	$(call log_build,Running Godot project with display...)
	$(GODOT_BIN) --rendering-driver opengl3 --path $(GODOT_PROJECT)
	$(call log_ok,Godot exited.)

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
