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
# Set GODOT_EDITOR=1 at build time to include the Godot editor binary.
# The headless binary (godot) is always included for CI/export use.
#   docker build --build-arg GODOT_EDITOR=1 -t lotr-dev build/docker/
ARG GODOT_EDITOR=0

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ------------------------------------------------------------
# System packages
# Install in a single layer to keep image size down.
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
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
RUN python3 -m pip install --break-system-packages --ignore-installed \
    gitpython \
    pre-commit \
    commitizen \
    pygit2

# Web crawling / HTTP
RUN python3 -m pip install --break-system-packages --ignore-installed \
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

# Install Playwright browser binaries (Chromium + Firefox, headless)
RUN python3 -m playwright install --with-deps chromium firefox

# Data / scripting utilities
RUN python3 -m pip install --break-system-packages --ignore-installed \
    pyyaml \
    toml \
    tomli \
    python-dotenv \
    click \
    rich \
    tqdm \
    pathspec \
    Pillow

# Code quality
RUN python3 -m pip install --break-system-packages --ignore-installed \
    black \
    isort \
    flake8 \
    mypy

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

