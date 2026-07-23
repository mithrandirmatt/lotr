REPO_ROOT ?= $(CURDIR)/..
BASE_MODEL ?= llama3-8b
QUANTIZATION ?= 4bit
AGENT_PROFILE ?= rx7900xtx-agentic
AGENT_MODEL_CONFIG ?= qwen25-coder-7b
AGENT_CORPUS_MODEL ?= $(AGENT_MODEL_CONFIG)
AGENT_BASE_MODEL ?=
AGENT_HF_BASE_MODEL ?=
MODEL_DIR ?= $(REPO_ROOT)/do/agent/models
OUTPUT_MODEL := $(MODEL_DIR)/lotr-$(BASE_MODEL)-$(QUANTIZATION).gguf
OLLAMA_MODEL_NAME := lotr-$(BASE_MODEL)-$(QUANTIZATION)
OLLAMA_AGENTIC_MODEL_NAME := lotr-agentic-$(AGENT_PROFILE)
OLLAMA_LORA_MODEL_NAME := lotr-lora-$(AGENT_PROFILE)
OLLAMA_FALLBACK_BASE ?= llama3.1:8b
OLLAMA_HOST ?= http://host.docker.internal:11434
OLLAMA_USE_LOCAL_DAEMON ?= 0
LORA_ALLOW_CPU ?= 0
LORA_GGUF_OUTTYPE ?= q4_k_m
AGENT_TORCH_VARIANT ?= auto
LORA_RECREATE_VENV ?= 0
AGENT_CACHE_DIR ?= $(REPO_ROOT)/build/docker/cache
AGENT_PIP_CACHE_DIR ?= $(AGENT_CACHE_DIR)/pip
AGENT_HF_CACHE_DIR ?= $(AGENT_CACHE_DIR)/huggingface
AGENT_TORCH_CACHE_DIR ?= $(AGENT_CACHE_DIR)/torch
AGENT_PYTHON ?= $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python
AGENT_PIP_BINARY_FLAGS ?= --prefer-binary --only-binary=:all:
AGENT_COMPILE_JOBS ?= auto
AGENT_UV ?= $(shell command -v uv 2>/dev/null)
AGENT_PIP_CMD ?= $(if $(strip $(AGENT_UV)),uv pip --python $(AGENT_PYTHON),$(AGENT_PYTHON) -m pip)
AGENT_PIP_BREAK_SYSTEM ?= $(if $(strip $(AGENT_UV)),,--break-system-packages)
AGENT_PIP_INSTALL_PROGRESS_FLAGS ?= $(if $(strip $(AGENT_UV)),--verbose,--progress-bar on --verbose)
AGENT_INSTALL_HEARTBEAT_SECS ?= 20
AGENT_BNB_ROCM_ENSURE ?= 1
AGENT_BNB_ROCM_BUILD_DIR ?= /tmp/bnb-rocm-build
AGENT_HIP_PATH ?= $(firstword $(wildcard /opt/rocm /usr))
AGENT_COMPILE_JOBS_VALUE ?= $(if $(filter auto,$(AGENT_COMPILE_JOBS)),$(shell nproc 2>/dev/null || echo 4),$(AGENT_COMPILE_JOBS))
AGENT_PIP_BUILD_ENV ?= MAX_JOBS=$(AGENT_COMPILE_JOBS_VALUE) CMAKE_BUILD_PARALLEL_LEVEL=$(AGENT_COMPILE_JOBS_VALUE)
LORA_OUTPUT_DIR := $(MODEL_DIR)/lora/$(AGENT_PROFILE)
LORA_MODELFILE := $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE).lora
LORA_MERGED_DIR := $(MODEL_DIR)/lora-merged/$(AGENT_PROFILE)
LORA_GGUF_TAG := $(shell printf '%s' "$(LORA_GGUF_OUTTYPE)" | tr '[:upper:]' '[:lower:]')
LORA_GGUF := $(MODEL_DIR)/lotr-lora-$(AGENT_PROFILE)-$(LORA_GGUF_TAG).gguf
LORA_CACHE_DIR := $(MODEL_DIR)/cache/$(AGENT_PROFILE)
LORA_TRAIN_FP := $(LORA_CACHE_DIR)/lora-train.sha256
LORA_TRAIN_FP_NEW := $(LORA_CACHE_DIR)/lora-train.sha256.new
LORA_TRAIN_DONE := $(LORA_CACHE_DIR)/lora-train.done
LLAMA_CPP_DIR ?= $(AGENT_CACHE_DIR)/llama.cpp

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
	@echo "Cleaning agent caches for a fresh build..."
	@rm -rf $(AGENT_PIP_CACHE_DIR)
	@rm -rf $(AGENT_HF_CACHE_DIR)
	@rm -rf $(AGENT_TORCH_CACHE_DIR)
	@if [ -d "$(REPO_ROOT)/build/agent/lotr_agent/venv" ]; then \
		rm -rf "$(REPO_ROOT)/build/agent/lotr_agent/venv" || \
		mv "$(REPO_ROOT)/build/agent/lotr_agent/venv" "$(REPO_ROOT)/build/agent/lotr_agent/venv_stale.$$"; \
	fi
	@rm -rf $(REPO_ROOT)/build/agent/lotr_agent/venv_stale*
	@echo "Agent cache cleanup complete."

.PHONY: validate-model
validate-model:
	@echo "Validating model configuration for $(BASE_MODEL) with $(QUANTIZATION) quantization..."
	@echo "Model output will be saved to: $(OUTPUT_MODEL)"

.PHONY: prepare-corpus
prepare-corpus:
	@echo "Preparing corpus/training artifacts for profile $(AGENT_PROFILE)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.train.py --model "$(AGENT_CORPUS_MODEL)" --quantization "$(QUANTIZATION)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" --data_dir "$(REPO_ROOT)"

.PHONY: train-$(BASE_MODEL)
train-$(BASE_MODEL): prepare-corpus
	@echo "Training $(BASE_MODEL) model with $(QUANTIZATION) quantization..."
	@echo "Training corpus prepared and placeholder model generated."

.PHONY: quantize-$(QUANTIZATION)
quantize-$(QUANTIZATION):
	@echo "Quantizing model with $(QUANTIZATION) quantization..."
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.quantize.py --quantization "$(QUANTIZATION)"

.PHONY: optimize-inference
optimize-inference:
	@echo "Optimizing inference for $(QUANTIZATION) quantization..."
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.optimize.py --quantization "$(QUANTIZATION)"

.PHONY: lotr-$(BASE_MODEL)-$(QUANTIZATION)
lotr-$(BASE_MODEL)-$(QUANTIZATION): train-$(BASE_MODEL) quantize-$(QUANTIZATION) optimize-inference
	@echo "Model training, quantization, and optimization completed successfully."
	@echo "Final model saved to: $(OUTPUT_MODEL)"

.PHONY: install-$(BASE_MODEL)
install-$(BASE_MODEL):
	@echo "Installing $(BASE_MODEL) model with $(QUANTIZATION) quantization..."
	@echo "Setting Python path to include build directory"
	# Ensure the virtual environment exists in the agent directory
	@mkdir -p $(REPO_ROOT)/build/agent/lotr_agent/venv
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	# Install once; skip when the package is already available in this venv
	@if $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import importlib.metadata as m; m.version('lotr_agent')" >/dev/null 2>&1; then \
		echo "lotr_agent already installed in venv, skipping reinstall."; \
	else \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) -e $(REPO_ROOT)/build/agent/lotr_agent $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@echo "Installation completed"

.PHONY: profile-modelfile
profile-modelfile:
	@echo "Generating Modelfile for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_BASE_MODEL)),--base_model "$(AGENT_BASE_MODEL)",) --output "$(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"

.PHONY: lora-train lora-train-run lora-fingerprint
lora-fingerprint: prepare-corpus
	@mkdir -p "$(LORA_CACHE_DIR)"
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.lora_fingerprint.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" --corpus "$(MODEL_DIR)/training/$(AGENT_PROFILE)-corpus.jsonl" --hf_base_model "$(AGENT_HF_BASE_MODEL)" --allow_cpu "$(LORA_ALLOW_CPU)" --torch_variant "$(AGENT_TORCH_VARIANT)" --output "$(LORA_TRAIN_FP_NEW)"

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
		$(MAKE) -f agent/agent.mk lora-train-run AGENT_PROFILE="$(AGENT_PROFILE)" AGENT_MODEL_CONFIG="$(AGENT_MODEL_CONFIG)" AGENT_HF_BASE_MODEL="$(AGENT_HF_BASE_MODEL)" LORA_ALLOW_CPU="$(LORA_ALLOW_CPU)" AGENT_TORCH_VARIANT="$(AGENT_TORCH_VARIANT)"; \
		mv -f "$(LORA_TRAIN_FP_NEW)" "$(LORA_TRAIN_FP)"; \
		touch "$(LORA_TRAIN_DONE)"; \
	fi

lora-train-run: prepare-corpus
	@echo "Training LoRA adapter for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@if [ "$(LORA_RECREATE_VENV)" = "1" ]; then \
		echo "LORA_RECREATE_VENV=1 set; recreating LoRA venv..."; \
		if [ -d "$(REPO_ROOT)/build/agent/lotr_agent/venv" ]; then \
			rm -rf "$(REPO_ROOT)/build/agent/lotr_agent/venv" || \
			mv "$(REPO_ROOT)/build/agent/lotr_agent/venv" "$(REPO_ROOT)/build/agent/lotr_agent/venv_stale.$$"; \
		fi; \
	fi
	@if [ ! -x "$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python" ]; then \
		echo "Creating LoRA venv..."; \
		python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv; \
	else \
		echo "Reusing existing LoRA venv."; \
	fi
	@mkdir -p $(AGENT_PIP_CACHE_DIR)
	@mkdir -p $(AGENT_HF_CACHE_DIR)
	@mkdir -p $(AGENT_TORCH_CACHE_DIR)
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_BNB_ROCM_ENSURE)" = "1" ] && { [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; }; then \
		if [ -f "$(REPO_ROOT)/build/agent/lotr_agent/venv/.bnb_rocm_ready" ]; then \
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
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip uninstall -y bitsandbytes >/dev/null 2>&1 || true; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) "$(AGENT_BNB_ROCM_BUILD_DIR)" $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! ls "$(REPO_ROOT)/build/agent/lotr_agent/venv/lib/python3.12/site-packages/bitsandbytes/libbitsandbytes_rocm"*.so >/dev/null 2>&1; then \
				echo "Error: Installed bitsandbytes package is still missing ROCm shared library in site-packages."; \
				exit 1; \
			fi; \
			touch "$(REPO_ROOT)/build/agent/lotr_agent/venv/.bnb_rocm_ready"; \
		fi; \
	fi
	@echo "Python package installer: $(AGENT_PIP_CMD)"
	@echo "Installer progress flags: $(AGENT_PIP_INSTALL_PROGRESS_FLAGS)"
	@echo "Compile jobs for build fallback: $(AGENT_COMPILE_JOBS_VALUE)"
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
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
		if $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import importlib; import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2'); importlib.import_module('torch._dynamo')" 2>/dev/null; then \
			echo "ROCm 7.2 text-training stack healthy ($$($(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c 'import torch; print(torch.__version__, torch.version.hip)')), skipping reinstall."; \
		else \
			echo "Repairing ROCm 7.2 text-training stack for LoRA training..."; \
			$(AGENT_PIP_CMD) uninstall -y torchvision torchaudio >/dev/null 2>&1 || true; \
			$(AGENT_PIP_CMD) uninstall -y torch >/dev/null 2>&1 || true; \
			echo "Installing fresh ROCm torch wheel (7.2) ..."; \
			$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_BUILD_ENV) $(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) $(AGENT_PIP_BINARY_FLAGS) --cache-dir $(AGENT_PIP_CACHE_DIR) --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch $(AGENT_PIP_BREAK_SYSTEM)); \
			if ! $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import importlib; importlib.import_module('torch._dynamo')" 2>/dev/null; then \
				echo "Torch repair failed: missing torch/_dynamo after reinstall."; \
				exit 1; \
			fi; \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && HF_HOME="$(AGENT_HF_CACHE_DIR)" TORCH_HOME="$(AGENT_TORCH_CACHE_DIR)" $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.finetune.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_HF_BASE_MODEL)),--base_model "$(AGENT_HF_BASE_MODEL)",) --corpus "$(MODEL_DIR)/training/$(AGENT_PROFILE)-corpus.jsonl" --output_dir "$(LORA_OUTPUT_DIR)" $(if $(filter 1,$(LORA_ALLOW_CPU)),--allow_cpu,)

.PHONY: lora-modelfile
lora-modelfile:
	@echo "Generating LoRA Modelfile for profile $(AGENT_PROFILE) using model config $(AGENT_MODEL_CONFIG)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_BASE_MODEL)),--base_model "$(AGENT_BASE_MODEL)",) --adapter_path "$(LORA_OUTPUT_DIR)" --output "$(LORA_MODELFILE)"

.PHONY: lora-export-gguf
lora-export-gguf:
	@echo "Exporting LoRA profile $(AGENT_PROFILE) to merged GGUF..."
	@echo "GGUF quantization outtype: $(LORA_GGUF_OUTTYPE)"
	@if [ ! -d "$(LORA_OUTPUT_DIR)" ]; then \
		echo "Error: LoRA adapter directory missing at $(LORA_OUTPUT_DIR)"; exit 1; \
	fi
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@if ! $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import transformers, peft, torch, sentencepiece, google.protobuf" >/dev/null 2>&1; then \
		echo "Installing GGUF export dependencies..."; \
		$(call AGENT_RUN_WITH_HEARTBEAT,$(AGENT_PIP_CMD) install $(AGENT_PIP_INSTALL_PROGRESS_FLAGS) transformers peft accelerate sentencepiece protobuf gguf $(AGENT_PIP_BREAK_SYSTEM)); \
	fi
	@mkdir -p "$(LORA_CACHE_DIR)"
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.lora_export_gguf.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --model_config "$(AGENT_MODEL_CONFIG)" $(if $(strip $(AGENT_HF_BASE_MODEL)),--base_model "$(AGENT_HF_BASE_MODEL)",) --adapter_dir "$(LORA_OUTPUT_DIR)" --merged_dir "$(LORA_MERGED_DIR)" --output_gguf "$(LORA_GGUF)" --outtype "$(LORA_GGUF_OUTTYPE)" --llama_cpp_dir "$(LLAMA_CPP_DIR)" --cache_dir "$(LORA_CACHE_DIR)"

.PHONY: ollama-install-$(BASE_MODEL)
ollama-install-$(BASE_MODEL):
	@echo "Installing $(OLLAMA_MODEL_NAME) into Ollama..."
	@echo "Preferred Ollama host: $(OLLAMA_HOST)"
	@if [ ! -f $(OUTPUT_MODEL) ]; then \
		 echo "Error: model file $(OUTPUT_MODEL) not found. Build the model first."; exit 1; \
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
	echo "FROM $(abspath $(OUTPUT_MODEL))" > Modelfile; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_MODEL_NAME) -f Modelfile || { \
		echo "Warning: GGUF import failed (likely placeholder/incompatible GGUF)."; \
		echo "Falling back to Ollama base model: $(OLLAMA_FALLBACK_BASE)"; \
		echo "FROM $(OLLAMA_FALLBACK_BASE)" > Modelfile; \
		OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_MODEL_NAME) -f Modelfile; \
	}; \
	rm Modelfile
	@echo "Ollama model installation completed."

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
	TMP_GGUF_MODELFILE="$(MODEL_DIR)/Modelfile.$(AGENT_PROFILE).lora.gguf.$$$$"; \
	echo "FROM $(abspath $(LORA_GGUF))" > "$$TMP_GGUF_MODELFILE"; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_LORA_MODEL_NAME) -f "$$TMP_GGUF_MODELFILE"; \
	CREATE_RC=$$?; \
	rm -f "$$TMP_GGUF_MODELFILE"; \
	if [ $$CREATE_RC -ne 0 ] && [ -f "$$LOCAL_OLLAMA_LOG" ]; then \
		echo "----- local ollama serve log (tail) -----"; \
		tail -n 120 "$$LOCAL_OLLAMA_LOG"; \
		echo "----- end local ollama serve log -----"; \
	fi; \
	test $$CREATE_RC -eq 0
	@echo "LoRA profile model installation completed."

.PHONY: agent_build
agent_build: install-$(BASE_MODEL) lotr-$(BASE_MODEL)-$(QUANTIZATION) ollama-install-$(BASE_MODEL) profile-modelfile ollama-install-agentic lora-train lora-export-gguf ollama-install-lora
	@echo "\n=== Full build workflow completed for $(BASE_MODEL) with $(QUANTIZATION) quantization ==="
	@echo "Base model artifact: $(OUTPUT_MODEL)"
	@echo "Agentic corpus metadata: $(MODEL_DIR)/training/$(AGENT_PROFILE)-metadata.json"
	@echo "LoRA adapter dir: $(LORA_OUTPUT_DIR)"
	@echo "Ollama base model: $(OLLAMA_MODEL_NAME)"
	@echo "Ollama agentic model: $(OLLAMA_AGENTIC_MODEL_NAME)"
	@echo "Ollama LoRA model: $(OLLAMA_LORA_MODEL_NAME)"
	@echo "Logs and outputs available in the terminal."

.PHONY: agentic_build
agentic_build: install-$(BASE_MODEL) train-$(BASE_MODEL) profile-modelfile ollama-install-agentic
	@echo "\n=== Agentic build workflow completed for profile $(AGENT_PROFILE) ==="
	@echo "Corpus metadata: $(MODEL_DIR)/training/$(AGENT_PROFILE)-metadata.json"
	@echo "Profile Modelfile: $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"
	@echo "Ollama model name: $(OLLAMA_AGENTIC_MODEL_NAME)"

.PHONY: lora_build
lora_build: install-$(BASE_MODEL) lora-train lora-modelfile ollama-install-lora
	@echo "\n=== LoRA build workflow completed for profile $(AGENT_PROFILE) ==="
	@echo "LoRA adapter dir: $(LORA_OUTPUT_DIR)"
	@echo "LoRA Modelfile: $(LORA_MODELFILE)"
	@echo "Ollama model name: $(OLLAMA_LORA_MODEL_NAME)"

agent_install: ollama-install-$(BASE_MODEL)

# hf.co/ManniX-ITA/gemma-4-A4B-98e-v6-coder-it-GGUF:Q6_K hf.co/ManniX-ITA/gemma-4-A4B-98e-v6-coder-it-GGUF:Q5_K_M
# ollama run hf.co/mradermacher/ERNIE-21B-A3B-Claude-4.5-High-OPUS-Thinking-i1-GGUF:Q5_K_M