# =============================================================================
# make speed - Full project build with intelligent caching and parallelization
# =============================================================================
# Location: build/makefiles/speed.mk
# Purpose: Orchestrate complete LOTR project build from scratch
# Cache-aware, CPU-optimized, phase-gated execution
# =============================================================================

.PHONY: speed speed-clean speed-verify speed-invalidate \
       __PREBUILD__ __PARALLEL_CORE__ __POSTBUILD__ \
       _speed_phases_0123456789

# -----------------------------------------------------------------------------
# Configuration and Defaults
# -----------------------------------------------------------------------------

# Auto-detect processor count with multiple fallback strategies
NPROCS ?= $(strip $(shell \
  nproc 2>/dev/null || \
  sysctl -n hw.ncpu 2>/dev/null || \
  getconf _NPROCESSORS_ONLN 2>/dev/null || \
  powershell -NoProfile -Command "[System.Environment]::ProcessorCount" 2>/dev/null | grep -o '[0-9][0-9]*' || \
  echo 4))

ifeq ($(NPROCS),)
NPROCS := 4
endif

# Cache directories for speed artifacts (gitignored by default)
SPEED_CACHE_DIR     := $(REPO_ROOT)/.speed-cache
# NOTE: real build output root is build/do/ (see build/do/assets, build/do/godot).
# The top-level do/ directory is a SEPARATE tree used only by the agent/LLM
# fine-tuning pipeline (build/agent/agent.mk's MODEL_DIR=do/agent/models) and
# is unrelated to `make speed`'s wiki/godot/admin/server outputs. Do not
# confuse the two -- see the caching-convention note above PREBUILD_TARGETS.
ASSETS_CACHE_DIR    := $(REPO_ROOT)/build/do/assets/.cache
AGENT_CACHE_DIR     := $(REPO_ROOT)/build/docker/cache/agent

# -----------------------------------------------------------------------------
# CACHING RULE (mandatory for every target listed below)
#
# Every target invoked by `make speed` (PREBUILD/PARALLEL/POSTBUILD) MUST
# implement a skip-if-unchanged caching mechanism so unchanged inputs never
# trigger unnecessary rebuilds:
#   - Filesystem-producing targets: use build/py/wiki/cache_stamp.py
#     (check/update, --input-mode content|stat, --output-mode content|stat).
#     Use "content" mode for small/few inputs, "stat" (size+mtime) for large
#     trees (e.g. card image directories) where full re-hashing is too slow.
#     Stamps live under build/do/<topic>/.cache/<target>.stamp.json.
#   - Docker-image-producing targets: rely on Docker's own BuildKit layer
#     cache (requires a correct .dockerignore so the build context doesn't
#     include volatile/ephemeral files like .venv/ or __pycache__/).
#   - Verification/test targets (e.g. server_test) are intentionally EXEMPT --
#     they are correctness gates, not build artifacts, and must always run.
#
# Build output organization: all filesystem build artifacts live under
# build/do/<topic>/<subtopic>/ (e.g. build/do/wiki assets under
# build/do/assets/{wiki,cards,database}, Godot export under build/do/godot/).
# The top-level do/ directory is a SEPARATE tree owned by the agent/LLM
# fine-tuning pipeline (build/agent/agent.mk) -- do not mix the two.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Phase Definitions - Organized by dependency order and parallelization potential
# -----------------------------------------------------------------------------

# PREBUILD: Must complete before any other phase starts
# These are data-gathering operations that feed into subsequent builds

# Phase A: must run first (sequential) -- downloads wiki pages/card data/images
PREBUILD_GATHER_TARGETS = \
    wiki_gather_sites

# Phase B: independent post-gather steps -- no inter-dependencies, safe to
# run concurrently (each writes its own cache stamp file).
PREBUILD_PARALLEL_TARGETS = \
    wiki_process_card_images \
    wiki_create_xlist_databases \
    wiki_create_starter_database

# Phase C: needs Phase B's xlist/errata databases (for on_xlist/has_errata
# annotation) and card_database.json (for game logic parsing) -- sequential
PREBUILD_DB_TARGETS = \
    wiki_create_lotr_database \
    wiki_parse_game_logic

# PARALLEL_CORE: Can run concurrently with each other (no inter-dependencies)
PARALLEL_TARGETS = \
    server_install_dev \
    admin_install \
    godot_export \
	server_docker_build

# POSTBUILD: Runs after all builds complete, for verification and testing
POSTBUILD_TARGETS = \
    server_test \
    wiki_game_asset_creation

# -----------------------------------------------------------------------------
# Main speed target - orchestrates everything in order
# -----------------------------------------------------------------------------

speed: $(SPEED_CACHE_DIR) $(ASSETS_CACHE_DIR)

	$(call log_info,=== make speed ===)
	$(call log_info,Building full LOTR project with intelligent caching)
	$(call log_info,Detected processors: $(NPROCS))
	@echo ""

	# Phase 0-1: Prebuild (sequential - data gathering must complete first)
	$(call log_info,[1/3] Starting prebuild phase)
	@echo ">>> PHASE PREBUILD/4: Data Gathering"
	$(MAKE) --no-print-directory \
	    -e 'PREBUILD_GATHER_TARGETS=$(PREBUILD_GATHER_TARGETS)' \
	    $(PREBUILD_GATHER_TARGETS)
	@echo ">>> PHASE PREBUILD/4: Card Images + X-List/Errata/Starter Databases ($(NPROCS) jobs)"
	$(MAKE) --no-print-directory --output-sync=line -j$(NPROCS) \
	    -e 'PREBUILD_PARALLEL_TARGETS=$(PREBUILD_PARALLEL_TARGETS)' \
	    $(PREBUILD_PARALLEL_TARGETS)
	@echo ">>> PHASE PREBUILD/4: Card Database + Game Logic"
	$(MAKE) --no-print-directory \
	    -e 'PREBUILD_DB_TARGETS=$(PREBUILD_DB_TARGETS)' \
	    $(PREBUILD_DB_TARGETS)
	$(call log_ok,[1/3] Prebuild phase complete)

	# Phase 2-3: Parallel core (run all parallel targets concurrently)
	# NOTE: --output-sync=line (not "target") is used deliberately -- "target"
	# buffers ALL output of a recipe until the whole target finishes, which
	# makes long-running targets (Godot asset export, docker build) look stuck
	# for minutes at a time. "line" still prevents interleaved/garbled lines
	# from concurrent jobs but streams output as soon as each line is produced.
	$(call log_info,[2/3] Starting parallel core phase ($(NPROCS) jobs))
	@echo ">>> PHASE PARALLEL/4: Core Builds ($(NPROCS) jobs)"
	$(MAKE) --no-print-directory --output-sync=line -j$(NPROCS) \
	    -e 'PARALLEL_TARGETS=$(PARALLEL_TARGETS)' \
	    $(PARALLEL_TARGETS)
	$(call log_ok,[2/3] Parallel core phase complete)

	# Phase 4-5: Postbuild (verification after all builds complete)
	$(call log_info,[3/3] Starting postbuild verification)
	@echo ">>> PHASE POSTBUILD/4: Verification"
	$(MAKE) --no-print-directory \
	    -e 'POSTBUILD_TARGETS=$(POSTBUILD_TARGETS)' \
	    $(POSTBUILD_TARGETS)
	$(call log_ok,[3/3] Postbuild verification complete)

	$(call log_ok,=== make speed completed successfully ===)

# -----------------------------------------------------------------------------
# Cache directory creation (idempotent)
# -----------------------------------------------------------------------------

$(SPEED_CACHE_DIR):
	mkdir -p $@

$(ASSETS_CACHE_DIR):
	mkdir -p $@

# -----------------------------------------------------------------------------
# Clean targets for make speed cache only (preserves source files)
# -----------------------------------------------------------------------------

speed-clean:
	@echo "Cleaning make speed cache directories..."
	rm -rf "$(SPEED_CACHE_DIR)"/* 2>/dev/null || true
	rm -rf "$(ASSETS_CACHE_DIR)/.git" 2>/dev/null || true
	touch $(REPO_ROOT)/build/do/assets/.force-rebuild
	$(call log_ok,Speed cache cleaned (preserving source files))

# -----------------------------------------------------------------------------
# Invalidate specific build caches without full clean
# -----------------------------------------------------------------------------

speed-invalidate-assets:
	@echo "Invalidating assets cache..."
	rm -rf "$(ASSETS_CACHE_DIR)/.git" 2>/dev/null || true
	touch $(REPO_ROOT)/build/do/assets/.force-rebuild

speed-invalidate-agent:
	@echo "Invalidating agent build cache..."
	rm -rf "$(AGENT_CACHE_DIR)"/* 2>/dev/null || true
	touch $(REPO_ROOT)/do/agent/models/.force-rebuild

# -----------------------------------------------------------------------------
# Verification target (runs after successful speed build)
# -----------------------------------------------------------------------------

speed-verify: speed
	@echo ""
	@echo "=== Running make speed verification ==="
	@echo ""

	# Verify all expected outputs exist
	for dir in build/do/assets/database build/do/godot build/docker/cache/agent; do \
	    if [ -d "$(REPO_ROOT)/$$dir" ]; then \
	        echo "[✓] $$dir exists"; \
	    else \
	        echo "[✗] $$dir missing!"; exit 1; \
	    fi; \
	done

	# Verify key artifacts
	if [ -f "$(REPO_ROOT)/build/do/assets/database/cards.json" ] || \
	   [ -d "$(REPO_ROOT)/build/do/assets/database/" ]; then \
	    echo "[✓] Asset database present"; \
	else \
	    echo "[✗] Asset database missing!"; exit 1; \
	fi

	if [ -f "$(REPO_ROOT)/build/do/godot/lotr-tcg.x86_64" ] || \
	   [ -d "$(REPO_ROOT)/build/do/godot/" ]; then \
	    echo "[✓] Godot export present"; \
	else \
	    echo "[✗] Godot export missing!"; exit 1; \
	fi

	$(call log_ok,All verifications passed)

