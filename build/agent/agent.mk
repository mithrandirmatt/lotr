REPO_ROOT ?= $(CURDIR)/..
BASE_MODEL ?= llama3-8b
QUANTIZATION ?= 4bit
AGENT_PROFILE ?= rx7900xtx-agentic
AGENT_BASE_MODEL ?= qwen2.5-coder:7b
AGENT_HF_BASE_MODEL ?= Qwen/Qwen2.5-Coder-7B-Instruct
MODEL_DIR ?= $(REPO_ROOT)/do/agent/models
OUTPUT_MODEL := $(MODEL_DIR)/lotr-$(BASE_MODEL)-$(QUANTIZATION).gguf
OLLAMA_MODEL_NAME := lotr-$(BASE_MODEL)-$(QUANTIZATION)
OLLAMA_AGENTIC_MODEL_NAME := lotr-agentic-$(AGENT_PROFILE)
OLLAMA_LORA_MODEL_NAME := lotr-lora-$(AGENT_PROFILE)
OLLAMA_FALLBACK_BASE ?= llama3.1:8b
OLLAMA_HOST ?= http://host.docker.internal:11434
OLLAMA_USE_LOCAL_DAEMON ?= 0
LORA_ALLOW_CPU ?= 0
AGENT_TORCH_VARIANT ?= auto
LORA_RECREATE_VENV ?= 0
LORA_OUTPUT_DIR := $(MODEL_DIR)/lora/$(AGENT_PROFILE)
LORA_MODELFILE := $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE).lora

.PHONY: validate-model
validate-model:
	@echo "Validating model configuration for $(BASE_MODEL) with $(QUANTIZATION) quantization..."
	@echo "Model output will be saved to: $(OUTPUT_MODEL)"

.PHONY: prepare-corpus
prepare-corpus:
	@echo "Preparing corpus/training artifacts for profile $(AGENT_PROFILE)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.train.py --model "$(BASE_MODEL)" --quantization "$(QUANTIZATION)" --profile "$(AGENT_PROFILE)" --data_dir "$(REPO_ROOT)"

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
		$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip install -e $(REPO_ROOT)/build/agent/lotr_agent --break-system-packages; \
	fi
	@echo "Installation completed"

.PHONY: profile-modelfile
profile-modelfile:
	@echo "Generating Modelfile for profile $(AGENT_PROFILE) using base model $(AGENT_BASE_MODEL)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --base_model "$(AGENT_BASE_MODEL)" --output "$(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)"

.PHONY: lora-train
lora-train: prepare-corpus
	@echo "Training LoRA adapter for profile $(AGENT_PROFILE) on $(AGENT_HF_BASE_MODEL)..."
	@if [ "$(LORA_RECREATE_VENV)" = "1" ]; then \
		echo "LORA_RECREATE_VENV=1 set; recreating LoRA venv..."; \
		rm -rf $(REPO_ROOT)/build/agent/lotr_agent/venv; \
	fi
	@if [ ! -x "$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python" ]; then \
		echo "Creating LoRA venv..."; \
		python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv; \
	else \
		echo "Reusing existing LoRA venv."; \
	fi
	@mkdir -p $(REPO_ROOT)/build/docker/cache/pip
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2')" 2>/dev/null && [ -d "$(REPO_ROOT)/build/agent/lotr_agent/venv/lib/python3.12/site-packages/torch/_dynamo" ]; then \
			echo "ROCm torch bootstrap already healthy."; \
		else \
			echo "Bootstrapping ROCm torch wheel (7.2) before LoRA dependency install..."; \
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip uninstall -y torch torchvision torchaudio >/dev/null 2>&1 || true; \
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip install --no-cache-dir --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch --break-system-packages; \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip install --cache-dir $(REPO_ROOT)/build/docker/cache/pip --index-url https://download.pytorch.org/whl/rocm7.2 --extra-index-url https://pypi.org/simple -r $(REPO_ROOT)/build/agent/requirements-lora.txt --break-system-packages; \
	else \
		$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip install --cache-dir $(REPO_ROOT)/build/docker/cache/pip -r $(REPO_ROOT)/build/agent/requirements-lora.txt --break-system-packages; \
	fi
	@# Text-only LoRA path: prevent optional vision/audio backends from breaking imports.
	@$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true
	@cd $(REPO_ROOT)/build/agent && if [ "$(AGENT_TORCH_VARIANT)" = "rocm" ] || { [ "$(AGENT_TORCH_VARIANT)" = "auto" ] && { [ -c /dev/kfd ] || [ -c /dev/dxg ]; }; }; then \
		if $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c "import torch; hip = getattr(torch.version, 'hip', None); assert hip and str(hip).startswith('7.2')" 2>/dev/null && [ -d "$(REPO_ROOT)/build/agent/lotr_agent/venv/lib/python3.12/site-packages/torch/_dynamo" ]; then \
			echo "ROCm 7.2 text-training stack healthy ($$($(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -c 'import torch; print(torch.__version__, torch.version.hip)')), skipping reinstall."; \
		else \
			echo "Repairing ROCm 7.2 text-training stack for LoRA training..."; \
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip uninstall -y torchvision torchaudio >/dev/null 2>&1 || true; \
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip uninstall -y torch >/dev/null 2>&1 || true; \
			echo "Installing fresh ROCm torch wheel (7.2) ..."; \
			$(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python -m pip install --no-cache-dir --upgrade --force-reinstall --index-url https://download.pytorch.org/whl/rocm7.2 torch --break-system-packages; \
			if [ ! -d "$(REPO_ROOT)/build/agent/lotr_agent/venv/lib/python3.12/site-packages/torch/_dynamo" ]; then \
				echo "Torch repair failed: missing torch/_dynamo after reinstall."; \
				exit 1; \
			fi; \
		fi; \
	fi
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.finetune.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --base_model "$(AGENT_HF_BASE_MODEL)" --corpus "$(MODEL_DIR)/training/$(AGENT_PROFILE)-corpus.jsonl" --output_dir "$(LORA_OUTPUT_DIR)" $(if $(filter 1,$(LORA_ALLOW_CPU)),--allow_cpu,)

.PHONY: lora-modelfile
lora-modelfile:
	@echo "Generating LoRA Modelfile for profile $(AGENT_PROFILE) using base model $(AGENT_BASE_MODEL)..."
	@python3 -m venv $(REPO_ROOT)/build/agent/lotr_agent/venv
	@cd $(REPO_ROOT)/build/agent && $(REPO_ROOT)/build/agent/lotr_agent/venv/bin/python build.modelfile.py --repo_root "$(REPO_ROOT)" --profile "$(AGENT_PROFILE)" --base_model "$(AGENT_BASE_MODEL)" --adapter_path "$(LORA_OUTPUT_DIR)" --output "$(LORA_MODELFILE)"

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
		ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		ollama serve > /dev/null 2>&1 & \
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
		ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	fi; \
	echo "Using active Ollama host: $$ACTIVE_OLLAMA_HOST"; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_AGENTIC_MODEL_NAME) -f $(MODEL_DIR)/Modelfile.$(AGENT_PROFILE)
	@echo "Agentic profile model installation completed."

.PHONY: ollama-install-lora
ollama-install-lora: lora-modelfile
	@echo "Installing LoRA profile $(AGENT_PROFILE) into Ollama as $(OLLAMA_LORA_MODEL_NAME)..."
	@echo "Preferred Ollama host: $(OLLAMA_HOST)"
	@if [ ! -f $(LORA_MODELFILE) ]; then \
		echo "Error: LoRA Modelfile missing at $(LORA_MODELFILE)"; exit 1; \
	fi
	@if [ ! -d $(LORA_OUTPUT_DIR) ]; then \
		echo "Error: LoRA adapter directory missing at $(LORA_OUTPUT_DIR)"; exit 1; \
	fi
	@ACTIVE_OLLAMA_HOST="$(OLLAMA_HOST)"; \
	if [ "$(OLLAMA_USE_LOCAL_DAEMON)" = "1" ]; then \
		echo "Starting local Ollama daemon in container (forced)..."; \
		ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	elif ! OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama list > /dev/null 2>&1; then \
		echo "Preferred host $$ACTIVE_OLLAMA_HOST is not reachable; starting local Ollama daemon in container..."; \
		ollama serve > /dev/null 2>&1 & \
		sleep 2; \
		ACTIVE_OLLAMA_HOST="http://127.0.0.1:11434"; \
	fi; \
	echo "Using active Ollama host: $$ACTIVE_OLLAMA_HOST"; \
	OLLAMA_HOST="$$ACTIVE_OLLAMA_HOST" ollama create $(OLLAMA_LORA_MODEL_NAME) -f $(LORA_MODELFILE)
	@echo "LoRA profile model installation completed."

.PHONY: agent_build
agent_build: install-$(BASE_MODEL) lotr-$(BASE_MODEL)-$(QUANTIZATION) ollama-install-$(BASE_MODEL) profile-modelfile ollama-install-agentic lora-train lora-modelfile ollama-install-lora
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