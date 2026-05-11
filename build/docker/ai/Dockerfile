# ============================================================
# LotR TCG AI Server (was MCP)
# Bundles the AI/MCP server and Ollama daemon.
#
# Build variants (from repo root):
#   docker build -t lotr-ai:cpu   build/docker/ai/
#   docker build -t lotr-ai:rocm  --build-arg GPU_VARIANT=rocm build/docker/ai/
#   docker build -t lotr-ai:cuda  --build-arg GPU_VARIANT=cuda build/docker/ai/
# Run standalone (CPU):
#   docker run --rm -p 11434:11434 -p 3100:3100 -v "$(pwd):/workspace" lotr-ai:cpu
# Run with ROCm (AMD 7900 XTX):
#   docker run --rm -p 11434:11434 -p 3100:3100 \
#     --device /dev/kfd --device /dev/dri \
#     --group-add video --group-add render \
#     -v "$(pwd):/workspace" lotr-ai:rocm
# ============================================================

FROM python:3.12-slim

# GPU_VARIANT selects the runtime: cpu (default) | rocm | cuda
ARG GPU_VARIANT=cpu

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg2 \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# ROCm userland (AMD GPUs — host provides kernel driver, container provides libraries)
# Supports RDNA3 / gfx1100 (RX 7900 XTX). Skipped for cpu/cuda variants.
RUN if [ "$GPU_VARIANT" = "rocm" ]; then \
      mkdir -p /etc/apt/keyrings && \
      curl -fsSL https://repo.radeon.com/rocm/rocm.gpg.key \
          | gpg --dearmor -o /etc/apt/keyrings/rocm.gpg && \
      printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/latest noble main\n' \
          > /etc/apt/sources.list.d/rocm.list && \
      apt-get update && \
      apt-get install -y --no-install-recommends \
          hip-runtime-amd \
          rocblas \
          rocm-libs && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# Install Ollama binary (official install script — includes ROCm/CUDA detection at runtime)
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY start_services.sh /usr/local/bin/start_services.sh
COPY gpu_detect.sh /usr/local/bin/gpu_detect.sh
COPY install_gpu_runtime.sh /usr/local/bin/install_gpu_runtime.sh
COPY supervisord.conf /etc/supervisor/supervisord.conf
RUN chmod +x /usr/local/bin/start_services.sh /usr/local/bin/gpu_detect.sh /usr/local/bin/install_gpu_runtime.sh

# Bake GPU_VARIANT into the image so start_services.sh and Ollama can inspect it
ARG GPU_VARIANT=cpu

# OLLAMA_HOST must be 0.0.0.0:11434 so Ollama binds on all interfaces
# HSA_OVERRIDE_GFX_VERSION=11.0.0 tells ROCm the 7900 XTX is gfx1100 (RDNA3)
ENV WORKSPACE=/workspace \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=3100 \
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_URL=http://localhost:11434 \
    OLLAMA_HOST_CACHE=/ollama-cache \
    GPU_VARIANT=${GPU_VARIANT} \
    HSA_OVERRIDE_GFX_VERSION=11.0.0

EXPOSE 3100 11434

ENTRYPOINT ["/usr/local/bin/start_services.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -sf http://localhost:11434/ && curl -sf http://localhost:3100/sse || exit 1
