# syntax=docker/dockerfile:1.7
# ============================================================
# lotr project -- development image
# Base: Ubuntu 24.04 LTS
#
# Includes:
#   - C/C++ build toolchain (gcc, clang, cmake, scons, ninja)
#   - Godot 4 build & export dependencies
#   - Git + GUI (gitk) + Python git tooling
#   - Python web-crawling + image-processing stack (Pillow)
#   - Common CI/scripting utilities
#
# Build:
#   docker build -t lotr-dev build/docker/
# Run:
#   docker run --rm -it -v "$(pwd):/workspace" lotr-dev
# ============================================================

FROM ubuntu:24.04

ARG GODOT_VERSION=4.4.1-stable
ARG GPU_VARIANT=rocm
# Set GODOT_EDITOR=1 at build time to include the Godot editor binary.
# The headless binary (godot) is always included for CI/export use.
#   docker build --build-arg GODOT_EDITOR=1 -t lotr-dev build/docker/
ARG GODOT_EDITOR=0

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HSA_OVERRIDE_GFX_VERSION=11.0.0 \
    HSA_ENABLE_DXG_DETECTION=1 \
    LD_LIBRARY_PATH=/opt/rocm/lib:/usr/lib/wsl/lib

# ------------------------------------------------------------
# System packages
# Install in a single layer to keep image size down.
# ------------------------------------------------------------
RUN --mount=type=cache,id=lotr-dev-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=lotr-dev-apt-lists,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Core build toolchain
    build-essential \
    gcc g++ \
    clang lld llvm \
    make cmake ninja-build \
    nasm yasm \
    pkg-config \
    # SCons -- Godot's primary build system
    scons \
    # Version control
    git gitk \
    # Archive / compression
    zip unzip p7zip-full \
    # Fetch / networking
    curl wget ca-certificates \
    apt-transport-https gnupg \
    # SSH client + agent (ssh, ssh-add, ssh-keygen) + PuTTY key converter
    openssh-client \
    putty-tools \
    # Terminal utilities
    less file tree jq \
    rsync \
    bash-completion \
    # Python 3
    python3 python3-pip python3-venv python3-dev \
    python3-tk \
    # Godot X11 / display dependencies
    libx11-dev libxcursor-dev libxrandr-dev \
    libxinerama-dev libxi-dev libxext-dev \
    libxrender-dev libxfixes-dev \
    # Virtual framebuffer + X auth (headless display for Godot editor / CI)
    xvfb x11-utils xauth dbus-x11 \
    # GTK4 runtime (required by Godot editor)
    libgtk-4-1 \
    # Godot OpenGL / GLES
    libgl-dev libgles2-mesa-dev \
    # Godot audio
    libasound2-dev libpulse-dev \
    # Godot system / D-Bus
    libudev-dev libdbus-1-dev \
    # Godot font / freetype
    libfontconfig1-dev libfreetype-dev \
    # Godot Wayland (Godot 4 supports Wayland natively)
    libwayland-dev wayland-protocols libwayland-bin \
    # Godot misc (PCRE2, zlib)
    libpcre2-dev zlib1g-dev libssl-dev \
    # Godot Vulkan headers (runtime provided by WSL/GPU driver)
    libvulkan-dev \
    # Godot speech (optional TTS)
    libspeechd-dev \
    # Java -- needed for Android export pipeline
    default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# ROCm userland is baked into the dev image for parity with lotr-ai.
# WSL still provides the kernel-side DXG device and /usr/lib/wsl/lib bridge libs.
RUN --mount=type=cache,id=lotr-dev-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=lotr-dev-apt-lists,target=/var/lib/apt/lists,sharing=locked \
    if [ "$GPU_VARIANT" = "rocm" ]; then \
        mkdir -p /etc/apt/keyrings && \
        for _url in \
            "https://repo.radeon.com/rocm/rocm.gpg.key" \
            "https://repo.amd.com/rocm/rocm.gpg.key" \
            "https://repo.radeon.com/amdgpu/rocm.gpg.key"; do \
          curl --retry 3 --retry-delay 5 -fsSL "$_url" \
              | gpg --dearmor -o /etc/apt/keyrings/rocm.gpg 2>/dev/null \
            && break || true; \
        done && \
        [ -s /etc/apt/keyrings/rocm.gpg ] || { echo "ERROR: failed to obtain ROCm GPG key"; exit 1; } && \
        printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/latest noble main\n' \
            > /etc/apt/sources.list.d/rocm.list && \
        apt-get update && \
        apt-get install -y --no-install-recommends hsa-rocr hip-runtime-amd rocminfo && \
        rm -rf /var/lib/apt/lists/* && \
        echo '/opt/rocm/lib' > /etc/ld.so.conf.d/rocm.conf && ldconfig; \
    else \
        echo '/opt/rocm/lib' > /etc/ld.so.conf.d/rocm.conf; \
    fi

# ------------------------------------------------------------
# Node.js 22 LTS (for admin panel / frontend dev)
# Uses NodeSource official repo to get a current LTS release.
# ------------------------------------------------------------
RUN --mount=type=cache,id=lotr-dev-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=lotr-dev-apt-lists,target=/var/lib/apt/lists,sharing=locked \
    set -eux; \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -; \
    apt-get install -y --no-install-recommends nodejs; \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Docker CE: install Docker's official packages (docker-ce, cli, buildx, compose)
# Prefer Docker CE (official) over the distro `docker.io` package for feature
# completeness (buildx, compose plugin). This adds Docker's apt repo and
# installs the required packages.
# ------------------------------------------------------------
RUN --mount=type=cache,id=lotr-dev-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=lotr-dev-apt-lists,target=/var/lib/apt/lists,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    chmod a+r /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Godot 4 headless export binary
# Pulls the official Linux headless build for CI/export use.
# The editor GUI is not included (headless only).
# Override GODOT_VERSION at build time to pin a different release.
# ------------------------------------------------------------
RUN set -eux; \
    GODOT_FILE="Godot_v${GODOT_VERSION}_linux.x86_64"; \
    curl -fsSL \
        "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${GODOT_FILE}.zip" \
        -o /tmp/godot.zip; \
    unzip /tmp/godot.zip -d /tmp/godot; \
    mv "/tmp/godot/${GODOT_FILE}" /usr/local/bin/godot; \
    chmod +x /usr/local/bin/godot; \
    rm -rf /tmp/godot.zip /tmp/godot

# ------------------------------------------------------------
# Godot 4 export templates (headless export requires these)
# ------------------------------------------------------------
RUN set -eux; \
    TEMPLATES_FILE="Godot_v${GODOT_VERSION}_export_templates.tpz"; \
    TEMPLATES_DIR="${HOME}/.local/share/godot/export_templates/${GODOT_VERSION}"; \
    curl -fsSL \
        "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${TEMPLATES_FILE}" \
        -o /tmp/templates.tpz; \
    mkdir -p "${TEMPLATES_DIR}"; \
    unzip /tmp/templates.tpz -d /tmp/templates; \
    mv /tmp/templates/templates/* "${TEMPLATES_DIR}/"; \
    rm -rf /tmp/templates.tpz /tmp/templates

# ------------------------------------------------------------
# Godot 4 editor binary (optional -- only when GODOT_EDITOR=1)
# Downloads the full editor build so developers can run the Godot editor
# inside the container via X11 forwarding or xvfb-run.
# ------------------------------------------------------------
RUN if [ "${GODOT_EDITOR}" = "1" ]; then \
    set -eux; \
    GODOT_FILE="Godot_v${GODOT_VERSION}_linux.x86_64"; \
    EDITOR_FILE="Godot_v${GODOT_VERSION}_linux.x86_64"; \
    curl -fsSL \
        "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${EDITOR_FILE}.zip" \
        -o /tmp/godot-editor.zip; \
    unzip /tmp/godot-editor.zip -d /tmp/godot-editor; \
    mv "/tmp/godot-editor/${GODOT_FILE}" /usr/local/bin/godot-editor; \
    chmod +x /usr/local/bin/godot-editor; \
    rm -rf /tmp/godot-editor.zip /tmp/godot-editor; \
fi

# ------------------------------------------------------------
# Python -- install packages
# --break-system-packages : required on Ubuntu 24.04 (PEP 668)
# --ignore-installed      : skip uninstalling Debian-managed packages
#                           that have no RECORD file (packaging, pyyaml,
#                           etc.); pip will install fresh copies into
#                           /usr/local/lib, which take precedence.
# Both flags are safe in a container where we own the whole environment.
# ------------------------------------------------------------

# Git tooling
RUN --mount=type=cache,id=lotr-dev-pip-cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed \
    gitpython \
    pre-commit \
    commitizen \
    pygit2

# Web crawling / HTTP
RUN --mount=type=cache,id=lotr-dev-pip-cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed \
    requests \
    httpx[http2] \
    aiohttp \
    beautifulsoup4 \
    lxml \
    cssselect \
    scrapy \
    playwright \
    selenium \
    webdriver-manager \
    tldextract \
    chardet
# Hugging Face hub for model downloads
RUN --mount=type=cache,id=lotr-dev-pip-cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed huggingface_hub

# Install Playwright browser binaries (Chromium + Firefox, headless)
RUN python3 -m playwright install --with-deps chromium firefox

# Data / scripting utilities
RUN --mount=type=cache,id=lotr-dev-pip-cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed \
    pyyaml \
    toml \
    tomli \
    python-dotenv \
    click \
    rich \
    tqdm \
    pathspec \
    tiktoken \
    Pillow \
    uvicorn

# Code quality
RUN --mount=type=cache,id=lotr-dev-pip-cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed \
    black \
    isort \
    flake8 \
    mypy

# AI helper dependencies (used by ai_update target)
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages --ignore-installed \
        numpy \
        faiss-cpu \
        langchain \
        langchain-community \
        ollama

# Install PyTorch variant by GPU build target.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ "$GPU_VARIANT" = "rocm" ]; then \
        python3 -m pip install --break-system-packages --ignore-installed \
            --index-url https://download.pytorch.org/whl/rocm7.2 \
            torch torchvision torchaudio; \
    else \
        python3 -m pip install --break-system-packages --ignore-installed \
            torch torchvision torchaudio; \
    fi

# Install zstd (required by the Ollama installer)
RUN apt-get update && apt-get install -y zstd

# Install Ollama binary for local LLM inference
RUN curl -fsSL https://ollama.com/install.sh | sh

# ------------------------------------------------------------
# Node.js (LTS) -- required for React admin panel (Vite + TypeScript)
# Uses NodeSource binary distribution for a current LTS release.
# ------------------------------------------------------------
RUN set -eux; \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -; \
    apt-get install -y --no-install-recommends nodejs; \
    rm -rf /var/lib/apt/lists/*; \
    npm install -g npm@latest vite

# Install the LOTR server package (required for godot_play target).
# Use a non-editable install so the package code is baked into site-packages,
# not a .pth pointer to a source path that won't exist at runtime.
COPY server/ /opt/server-src/
RUN python3 -m pip install --break-system-packages --ignore-installed /opt/server-src

# Copy VS Code extension source and build it inside the image (if present)
COPY .vscode /workspace/.vscode
RUN if [ -d /workspace/.vscode/extensions/ai ]; then \
    cd /workspace/.vscode/extensions/ai && npm install && npm run compile; \
fi

# ------------------------------------------------------------
# Shell -- enable bash-completion (including make target completion)
# Docker containers run bash as a non-login, non-interactive shell by
# default so /etc/bash_completion is not auto-sourced. Writing to
# /root/.bashrc ensures it loads whenever an interactive shell starts.
# ------------------------------------------------------------
RUN echo '' >> /root/.bashrc && \
    echo '# bash-completion' >> /root/.bashrc && \
    echo 'if [ -f /usr/share/bash-completion/bash_completion ]; then' >> /root/.bashrc && \
    echo '    . /usr/share/bash-completion/bash_completion' >> /root/.bashrc && \
    echo 'fi' >> /root/.bashrc && \
    echo '' >> /root/.bashrc && \
    echo '# project aliases' >> /root/.bashrc && \
    echo 'if [ -f /root/.bash_aliases ]; then' >> /root/.bashrc && \
    echo '    . /root/.bash_aliases' >> /root/.bashrc && \
    echo 'fi' >> /root/.bashrc

# Copy project aliases into the image
COPY build/docker/.bash_aliases /root/.bash_aliases
COPY build/docker/ssh-add.sh   /usr/local/bin/ssh-add.sh
COPY build/docker/run-godot.sh /usr/local/bin/run-godot.sh
RUN  chmod +x /usr/local/bin/ssh-add.sh /usr/local/bin/run-godot.sh
# ------------------------------------------------------------
# Working directory
# Mount the project root here when running the container:
#   docker run --rm -it -v "$(pwd):/workspace" lotr-dev
# ------------------------------------------------------------
WORKDIR /workspace

CMD ["/bin/bash", "-l"]

