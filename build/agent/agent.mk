REPO_ROOT ?= $(CURDIR)/..
AGENT_PROFILE ?= rx7900xtx-agentic
AGENT_MODEL_CONFIG ?= qwen35-9b
AGENT_CORPUS_MODEL ?= $(AGENT_MODEL_CONFIG)
QUANTIZATION ?= 4bit
AGENT_BASE_MODEL ?=
AGENT_HF_BASE_MODEL ?=
MODEL_DIR ?= $(REPO_ROOT)/do/agent/models
OLLAMA_AGENTIC_MODEL_NAME := lotr-agentic-$(AGENT_PROFILE)
OLLAMA_LORA_MODEL_NAME := $(AGENT_MODEL_CONFIG)_lotr_lora
OLLAMA_HOST ?= http://host.docker.internal:11434
OLLAMA_USE_LOCAL_DAEMON ?= 0
LORA_ALLOW_CPU ?= 0
# ROCm's Triton backend can stall for a long time compiling the AMDGCN autotune
# candidates for flash-linear-attention's Gated DeltaNet backward kernel (Qwen3.5)
# on the very first backward pass of a fresh container. That fla/Triton path is
# also the memory-efficient one (fused, half-precision) -- the plain-torch
# fallback (LORA_DISABLE_FLA=1) upcasts to fp32 and keeps many more autograd
# intermediates alive, which OOM'd on a 24GB GPU at max_seq_length=4096 even
# though it avoided the compile stall. Default this OFF (use fla/Triton) and
# rely on AGENT_TRITON_CACHE_DIR below to persist compiled kernels across
# container restarts, so the slow compile only ever happens once. Set to 1 only
# as a temporary escape hatch if the compile stall itself needs to be bypassed.
LORA_DISABLE_FLA ?= 0
LORA_GGUF_OUTTYPE ?= q4_k_m
LORA_MAX_STEPS ?=
LORA_MAX_TRAIN_SAMPLES ?=
LORA_LITE_MAX_STEPS ?= 5
LORA_LITE_MAX_TRAIN_SAMPLES ?= 20
AGENT_TORCH_VARIANT ?= auto
LORA_RECREATE_VENV ?= 0
AGENT_CACHE_DIR ?= $(REPO_ROOT)/build/docker/cache
AGENT_PIP_CACHE_DIR ?= $(AGENT_CACHE_DIR)/pip
AGENT_HF_CACHE_DIR ?= $(AGENT_CACHE_DIR)/huggingface
AGENT_TORCH_CACHE_DIR ?= $(AGENT_CACHE_DIR)/torch
# Persists Triton's compiled-kernel cache across runs, so the one-time ROCm
# AMDGCN compile for fla's Gated DeltaNet kernels only ever happens once.
# Deliberately NOT under AGENT_CACHE_DIR (which lives on the /workspace bind
# mount, i.e. WSL2's 9p/drvfs passthrough to the Windows host filesystem --
# measured ~30x slower than native fs for the many small files Triton/LLVM
# codegen writes, which can turn a ~45-60 min first compile into multiple
# hours). Instead this points at the 'lotr-agent-triton-cache' named Docker
# volume (backed by the WSL2 distro's own ext4), mounted by docker.ps1 at
# /root/.cache/lotr-triton-cache -- fast AND persistent across container runs.
AGENT_TRITON_CACHE_DIR ?= /root/.cache/lotr-triton-cache
# Same rationale as AGENT_TRITON_CACHE_DIR above: the LoRA venv used to live at
# $(AGENT_VENV_DIR), i.e. on the /workspace 9p/drvfs
# bind mount. Every reinstall of a package with many files (e.g. transformers,
# which ships ~1000+ files) has to delete+recreate them all on that slow
# filesystem -- confirmed via strace-equivalent (process stuck in D state) to
# take minutes per package and a likely major contributor to multi-hour/day
# dependency-install stalls. Now points at the 'lotr-agent-venv' named Docker
# volume (backed by the WSL2 distro's own ext4), mounted by docker.ps1 at
# /root/.cache/lotr-agent-venv -- fast AND persistent across container runs.
AGENT_VENV_DIR ?= /root/.cache/lotr-agent-venv
AGENT_PYTHON ?= $(AGENT_VENV_DIR)/bin/python
AGENT_PIP_BINARY_FLAGS ?= --prefer-binary --only-binary=:all:
AGENT_COMPILE_JOBS ?= auto
AGENT_UV ?= $(shell command -v uv 2>/dev/null)
AGENT_PIP_CMD ?= $(if $(strip $(AGENT_UV)),uv pip --python $(AGENT_PYTHON),$(AGENT_PYTHON) -m pip)
AGENT_PIP_BREAK_SYSTEM ?= $(if $(strip $(AGENT_UV)),,--break-system-packages)
AGENT_PIP_INSTALL_PROGRESS_FLAGS ?= $(if $(strip $(AGENT_UV)),--verbose,--progress-bar on --verbose)
AGENT_INSTALL_HEARTBEAT_SECS ?= 20
# The bitsandbytes ROCm source build below is installed into the venv via
# `pip install --no-deps "$(AGENT_BNB_ROCM_BUILD_DIR)"`. --no-deps is
# deliberate: without it, pip resolves bitsandbytes' generic (non-ROCm)
# torch/numpy/etc. requirement pins from PyPI on a fresh venv (torch isn't
# installed yet at this point in the recipe), downloading a throwaway ~1GB+
# CUDA-flavored torch/cudnn/cuda-toolkit stack that gets uninstalled and
# replaced by the ROCm torch wheel moments later anyway. The already-compiled
# libbitsandbytes_rocm*.so is all this step needs to install; torch/numpy are
# installed properly by the ROCm torch bootstrap and requirements-lora.txt
# steps that follow.
AGENT_BNB_ROCM_ENSURE ?= 1
AGENT_BNB_ROCM_BUILD_DIR ?= /tmp/bnb-rocm-build
AGENT_HIP_PATH ?= $(firstword $(wildcard /opt/rocm /usr))
AGENT_COMPILE_JOBS_VALUE ?= $(if $(filter auto,$(AGENT_COMPILE_JOBS)),$(shell nproc 2>/dev/null || echo 4),$(AGENT_COMPILE_JOBS))
AGENT_PIP_BUILD_ENV ?= MAX_JOBS=$(AGENT_COMPILE_JOBS_VALUE) CMAKE_BUILD_PARALLEL_LEVEL=$(AGENT_COMPILE_JOBS_VALUE)
LORA_OUTPUT_DIR := $(MODEL_DIR)/lora/$(AGENT_PROFILE)
LORA_MODELFILE := $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE).lora
LORA_GGUF_MODELFILE := $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE).lora.gguf
LORA_MERGED_DIR := $(MODEL_DIR)/lora-merged/$(AGENT_PROFILE)
LORA_GGUF_TAG := $(shell printf '%s' "$(LORA_GGUF_OUTTYPE)" | tr '[:upper:]' '[:lower:]')
LORA_GGUF := $(MODEL_DIR)/$(AGENT_MODEL_CONFIG)_lotr_lora-$(LORA_GGUF_TAG).gguf
LORA_CACHE_DIR := $(MODEL_DIR)/cache/$(AGENT_PROFILE)
LORA_TRAIN_FP := $(LORA_CACHE_DIR)/lora-train.sha256
LORA_TRAIN_FP_NEW := $(LORA_CACHE_DIR)/lora-train.sha256.new
LORA_TRAIN_DONE := $(LORA_CACHE_DIR)/lora-train.done
LLAMA_CPP_DIR ?= $(AGENT_CACHE_DIR)/llama.cpp
AGENT_SFT_MODEL_CONFIG ?= qwen35-9b
SFT_CORPUS := $(MODEL_DIR)/training/$(AGENT_PROFILE)-sft-corpus.jsonl
SFT_OUTPUT_DIR := $(MODEL_DIR)/lora/$(AGENT_PROFILE)-sft

define AGENT_RUN_WITH_HEARTBEAT
{ \
	( while true; do echo "[pip] still working..."; sleep $(AGENT_INSTALL_HEARTBEAT_SECS); done ) & hb=$$!; \
	$(1); rc=$$?; \
	kill $$hb >/dev/null 2>&1 || true; \
	wait $$hb 2>/dev/null || true; \
	exit $$rc; \
}
endef

.PHONY: agent_clean
agent_clean:
	@echo "Cleaning all agent_build artifacts for a fresh build..."
	@rm -rf $(AGENT_PIP_CACHE_DIR)
	@rm -rf $(AGENT_HF_CACHE_DIR)
	@rm -rf $(AGENT_TORCH_CACHE_DIR)
	@rm -rf $(LLAMA_CPP_DIR)
	@if [ -d "$(AGENT_VENV_DIR)" ]; then \
		rm -rf "$(AGENT_VENV_DIR)" || \
		mv "$(AGENT_VENV_DIR)" "$(AGENT_VENV_DIR)_stale.$$"; \
	fi
	@rm -rf $(AGENT_VENV_DIR)_stale*
	@echo "Removing generated model artifacts at $(MODEL_DIR) (corpus, metadata, Modelfiles, LoRA adapters/merged models, GGUF exports, fingerprint caches)..."
	@rm -rf $(MODEL_DIR)
	@echo "Agent build artifact cleanup complete."

.PHONY: prepare-corpus
prepare-corpus:
	@echo "Preparing corpus/training artifacts for profile $(AGENT_PROFILE)..."
	@python3 -m venv $(AGENT_VENV_DIR)
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.train.py --model "$(AGENT_CORPUS_MODEL)" --quantization "$(QUANTIZATION)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" --data_dir "$(REPO_ROOT)"

.PHONY: install-agent-env
install-agent-env:
	@echo "Installing lotr_agent package into build venv..."
	@echo "Setting Python path to include build directory"
	# Ensure the virtual environment exists in the agent directory
	@mkdir -p $(AGENT_VENV_DIR)
	@python3 -m venv $(AGENT_VENV_DIR)
	# Install once; skip when the package is already available in this venv
	@if $(AGENT_VENV_DIR)/bin/python -c "import importlib.metadata as m; m.version('lotr_agent')" >/dev/null 2>&1; then \
		echo "lotr_agent already installed in venv, skipping reinstall."; \
	else \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) -e $(REPO_ROOT)/build/agent/lotr_agent $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@echo "Installation completed"

.PHONY: profile-modelfile
profile-modelfile:
	@echo "Generating Modelfile for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@python3 -m venv $(AGENT_VENV_DIR)
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_BASE_MODEL)),--base_model "$(AGENT_BASE_MODEL)",) --output "$(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"

.PHONY: lora-train lora-train-run lora-fingerprint
lora-fingerprint: prepare-corpus
	@mkdir -p "$(LORA_CACHE_DIR)"
	@python3 -m venv $(AGENT_VENV_DIR)
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.lora_fingerprint.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" --corpus "$(MODEL_DIR)/training/$(AGENT_PROFILE)-corpus.jsonl" --hf_base_model "$(AGENT_HF_BASE_MODEL)" --allow_cpu "$(LORA_ALLOW_CPU)" --torch_variant "$(AGENT_TORCH_VARIANT)" --output "$(LORA_TRAIN_FP_NEW)"

lora-train: lora-fingerprint
	@echo "Training LoRA adapter for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@if [ -f "$(LORA_OUTPUT_DIR)/adapter_model.safetensors" ] && [ -f "$(LORA_OUTPUT_DIR)/adapter_config.json" ] && { [ ! -f "$(LORA_TRAIN_FP)" ] || cmp -s "$(LORA_TRAIN_FP)" "$(LORA_TRAIN_FP_NEW)"; }; then \
		if [ ! -f "$(LORA_TRAIN_FP)" ]; then \
			echo "Bootstrapping LoRA cache from existing adapter artifacts; skipping retrain."; \
		else \
			echo "LoRA inputs unchanged and adapter artifacts exist; skipping retrain."; \
		fi; \
		mv -f "$(LORA_TRAIN_FP_NEW)" "$(LORA_TRAIN_FP)"; \
		touch "$(LORA_TRAIN_DONE)"; \
	else \
		$(MAKE) -f agent/agent.mk lora-train-run AGENT_PROFILE="$(AGENT_PROFILE)" AGENT_MODEL_CONFIG="$(AGENT_MODEL_CONFIG)" AGENT_HF_BASE_MODEL="$(AGENT_HF_BASE_MODEL)" LORA_ALLOW_CPU="$(LORA_ALLOW_CPU)" AGENT_TORCH_VARIANT="$(AGENT_TORCH_VARIANT)" || exit 1; \
		mv -f "$(LORA_TRAIN_FP_NEW)" "$(LORA_TRAIN_FP)"; \
		touch "$(LORA_TRAIN_DONE)"; \
	fi

lora-train-run: prepare-corpus
	@echo "Training LoRA adapter for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@if [ "$(LORA_RECREATE_VENV)" = "1" ]; then \
		echo "LORA_RECREATE_VENV=1 set; recreating LoRA venv..."; \
		if [ -d "$(AGENT_VENV_DIR)" ]; then \
			rm -rf "$(AGENT_VENV_DIR)" || \
			mv "$(AGENT_VENV_DIR)" "$(AGENT_VENV_DIR)_stale.$$"; \
		fi; \
	fi
	@if [ ! -x "$(AGENT_VENV_DIR)/bin/python" ]; then \
		echo "Creating LoRA venv..."; \
		python3 -m venv $(AGENT_VENV_DIR); \
	else \
		echo "Reusing existing LoRA venv."; \
	fi
	@mkdir -p $(AGENT_PIP_CACHE_DIR)
	@mkdir -p $(AGENT_HF_CACHE_DIR)
	@mkdir -p $(AGENT_TORCH_CACHE_DIR)
	@mkdir -p $(AGENT_TRITON_CACHE_DIR)
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_BNB_ROCM_ENSURE)" = "1" ] && { [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; }; then \
		if [ -f "$(AGENT_VENV_DIR)/.bnb_rocm_ready" ]; then \
			echo "ROCm bitsandbytes bootstrap already completed for this venv."; \
		else \
			echo "Ensuring ROCm-capable bitsandbytes (source build) for quantized loading..."; \
			if ! command -v hipcc >/dev/null 2>&1; then \
				echo "Error: hipcc not found in container; cannot build ROCm bitsandbytes backend."; \
				echo "Install ROCm development toolchain in build/docker/Dockerfile (hipcc + ROCm CMake config), then rerun."; \
				exit 1; \
			fi; \
			export HIP_PATH=$(AGENT_HIP_PATH); \
			rm -rf "$(AGENT_BNB_ROCM_BUILD_DIR)"; \
			git clone --depth 1 --branch rocm_enabled https://github.com/ROCm/bitsandbytes.git "$(AGENT_BNB_ROCM_BUILD_DIR)"; \
			HIP_DEVLIBS=$$(find /opt/rocm*/lib/llvm/lib/clang/*/lib/amdgcn/bitcode -name 'hip.bc' 2>/dev/null | head -1 | xargs dirname 2>/dev/null || echo ""); \
			if [ -z "$$HIP_DEVLIBS" ]; then \
				HIP_DEVLIBS=$$(find /usr/lib/llvm-* -name 'hip.bc' 2>/dev/null | head -1 | xargs dirname 2>/dev/null); \
			fi; \
			HIP_LLVM_VER=$$(echo "$$HIP_DEVLIBS" | grep -oP 'clang/\K[0-9]+' | head -1 || echo "22"); \
			HIP_CLANG=$$(find /opt/rocm*/lib/llvm/bin -name 'clang++' 2>/dev/null | head -1 || command -v "clang++-$$HIP_LLVM_VER" 2>/dev/null || command -v clang++-17 2>/dev/null || ls /usr/bin/clang++-[0-9]* 2>/dev/null | sort -V | head -1); \
			HIP_LLVM_BINDIR=$$(dirname "$$HIP_CLANG" 2>/dev/null || true); \
			ROCM_ROOT=$$(readlink -f /opt/rocm 2>/dev/null || true); \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				ROCM_ROOT=$$(find /opt -maxdepth 1 -type d -name 'rocm-*' 2>/dev/null | sort -V | tail -1); \
			fi; \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				ROCM_ROOT=/usr; \
			fi; \
			HIPBLAS_CFG=$$(find /usr /opt/rocm /opt/rocm-* \( -name 'hipblasConfig.cmake' -o -name 'hipblas-config.cmake' \) 2>/dev/null | head -1); \
			HIPBLAS_DIR=$$(dirname "$$HIPBLAS_CFG" 2>/dev/null || true); \
			if [ -n "$$HIPBLAS_CFG" ]; then \
				ROCM_ROOT=$$(dirname $$(dirname $$(dirname "$$HIPBLAS_DIR" 2>/dev/null) 2>/dev/null) 2>/dev/null); \
			fi; \
			if [ -z "$$HIPBLAS_CFG" ]; then \
				HIPBLAS_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhipblas.so' 2>/dev/null | head -1); \
				if [ -n "$$HIPBLAS_LIB" ]; then \
					HIPBLAS_DIR=/tmp/hipblas-cmake; \
					mkdir -p "$$HIPBLAS_DIR"; \
					printf '%s\n' \
						'set(hipblas_FOUND TRUE)' \
						'if(NOT TARGET roc::hipblas)' \
						'  add_library(roc::hipblas SHARED IMPORTED)' \
						"  set_target_properties(roc::hipblas PROPERTIES IMPORTED_LOCATION \"$$HIPBLAS_LIB\")" \
						'endif()' \
						'if(NOT TARGET hipblas::hipblas)' \
						'  add_library(hipblas::hipblas INTERFACE IMPORTED)' \
						'  target_link_libraries(hipblas::hipblas INTERFACE roc::hipblas)' \
						'endif()' \
						> "$$HIPBLAS_DIR/hipblas-config.cmake"; \
					printf '%s\n' \
						'set(PACKAGE_VERSION "0")' \
						'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
						'set(PACKAGE_VERSION_EXACT TRUE)' \
						> "$$HIPBLAS_DIR/hipblas-config-version.cmake"; \
				else \
					echo "Error: hipblasConfig.cmake and libhipblas.so were not found in this image."; \
					exit 1; \
				fi; \
			fi; \
			HIPRAND_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhiprand.so' 2>/dev/null | head -1); \
			if [ -n "$$HIPRAND_LIB" ]; then \
				HIPRAND_DIR=/tmp/hiprand-cmake; \
				mkdir -p "$$HIPRAND_DIR"; \
				printf '%s\n' \
					'set(hiprand_FOUND TRUE)' \
					'if(NOT TARGET hip::hiprand)' \
					'  add_library(hip::hiprand SHARED IMPORTED)' \
					"  set_target_properties(hip::hiprand PROPERTIES IMPORTED_LOCATION \"$$HIPRAND_LIB\")" \
					'endif()' \
					'if(NOT TARGET hiprand::hiprand)' \
					'  add_library(hiprand::hiprand INTERFACE IMPORTED)' \
					'  target_link_libraries(hiprand::hiprand INTERFACE hip::hiprand)' \
					'endif()' \
					> "$$HIPRAND_DIR/hiprand-config.cmake"; \
				printf '%s\n' \
					'set(PACKAGE_VERSION "0")' \
					'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
					'set(PACKAGE_VERSION_EXACT TRUE)' \
					> "$$HIPRAND_DIR/hiprand-config-version.cmake"; \
			else \
				echo "Error: hiprand config and libhiprand.so were not found in this image."; \
				exit 1; \
			fi; \
				HIPSPARSE_CFG=$$(find /usr /opt/rocm /opt/rocm-* \( -name 'hipsparseConfig.cmake' -o -name 'hipsparse-config.cmake' \) 2>/dev/null | head -1); \
				HIPSPARSE_DIR=$$(dirname "$$HIPSPARSE_CFG" 2>/dev/null || true); \
				if [ -z "$$HIPSPARSE_CFG" ]; then \
					HIPSPARSE_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhipsparse.so' 2>/dev/null | head -1); \
					if [ -n "$$HIPSPARSE_LIB" ]; then \
						HIPSPARSE_DIR=/tmp/hipsparse-cmake; \
						mkdir -p "$$HIPSPARSE_DIR"; \
						printf '%s\n' \
							'set(hipsparse_FOUND TRUE)' \
							'if(NOT TARGET roc::hipsparse)' \
							'  add_library(roc::hipsparse SHARED IMPORTED)' \
							"  set_target_properties(roc::hipsparse PROPERTIES IMPORTED_LOCATION \"$$HIPSPARSE_LIB\")" \
							'endif()' \
							'if(NOT TARGET hipsparse::hipsparse)' \
							'  add_library(hipsparse::hipsparse INTERFACE IMPORTED)' \
							'  target_link_libraries(hipsparse::hipsparse INTERFACE roc::hipsparse)' \
							'endif()' \
							> "$$HIPSPARSE_DIR/hipsparse-config.cmake"; \
						printf '%s\n' \
							'set(PACKAGE_VERSION "0")' \
							'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
							'set(PACKAGE_VERSION_EXACT TRUE)' \
							> "$$HIPSPARSE_DIR/hipsparse-config-version.cmake"; \
					else \
						echo "Error: hipsparse config and libhipsparse.so were not found in this image."; \
						exit 1; \
					fi; \
				fi; \
			HIP_LANG_DIR=$$(find "$$ROCM_ROOT" /usr -name 'hip-lang-config.cmake' 2>/dev/null | head -1 | xargs dirname 2>/dev/null); \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				echo "Error: unable to resolve ROCm root from hipblas CMake location."; \
				exit 1; \
			fi; \
			HIP_INCLUDE_DIR="$$ROCM_ROOT/include"; \
			if [ -d "$$HIP_INCLUDE_DIR/hipblas" ] && [ ! -e /usr/include/hipblas ]; then \
				ln -s "$$HIP_INCLUDE_DIR/hipblas" /usr/include/hipblas; \
			fi; \
			HIP_CMAKE_PREFIX=$$(dirname "$$HIPBLAS_DIR" 2>/dev/null || true); \
			HIPRAND_CMAKE_PREFIX=$$(dirname "$$HIPRAND_DIR" 2>/dev/null || true); \
			HIPSPARSE_CMAKE_PREFIX=$$(dirname "$$HIPSPARSE_DIR" 2>/dev/null || true); \
			if [ -z "$$HIP_LANG_DIR" ]; then \
				echo "Warning: hip-lang-config.cmake was not found during preflight; relying on CMake package discovery paths."; \
			fi; \
			if [ -z "$$HIP_DEVLIBS" ] || [ -z "$$HIP_CLANG" ]; then \
				echo "Error: unable to resolve ROCm LLVM device libs or clang compiler for HIP build."; \
				exit 1; \
			fi; \
			cd "$(AGENT_BNB_ROCM_BUILD_DIR)" && \
				PATH="$$HIP_LLVM_BINDIR:$$PATH" CPATH="$$HIP_INCLUDE_DIR:$$CPATH" CPLUS_INCLUDE_PATH="$$HIP_INCLUDE_DIR:$$CPLUS_INCLUDE_PATH" ROCM_PATH="$$ROCM_ROOT" ROCM_HOME="$$ROCM_ROOT" HIP_PATH="$$ROCM_ROOT" \
				cmake -DCOMPUTE_BACKEND=hip \
					-DCMAKE_PREFIX_PATH="$$HIP_CMAKE_PREFIX;$$HIPRAND_CMAKE_PREFIX;$$HIPSPARSE_CMAKE_PREFIX;$$ROCM_ROOT/lib/cmake;$$ROCM_ROOT;/opt/rocm;/opt/rocm/lib/cmake;/usr/lib/x86_64-linux-gnu/cmake;/usr/lib/cmake" \
					-DCMAKE_INCLUDE_PATH="$$HIP_INCLUDE_DIR" \
					-Dhipblas_DIR="$$HIPBLAS_DIR" \
					-Dhiprand_DIR="$$HIPRAND_DIR" \
					-Dhipsparse_DIR="$$HIPSPARSE_DIR" \
					-DCMAKE_HIP_COMPILER_ROCM_ROOT="$$ROCM_ROOT" \
					-DCMAKE_HIP_COMPILER=$$HIP_CLANG \
					-DCMAKE_CXX_COMPILER=$$HIP_CLANG \
					-DAMDGPU_TARGETS="gfx900;gfx906;gfx908;gfx90a;gfx1030;gfx1100;gfx1101;gfx1102;gfx1103" \
					"-DCMAKE_HIP_FLAGS=--rocm-path=$$ROCM_ROOT --rocm-device-lib-path=$$HIP_DEVLIBS -I$$HIP_INCLUDE_DIR" \
					"-DCMAKE_CXX_FLAGS=-D__HIP_PLATFORM_AMD__ -I$$HIP_INCLUDE_DIR" \
					"-DCMAKE_HIP_ARCHITECTURES=gfx1100" \
					-DHIP_PATH="$$ROCM_ROOT" \
					-DROCM_PATH="$$ROCM_ROOT" \
					-DCMAKE_EXE_LINKER_FLAGS="-Wl,--allow-shlib-undefined" \
					-S . -B build && \
				cmake --build build -j"$(AGENT_COMPILE_JOBS_VALUE)"; \
			if ! find "$(AGENT_BNB_ROCM_BUILD_DIR)/build" "$(AGENT_BNB_ROCM_BUILD_DIR)/bitsandbytes" -type f -name 'libbitsandbytes_rocm*.so' 2>/dev/null | grep -q .; then \
				echo "Error: ROCm bitsandbytes library (libbitsandbytes_rocm*.so) was not produced."; \
				echo "Aborting to avoid falling back to CPU-only bitsandbytes."; \
				exit 1; \
			fi; \
			$(AGENT_VENV_DIR)/bin/python -m pip uninstall -y bitsandbytes >/dev/null 2>&1 || true; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install --no-deps $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) "$(AGENT_BNB_ROCM_BUILD_DIR)" $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! ls "$(AGENT_VENV_DIR)/lib/python3.12/site-packages/bitsandbytes/libbitsandbytes_rocm"*.so >/dev/null 2>&1; then \
				echo "Error: Installed bitsandbytes package is still missing ROCm shared library in site-packages."; \
				exit 1; \
			fi; \
			touch "$(AGENT_VENV_DIR)/.bnb_rocm_ready"; \
		fi; \
	fi
	@echo "Python package installer: $(AGENT_PIP_CMD)"
	@echo "Installer progress flags: $(AGENT_PIP_INSTALL_PROGRESS_FLAGS)"
	@echo "Compile jobs for build fallback: $(AGENT_COMPILE_JOBS_VALUE)"
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(AGENT_VENV_DIR)/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
			echo "ROCm torch bootstrap already healthy."; \
		else \
			echo "Bootstrapping ROCm torch wheel (7.2) before LoRA dependency install..."; \
			$(AGENT_PIP_CMD) uninstall -y torch torchvision torchaudio >/dev/null 2>&1 || true; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch $(AGENT_PIP_BREAK_SYSTEM)); \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --index-url https://download.pytorch.org/whl/rocm7.2 --extra-index-url https://pypi.org/simple -r $(REPO_ROOT)/build/agent/requirements-lora.txt $(AGENT_PIP_BREAK_SYSTEM)); \
	else \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) -r $(REPO_ROOT)/build/agent/requirements-lora.txt $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@# Vision-language LoRA path: keep torchvision/pillow installed (from
	@# requirements-lora.txt above) so models with lora_overrides.keep_vision=true
	@# (e.g. qwen35-9b) can load via AutoModelForMultimodalLM/AutoProcessor with
	@# the vision tower intact, matching Qwen's own official usage example.
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(AGENT_VENV_DIR)/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
			echo "ROCm 7.2 text-training stack healthy ($$($(AGENT_VENV_DIR)/bin/python -c 'import torch; print(torch.__version__, torch.version.hip)')), skipping reinstall."; \
		else \
			echo "Repairing ROCm 7.2 text-training stack for LoRA training..."; \
			$(AGENT_PIP_CMD) uninstall -y torch >/dev/null 2>&1 || true; \
			echo "Installing fresh ROCm torch wheel (7.2) ..."; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! $(AGENT_VENV_DIR)/bin/python -c "import importlib; importlib.import_module('torch._dynamo')" 2>/dev/null; then \
				echo "Torch repair failed: missing torch/_dynamo after reinstall."; \
				exit 1; \
			fi; \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && HF_HOME="$(AGENT_HF_CACHE_DIR)" TORCH_HOME="$(AGENT_TORCH_CACHE_DIR)" TRITON_CACHE_DIR="$(AGENT_TRITON_CACHE_DIR)" LORA_DISABLE_FLA="$(LORA_DISABLE_FLA)" $(AGENT_VENV_DIR)/bin/python build.finetune.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_HF_BASE_MODEL)),--base_model "$(AGENT_HF_BASE_MODEL)",) --corpus "$(MODEL_DIR)/training/$(AGENT_PROFILE)-corpus.jsonl" --output_dir "$(LORA_OUTPUT_DIR)" $(if $(filter 1,$(LORA_ALLOW_CPU)),--allow_cpu,) $(if $(strip $(LORA_MAX_STEPS)),--max_steps "$(LORA_MAX_STEPS)",) $(if $(strip $(LORA_MAX_TRAIN_SAMPLES)),--max_train_samples "$(LORA_MAX_TRAIN_SAMPLES)",)

.PHONY: sft-corpus
sft-corpus:
	@echo "Preparing SFT reasoning-distillation corpus (Opus-4.6 distillation datasets) for profile $(AGENT_PROFILE)..."
	@if [ ! -x "$(AGENT_VENV_DIR)/bin/python" ]; then \
		echo "Creating LoRA venv..."; \
		python3 -m venv $(AGENT_VENV_DIR); \
	fi
	@mkdir -p $(AGENT_HF_CACHE_DIR)
	@mkdir -p "$(MODEL_DIR)/training"
	@cd $(REPO_ROOT)/build/agent && HF_HOME="$(AGENT_HF_CACHE_DIR)" $(AGENT_VENV_DIR)/bin/python build.sft_corpus.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --cache_dir "$(AGENT_HF_CACHE_DIR)/datasets" --output "$(SFT_CORPUS)"

# Mirrors lora-train-run's venv/dependency bootstrap (same shared venv, same requirements-lora.txt,
# same ROCm bitsandbytes source-build gate) but runs build.sft_train.py against the Opus-harnessing
# SFT corpus instead of build.finetune.py's plain-corpus continued-pretraining path.
.PHONY: sft-train-run
sft-train-run: sft-corpus
	@echo "SFT-training LoRA adapter (reasoning distillation) for profile $(AGENT_PROFILE) using model config $(AGENT_SFT_MODEL_CONFIG)..."
	@if [ "$(LORA_RECREATE_VENV)" = "1" ]; then \
		echo "LORA_RECREATE_VENV=1 set; recreating LoRA venv..."; \
		if [ -d "$(AGENT_VENV_DIR)" ]; then \
			rm -rf "$(AGENT_VENV_DIR)" || \
			mv "$(AGENT_VENV_DIR)" "$(AGENT_VENV_DIR)_stale.$$"; \
		fi; \
	fi
	@if [ ! -x "$(AGENT_VENV_DIR)/bin/python" ]; then \
		echo "Creating LoRA venv..."; \
		python3 -m venv $(AGENT_VENV_DIR); \
	else \
		echo "Reusing existing LoRA venv."; \
	fi
	@mkdir -p $(AGENT_PIP_CACHE_DIR)
	@mkdir -p $(AGENT_HF_CACHE_DIR)
	@mkdir -p $(AGENT_TORCH_CACHE_DIR)
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_BNB_ROCM_ENSURE)" = "1" ] && { [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; }; then \
		if [ -f "$(AGENT_VENV_DIR)/.bnb_rocm_ready" ]; then \
			echo "ROCm bitsandbytes bootstrap already completed for this venv."; \
		else \
			echo "Ensuring ROCm-capable bitsandbytes (source build) for quantized loading..."; \
			if ! command -v hipcc >/dev/null 2>&1; then \
				echo "Error: hipcc not found in container; cannot build ROCm bitsandbytes backend."; \
				echo "Install ROCm development toolchain in build/docker/Dockerfile (hipcc + ROCm CMake config), then rerun."; \
				exit 1; \
			fi; \
			export HIP_PATH=$(AGENT_HIP_PATH); \
			rm -rf "$(AGENT_BNB_ROCM_BUILD_DIR)"; \
			git clone --depth 1 --branch rocm_enabled https://github.com/ROCm/bitsandbytes.git "$(AGENT_BNB_ROCM_BUILD_DIR)"; \
			HIP_DEVLIBS=$$(find /opt/rocm*/lib/llvm/lib/clang/*/lib/amdgcn/bitcode -name 'hip.bc' 2>/dev/null | head -1 | xargs dirname 2>/dev/null || echo ""); \
			if [ -z "$$HIP_DEVLIBS" ]; then \
				HIP_DEVLIBS=$$(find /usr/lib/llvm-* -name 'hip.bc' 2>/dev/null | head -1 | xargs dirname 2>/dev/null); \
			fi; \
			HIP_LLVM_VER=$$(echo "$$HIP_DEVLIBS" | grep -oP 'clang/\K[0-9]+' | head -1 || echo "22"); \
			HIP_CLANG=$$(find /opt/rocm*/lib/llvm/bin -name 'clang++' 2>/dev/null | head -1 || command -v "clang++-$$HIP_LLVM_VER" 2>/dev/null || command -v clang++-17 2>/dev/null || ls /usr/bin/clang++-[0-9]* 2>/dev/null | sort -V | head -1); \
			HIP_LLVM_BINDIR=$$(dirname "$$HIP_CLANG" 2>/dev/null || true); \
			ROCM_ROOT=$$(readlink -f /opt/rocm 2>/dev/null || true); \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				ROCM_ROOT=$$(find /opt -maxdepth 1 -type d -name 'rocm-*' 2>/dev/null | sort -V | tail -1); \
			fi; \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				ROCM_ROOT=/usr; \
			fi; \
			HIPBLAS_CFG=$$(find /usr /opt/rocm /opt/rocm-* \( -name 'hipblasConfig.cmake' -o -name 'hipblas-config.cmake' \) 2>/dev/null | head -1); \
			HIPBLAS_DIR=$$(dirname "$$HIPBLAS_CFG" 2>/dev/null || true); \
			if [ -n "$$HIPBLAS_CFG" ]; then \
				ROCM_ROOT=$$(dirname $$(dirname $$(dirname "$$HIPBLAS_DIR" 2>/dev/null) 2>/dev/null) 2>/dev/null); \
			fi; \
			if [ -z "$$HIPBLAS_CFG" ]; then \
				HIPBLAS_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhipblas.so' 2>/dev/null | head -1); \
				if [ -n "$$HIPBLAS_LIB" ]; then \
					HIPBLAS_DIR=/tmp/hipblas-cmake; \
					mkdir -p "$$HIPBLAS_DIR"; \
					printf '%s\n' \
						'set(hipblas_FOUND TRUE)' \
						'if(NOT TARGET roc::hipblas)' \
						'  add_library(roc::hipblas SHARED IMPORTED)' \
						"  set_target_properties(roc::hipblas PROPERTIES IMPORTED_LOCATION \"$$HIPBLAS_LIB\")" \
						'endif()' \
						'if(NOT TARGET hipblas::hipblas)' \
						'  add_library(hipblas::hipblas INTERFACE IMPORTED)' \
						'  target_link_libraries(hipblas::hipblas INTERFACE roc::hipblas)' \
						'endif()' \
						> "$$HIPBLAS_DIR/hipblas-config.cmake"; \
					printf '%s\n' \
						'set(PACKAGE_VERSION "0")' \
						'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
						'set(PACKAGE_VERSION_EXACT TRUE)' \
						> "$$HIPBLAS_DIR/hipblas-config-version.cmake"; \
				else \
					echo "Error: hipblasConfig.cmake and libhipblas.so were not found in this image."; \
					exit 1; \
				fi; \
			fi; \
			HIPRAND_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhiprand.so' 2>/dev/null | head -1); \
			if [ -n "$$HIPRAND_LIB" ]; then \
				HIPRAND_DIR=/tmp/hiprand-cmake; \
				mkdir -p "$$HIPRAND_DIR"; \
				printf '%s\n' \
					'set(hiprand_FOUND TRUE)' \
					'if(NOT TARGET hip::hiprand)' \
					'  add_library(hip::hiprand SHARED IMPORTED)' \
					"  set_target_properties(hip::hiprand PROPERTIES IMPORTED_LOCATION \"$$HIPRAND_LIB\")" \
					'endif()' \
					'if(NOT TARGET hiprand::hiprand)' \
					'  add_library(hiprand::hiprand INTERFACE IMPORTED)' \
					'  target_link_libraries(hiprand::hiprand INTERFACE hip::hiprand)' \
					'endif()' \
					> "$$HIPRAND_DIR/hiprand-config.cmake"; \
				printf '%s\n' \
					'set(PACKAGE_VERSION "0")' \
					'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
					'set(PACKAGE_VERSION_EXACT TRUE)' \
					> "$$HIPRAND_DIR/hiprand-config-version.cmake"; \
			else \
				echo "Error: hiprand config and libhiprand.so were not found in this image."; \
				exit 1; \
			fi; \
				HIPSPARSE_CFG=$$(find /usr /opt/rocm /opt/rocm-* \( -name 'hipsparseConfig.cmake' -o -name 'hipsparse-config.cmake' \) 2>/dev/null | head -1); \
				HIPSPARSE_DIR=$$(dirname "$$HIPSPARSE_CFG" 2>/dev/null || true); \
				if [ -z "$$HIPSPARSE_CFG" ]; then \
					HIPSPARSE_LIB=$$(find "$$ROCM_ROOT" /usr /opt/rocm /opt/rocm-* -name 'libhipsparse.so' 2>/dev/null | head -1); \
					if [ -n "$$HIPSPARSE_LIB" ]; then \
						HIPSPARSE_DIR=/tmp/hipsparse-cmake; \
						mkdir -p "$$HIPSPARSE_DIR"; \
						printf '%s\n' \
							'set(hipsparse_FOUND TRUE)' \
							'if(NOT TARGET roc::hipsparse)' \
							'  add_library(roc::hipsparse SHARED IMPORTED)' \
							"  set_target_properties(roc::hipsparse PROPERTIES IMPORTED_LOCATION \"$$HIPSPARSE_LIB\")" \
							'endif()' \
							'if(NOT TARGET hipsparse::hipsparse)' \
							'  add_library(hipsparse::hipsparse INTERFACE IMPORTED)' \
							'  target_link_libraries(hipsparse::hipsparse INTERFACE roc::hipsparse)' \
							'endif()' \
							> "$$HIPSPARSE_DIR/hipsparse-config.cmake"; \
						printf '%s\n' \
							'set(PACKAGE_VERSION "0")' \
							'set(PACKAGE_VERSION_COMPATIBLE TRUE)' \
							'set(PACKAGE_VERSION_EXACT TRUE)' \
							> "$$HIPSPARSE_DIR/hipsparse-config-version.cmake"; \
					else \
						echo "Error: hipsparse config and libhipsparse.so were not found in this image."; \
						exit 1; \
					fi; \
				fi; \
			HIP_LANG_DIR=$$(find "$$ROCM_ROOT" /usr -name 'hip-lang-config.cmake' 2>/dev/null | head -1 | xargs dirname 2>/dev/null); \
			if [ -z "$$ROCM_ROOT" ] || [ ! -d "$$ROCM_ROOT" ]; then \
				echo "Error: unable to resolve ROCm root from hipblas CMake location."; \
				exit 1; \
			fi; \
			HIP_INCLUDE_DIR="$$ROCM_ROOT/include"; \
			if [ -d "$$HIP_INCLUDE_DIR/hipblas" ] && [ ! -e /usr/include/hipblas ]; then \
				ln -s "$$HIP_INCLUDE_DIR/hipblas" /usr/include/hipblas; \
			fi; \
			HIP_CMAKE_PREFIX=$$(dirname "$$HIPBLAS_DIR" 2>/dev/null || true); \
			HIPRAND_CMAKE_PREFIX=$$(dirname "$$HIPRAND_DIR" 2>/dev/null || true); \
			HIPSPARSE_CMAKE_PREFIX=$$(dirname "$$HIPSPARSE_DIR" 2>/dev/null || true); \
			if [ -z "$$HIP_LANG_DIR" ]; then \
				echo "Warning: hip-lang-config.cmake was not found during preflight; relying on CMake package discovery paths."; \
			fi; \
			if [ -z "$$HIP_DEVLIBS" ] || [ -z "$$HIP_CLANG" ]; then \
				echo "Error: unable to resolve ROCm LLVM device libs or clang compiler for HIP build."; \
				exit 1; \
			fi; \
			cd "$(AGENT_BNB_ROCM_BUILD_DIR)" && \
				PATH="$$HIP_LLVM_BINDIR:$$PATH" CPATH="$$HIP_INCLUDE_DIR:$$CPATH" CPLUS_INCLUDE_PATH="$$HIP_INCLUDE_DIR:$$CPLUS_INCLUDE_PATH" ROCM_PATH="$$ROCM_ROOT" ROCM_HOME="$$ROCM_ROOT" HIP_PATH="$$ROCM_ROOT" \
				cmake -DCOMPUTE_BACKEND=hip \
					-DCMAKE_PREFIX_PATH="$$HIP_CMAKE_PREFIX;$$HIPRAND_CMAKE_PREFIX;$$HIPSPARSE_CMAKE_PREFIX;$$ROCM_ROOT/lib/cmake;$$ROCM_ROOT;/opt/rocm;/opt/rocm/lib/cmake;/usr/lib/x86_64-linux-gnu/cmake;/usr/lib/cmake" \
					-DCMAKE_INCLUDE_PATH="$$HIP_INCLUDE_DIR" \
					-Dhipblas_DIR="$$HIPBLAS_DIR" \
					-Dhiprand_DIR="$$HIPRAND_DIR" \
					-Dhipsparse_DIR="$$HIPSPARSE_DIR" \
					-DCMAKE_HIP_COMPILER_ROCM_ROOT="$$ROCM_ROOT" \
					-DCMAKE_HIP_COMPILER=$$HIP_CLANG \
					-DCMAKE_CXX_COMPILER=$$HIP_CLANG \
					-DAMDGPU_TARGETS="gfx900;gfx906;gfx908;gfx90a;gfx1030;gfx1100;gfx1101;gfx1102;gfx1103" \
					"-DCMAKE_HIP_FLAGS=--rocm-path=$$ROCM_ROOT --rocm-device-lib-path=$$HIP_DEVLIBS -I$$HIP_INCLUDE_DIR" \
					"-DCMAKE_CXX_FLAGS=-D__HIP_PLATFORM_AMD__ -I$$HIP_INCLUDE_DIR" \
					"-DCMAKE_HIP_ARCHITECTURES=gfx1100" \
					-DHIP_PATH="$$ROCM_ROOT" \
					-DROCM_PATH="$$ROCM_ROOT" \
					-DCMAKE_EXE_LINKER_FLAGS="-Wl,--allow-shlib-undefined" \
					-S . -B build && \
				cmake --build build -j"$(AGENT_COMPILE_JOBS_VALUE)"; \
			if ! find "$(AGENT_BNB_ROCM_BUILD_DIR)/build" "$(AGENT_BNB_ROCM_BUILD_DIR)/bitsandbytes" -type f -name 'libbitsandbytes_rocm*.so' 2>/dev/null | grep -q .; then \
				echo "Error: ROCm bitsandbytes library (libbitsandbytes_rocm*.so) was not produced."; \
				echo "Aborting to avoid falling back to CPU-only bitsandbytes."; \
				exit 1; \
			fi; \
			$(AGENT_VENV_DIR)/bin/python -m pip uninstall -y bitsandbytes >/dev/null 2>&1 || true; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install --no-deps $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) "$(AGENT_BNB_ROCM_BUILD_DIR)" $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! ls "$(AGENT_VENV_DIR)/lib/python3.12/site-packages/bitsandbytes/libbitsandbytes_rocm"*.so >/dev/null 2>&1; then \
				echo "Error: Installed bitsandbytes package is still missing ROCm shared library in site-packages."; \
				exit 1; \
			fi; \
			touch "$(AGENT_VENV_DIR)/.bnb_rocm_ready"; \
		fi; \
	fi
	@echo "Python package installer: $(AGENT_PIP_CMD)"
	@echo "Installer progress flags: $(AGENT_PIP_INSTALL_PROGRESS_FLAGS)"
	@echo "Compile jobs for build fallback: $(AGENT_COMPILE_JOBS_VALUE)"
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(AGENT_VENV_DIR)/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
			echo "ROCm torch bootstrap already healthy."; \
		else \
			echo "Bootstrapping ROCm torch wheel (7.2) before LoRA dependency install..."; \
			$(AGENT_PIP_CMD) uninstall -y torch torchvision torchaudio >/dev/null 2>&1 || true; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch $(AGENT_PIP_BREAK_SYSTEM)); \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --index-url https://download.pytorch.org/whl/rocm7.2 --extra-index-url https://pypi.org/simple -r $(REPO_ROOT)/build/agent/requirements-lora.txt $(AGENT_PIP_BREAK_SYSTEM)); \
	else \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) -r $(REPO_ROOT)/build/agent/requirements-lora.txt $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@# Text-only LoRA path: prevent optional vision/audio backends from breaking imports.
	@$(AGENT_PIP_CMD) uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(AGENT_VENV_DIR)/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
			echo "ROCm 7.2 text-training stack healthy ($$($(AGENT_VENV_DIR)/bin/python -c 'import torch; print(torch.__version__, torch.version.hip)')), skipping reinstall."; \
		else \
			echo "Repairing ROCm 7.2 text-training stack for LoRA training..."; \
			$(AGENT_PIP_CMD) uninstall -y torchvision torchaudio >/dev/null 2>&1 || true; \
			$(AGENT_PIP_CMD) uninstall -y torch >/dev/null 2>&1 || true; \
			echo "Installing fresh ROCm torch wheel (7.2) ..."; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! $(AGENT_VENV_DIR)/bin/python -c "import importlib; importlib.import_module('torch._dynamo')" 2>/dev/null; then \
				echo "Torch repair failed: missing torch/_dynamo after reinstall."; \
				exit 1; \
			fi; \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && HF_HOME="$(AGENT_HF_CACHE_DIR)" TORCH_HOME="$(AGENT_TORCH_CACHE_DIR)" $(AGENT_VENV_DIR)/bin/python build.sft_train.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_SFT_MODEL_CONFIG)" $(if $(strip $(AGENT_HF_BASE_MODEL)),--base_model "$(AGENT_HF_BASE_MODEL)",) --corpus "$(SFT_CORPUS)" --output_dir "$(SFT_OUTPUT_DIR)" $(if $(filter 1,$(LORA_ALLOW_CPU)),--allow_cpu,)

.PHONY: sft-modelfile
sft-modelfile:
	@echo "Generating SFT LoRA Modelfile for profile $(AGENT_PROFILE) using model config $(AGENT_SFT_MODEL_CONFIG)..."
	@python3 -m venv $(AGENT_VENV_DIR)
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_SFT_MODEL_CONFIG)" $(if $(strip $(AGENT_BASE_MODEL)),--base_model "$(AGENT_BASE_MODEL)",) --adapter_path "$(SFT_OUTPUT_DIR)" --output "$(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)-sft"

.PHONY: lora-modelfile
lora-modelfile:
	@echo "Generating LoRA Modelfile for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@python3 -m venv $(AGENT_VENV_DIR)
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_BASE_MODEL)),--base_model "$(AGENT_BASE_MODEL)",) --adapter_path "$(LORA_OUTPUT_DIR)" --output "$(LORA_MODELFILE)"

.PHONY: lora-export-gguf
lora-export-gguf:
	@echo "Exporting LoRA profile $(AGENT_PROFILE) to merged GGUF..."
	@echo "GGUF quantization outtype: $(LORA_GGUF_OUTTYPE)"
	@if [ ! -d "$(LORA_OUTPUT_DIR)" ]; then \
		echo "Error: LoRA adapter directory missing at $(LORA_OUTPUT_DIR)"; exit 1; \
	fi
	@python3 -m venv $(AGENT_VENV_DIR)
	@if ! $(AGENT_VENV_DIR)/bin/python -c "import transformers, peft, torch, sentencepiece, google.protobuf" >/dev/null 2>&1; then \
		echo "Installing GGUF export dependencies..."; \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) transformers peft accelerate sentencepiece protobuf gguf $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@mkdir -p "$(LORA_CACHE_DIR)"
	@cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.lora_export_gguf.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_HF_BASE_MODEL)),--base_model "$(AGENT_HF_BASE_MODEL)",) --adapter_dir "$(LORA_OUTPUT_DIR)" --merged_dir "$(LORA_MERGED_DIR)" --output_gguf "$(LORA_GGUF)" --outtype "$(LORA_GGUF_OUTTYPE)" --llama_cpp_dir "$(LLAMA_CPP_DIR)" --cache_dir "$(LORA_CACHE_DIR)"

.PHONY: ollama-install-agentic
ollama-install-agentic: profile-modelfile
	@echo "Installing agentic profile $(AGENT_PROFILE) into Ollama as $(OLLAMA_AGENTIC_MODEL_NAME)..."
	@echo "Preferred Ollama host: $(OLLAMA_HOST)"
	@if [ ! -f $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE) ]; then \
		echo "Error: profile Modelfile missing at $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"; exit 1; \
	fi
	@ACTIVE_OLLAMA_HOST="$(OLLAMA_HOST)"; \
	if [ "$(OLLAMA_USE_LOCAL_DAEMON)" = "1" ]; then \
		echo "Starting local Ollama daemon in container (forced)..."; \
		OLLAMA_HOST="127.0.0.1:11434" ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		OLLAMA_HOST="127.0.0.1:11434" ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	fi; \
	echo "Using active Ollama host: $$ACTIVE_OLLAMA_HOST"; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_AGENTIC_MODEL_NAME) -f $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)
	@echo "Agentic profile model installation completed."

.PHONY: ollama-install-dual-model
ollama-install-dual-model:
	@echo "Installing dual-model setup (Opus 1.5 thinking + Qwen execution)..."
	@echo "Preferred Ollama host: $(OLLAMA_HOST)"
	@ACTIVE_OLLAMA_HOST="$(OLLAMA_HOST)"; \
	if [ "$(OLLAMA_USE_LOCAL_DAEMON)" = "1" ]; then \
		echo "Starting local Ollama daemon in container (forced)..."; \
		pkill -x ollama >/dev/null 2>&1 || true; \
		OLLAMA_HOST="127.0.0.1:11434" ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		OLLAMA_HOST="127.0.0.1:11434" ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	fi; \
	echo "Using active Ollama host: $$ACTIVE_OLLAMA_HOST"; \
	echo "Pulling Opus 1.5 (thinking model)..."; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama pull opus-research/opus-1.5; \
	echo "Pulling Qwen 2.5 Coder 14B (execution model)..."; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama pull qwen2.5-coder:14b; \
	echo "Dual-model setup installation completed."
	@echo "Thinking pipeline ready:"
	@echo "  - Thinking model: opus-research/opus-1.5"
	@echo "  - Execution model: qwen2.5-coder:14b"
	@echo "  - To use: AGENT_MODEL_CONFIG=qwen25-coder-14b-with-opus-thinking"

.PHONY: ollama-install-lora
ollama-install-lora: lora-export-gguf
	@echo "Installing LoRA profile $(AGENT_PROFILE) into Ollama as $(OLLAMA_LORA_MODEL_NAME) from GGUF..."
	@echo "Preferred Ollama host: $(OLLAMA_HOST)"
	@if [ ! -f $(LORA_GGUF) ]; then \
		echo "Error: merged GGUF not found at $(LORA_GGUF)"; exit 1; \
	fi
	@ACTIVE_OLLAMA_HOST="$(OLLAMA_HOST)"; \
	LOCAL_OLLAMA_HOST="http://127.0.0.1:11435"; \
	LOCAL_OLLAMA_BIND="127.0.0.1:11435"; \
	LOCAL_OLLAMA_LOG="$(MODEL_DIR)/ollama-lora-serve.log"; \
	if [ "$(OLLAMA_USE_LOCAL_DAEMON)" = "1" ]; then \
		echo "Starting local Ollama daemon in container (forced)..."; \
		pkill -x ollama >/dev/null 2>&1 || true; \
		( cd "$(MODEL_DIR)" && nohup env OLLAMA_HOST="$$LOCAL_OLLAMA_BIND" ollama serve > "$$LOCAL_OLLAMA_LOG" 2>&1 & ); \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="$$LOCAL_OLLAMA_HOST"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		pkill -x ollama >/dev/null 2>&1 || true; \
		( cd "$(MODEL_DIR)" && nohup env OLLAMA_HOST="$$LOCAL_OLLAMA_BIND" ollama serve > "$$LOCAL_OLLAMA_LOG" 2>&1 & ); \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="$$LOCAL_OLLAMA_HOST"; \
	fi; \
	if [ "$$ACTIVE_OLLAMA_HOST" = "$$LOCAL_OLLAMA_HOST" ] || [ "$$ACTIVE_OLLAMA_HOST" = "http://localhost:11435" ]; then \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			if OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
				break; \
			fi; \
			sleep 1; \
		done; \
		if ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
			echo "Error: local Ollama daemon did not become ready at $$ACTIVE_OLLAMA_HOST"; \
			exit 1; \
		fi; \
		echo "Local ollama daemon cwd: $$(pwdx $$(pgrep -n -x ollama) 2>/dev/null || echo unknown)"; \
	fi; \
	echo "Using active Ollama host: $$ACTIVE_OLLAMA_HOST"; \
	CREATE_RC=0; \
	cd $(REPO_ROOT)/build/agent && $(AGENT_VENV_DIR)/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" --base_model "$(abspath $(LORA_GGUF))" --output "$(LORA_GGUF_MODELFILE)"; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_LORA_MODEL_NAME) -f "$(LORA_GGUF_MODELFILE)"; \
	CREATE_RC=$$?; \
	if [ $$CREATE_RC -ne 0 ] && [ -f "$$LOCAL_OLLAMA_LOG" ]; then \
		echo "----- local ollama serve log (tail) -----"; \
		tail -n 120 "$$LOCAL_OLLAMA_LOG"; \
		echo "----- end local ollama serve log -----"; \
	fi; \
	test $$CREATE_RC -eq 0
	@echo "LoRA profile model installation completed."

# LM Studio only ever runs on the Windows host (never inside WSL2/Docker), so
# this target shells out to powershell.exe the same way agent_setup does for
# setup-llama-server.ps1. Detection is folder-existence based (see
# install-lmstudio-model.ps1): if LM Studio's models directory isn't found on
# the host -- or powershell.exe isn't reachable at all, e.g. when running via
# `docker.ps1 exec` -- this step is skipped without failing the build, so
# agent_build stays safe to run from inside the dev container.
.PHONY: lmstudio-install-lora
lmstudio-install-lora: lora-export-gguf
	@if [ ! -f $(LORA_GGUF) ]; then \
		echo "Error: merged GGUF not found at $(LORA_GGUF)"; exit 1; \
	fi
	@if ! command -v powershell.exe >/dev/null 2>&1; then \
		echo "Skipping LM Studio install: powershell.exe not reachable from this shell (expected when running via docker.ps1 exec)."; \
		echo "Run this target from a host PowerShell terminal instead to install into LM Studio if present:"; \
		echo "  PowerShell -ExecutionPolicy Bypass -File build/docker/install-lmstudio-model.ps1 -GgufPath \"$(abspath $(LORA_GGUF))\" -ModelName \"$(OLLAMA_LORA_MODEL_NAME)\""; \
		exit 0; \
	fi
	@powershell.exe -ExecutionPolicy Bypass -File "$(REPO_ROOT)/build/docker/install-lmstudio-model.ps1" -GgufPath "$(abspath $(LORA_GGUF))" -ModelName "$(OLLAMA_LORA_MODEL_NAME)"

.PHONY: agent_build
agent_build: install-agent-env profile-modelfile ollama-install-agentic lora-train lora-export-gguf ollama-install-lora lmstudio-install-lora
	@echo "\n=== Full build workflow completed for model config $(AGENT_MODEL_CONFIG) (profile $(AGENT_PROFILE)) ==="
	@echo "Agentic corpus metadata: $(MODEL_DIR)/training/$(AGENT_PROFILE)-metadata.json"

# Smoke-test variant of agent_build: runs the exact same full pipeline
# (agentic Ollama install, LoRA train, GGUF export, LoRA Ollama install) so it
# exercises every step end-to-end, but caps the LoRA training pass to a
# handful of steps/rows via LORA_LITE_MAX_STEPS / LORA_LITE_MAX_TRAIN_SAMPLES
# so it finishes quickly instead of committing to a full training run. Note:
# lora-export-gguf's cost scales with base model size, not training duration,
# so that step is not shrunk by this target.
.PHONY: agent_build_lite
agent_build_lite:
	@echo "=== Running agent_build in smoke-test (lite) mode: max_steps=$(LORA_LITE_MAX_STEPS), max_train_samples=$(LORA_LITE_MAX_TRAIN_SAMPLES) ==="
	@$(MAKE) -f agent/agent.mk agent_build \
		AGENT_PROFILE="$(AGENT_PROFILE)" AGENT_MODEL_CONFIG="$(AGENT_MODEL_CONFIG)" \
		LORA_MAX_STEPS="$(LORA_LITE_MAX_STEPS)" LORA_MAX_TRAIN_SAMPLES="$(LORA_LITE_MAX_TRAIN_SAMPLES)"

# llama.cpp's llama-server runs natively on the WINDOWS HOST (never inside
# WSL2/Docker) so it can bind the host GPU directly, same as Ollama already
# does. This recipe just wraps build/docker/setup-llama-server.ps1; it only
# works when invoked from a shell with real Windows interop (native
# PowerShell, or a WSL/Git-Bash shell with `powershell.exe` on PATH) -- it
# will NOT work from inside the dev container via `docker.ps1 exec`, since
# plain containers have no path back to the Windows host.
LLAMA_SERVER_SCRIPT := $(REPO_ROOT)/build/docker/setup-llama-server.ps1
LLAMA_SERVER_ARGS ?=

.PHONY: agent_setup
agent_setup:
	@if ! command -v powershell.exe >/dev/null 2>&1; then \
		echo "Error: powershell.exe not reachable from this shell."; \
		echo "agent_setup must run where the Windows host is reachable (native PowerShell, or WSL/Git-Bash with interop)."; \
		echo "Run the script directly instead, e.g. from a Windows PowerShell terminal:"; \
		echo "  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 prereqs"; \
		echo "  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 build"; \
		echo "  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 run"; \
		exit 1; \
	fi
	@echo "=== llama.cpp server setup (runs on the Windows host, not in the dev container) ==="
	@powershell.exe -ExecutionPolicy Bypass -File "$(LLAMA_SERVER_SCRIPT)" prereqs $(LLAMA_SERVER_ARGS)
	@powershell.exe -ExecutionPolicy Bypass -File "$(LLAMA_SERVER_SCRIPT)" build $(LLAMA_SERVER_ARGS)
	@powershell.exe -ExecutionPolicy Bypass -File "$(LLAMA_SERVER_SCRIPT)" run $(LLAMA_SERVER_ARGS)
	@echo "llama-server should now be serving at http://127.0.0.1:8090/v1/chat/completions"
	@echo "Check status any time with:"
	@echo "  PowerShell -ExecutionPolicy Bypass -File build/docker/setup-llama-server.ps1 status"
	@echo "LoRA adapter dir: $(LORA_OUTPUT_DIR)"
	@echo "Ollama agentic model: $(OLLAMA_AGENTIC_MODEL_NAME)"
	@echo "Ollama LoRA model: $(OLLAMA_LORA_MODEL_NAME)"
	@echo "Logs and outputs available in the terminal."

.PHONY: agentic_build
agentic_build: install-agent-env prepare-corpus profile-modelfile ollama-install-agentic
	@echo "\n=== Agentic build workflow completed for profile $(AGENT_PROFILE) ==="
	@echo "Corpus metadata: $(MODEL_DIR)/training/$(AGENT_PROFILE)-metadata.json"
	@echo "Profile Modelfile: $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"
	@echo "Ollama model name: $(OLLAMA_AGENTIC_MODEL_NAME)"

.PHONY: lora_build
lora_build: install-agent-env lora-train lora-modelfile ollama-install-lora lmstudio-install-lora
	@echo "\n=== LoRA build workflow completed for profile $(AGENT_PROFILE) ==="
	@echo "LoRA adapter dir: $(LORA_OUTPUT_DIR)"
	@echo "LoRA Modelfile: $(LORA_MODELFILE)"
	@echo "Ollama model name: $(OLLAMA_LORA_MODEL_NAME)"

agent_install: ollama-install-agentic

# hf.co/ManniX-ITA/gemma-4-A4B-98e-v6-coder-it-GGUF:Q6_K hf.co/ManniX-ITA/gemma-4-A4B-98e-v6-coder-it-GGUF:Q5_K_M
# ollama run hf.co/mradermacher/ERNIE-21B-A3B-Claude-4.5-High-OPUS-Thinking-i1-GGUF:Q5_K_M