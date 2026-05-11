#!/usr/bin/env bash
# install_rocdxg.sh
#
# Builds and installs librocdxg (AMD ROCDXG) inside the lotr-docker-service WSL2
# distro, enabling ROCm GPU access via /dev/dxg (Windows DXCore).
#
# Run as root inside the WSL2 distro. Called automatically by setup-wsl-docker.ps1
# when an AMD GPU and /dev/dxg are detected.
#
# Environment variables (all optional):
#   WIN_SDK   -- path to the versioned Windows SDK Include directory
#                e.g. /mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.26100.0
#                Auto-detected from /mnt/c/Program Files (x86)/Windows Kits if not set.
#
# Exit codes:
#   0  success (or already installed -- idempotent)
#   1  /dev/dxg not found; AMD GPU inaccessible or Windows driver too old
#   2  Windows SDK not found; install the Windows 10/11 SDK and retry
#   3  build or install failed; check /var/log/install_rocdxg.log

set -euo pipefail

MARKER=/var/local/rocdxg.installed
LOG=/var/log/install_rocdxg.log

mkdir -p /var/local /var/log

log() { echo "[$(date -Is)] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------
if [ -f "$MARKER" ]; then
    log "librocdxg already installed (marker $MARKER). Skipping."
    exit 0
fi

log "=== ROCDXG installer started ==="

# ---------------------------------------------------------------------------
# Pre-flight: /dev/dxg
# ---------------------------------------------------------------------------
if [ ! -c /dev/dxg ]; then
    log "ERROR: /dev/dxg not found."
    log "  Ensure a recent AMD Adrenalin driver is installed on Windows (26.2.2+)."
    log "  WSL2 exposes /dev/dxg only when the host GPU driver supports DXCore."
    exit 1
fi
log "/dev/dxg present -- proceeding."

export DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# Build dependencies
# ---------------------------------------------------------------------------
log "Installing build dependencies..."
apt-get update -qq 2>&1 | tee -a "$LOG"
apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config python3 \
    libnuma-dev libpciaccess-dev ca-certificates curl gnupg zstd \
    2>&1 | tee -a "$LOG"

# ---------------------------------------------------------------------------
# ROCm userland (rocminfo + runtime, best-effort, non-fatal)
# librocdxg build itself only needs cmake/gcc; rocminfo is for post-install
# verification only. If ROCm packages cannot be installed the build continues.
# ---------------------------------------------------------------------------
install_rocm_packages() {
    # Disable errexit inside this function -- failures are non-fatal
    set +e

    local codename
    codename=$(lsb_release -cs 2>/dev/null)
    local arch
    arch=$(dpkg --print-architecture 2>/dev/null || echo amd64)
    local keyring=/etc/apt/keyrings/rocm.gpg
    local sources=/etc/apt/sources.list.d/rocm.list

    mkdir -p /etc/apt/keyrings
    curl -fsSL https://repo.radeon.com/rocm/rocm.gpg.key \
        | gpg --dearmor -o "$keyring" 2>>"$LOG"
    if [ $? -ne 0 ]; then
        log "WARNING: Failed to download ROCm GPG key -- skipping ROCm packages."
        set -e; return 0
    fi

    # Try native codename first; fall back to jammy (ROCm lags behind Ubuntu releases)
    local repo_ok=0
    for suite in "$codename" jammy; do
        echo "deb [arch=${arch} signed-by=${keyring}] \
https://repo.radeon.com/rocm/apt/latest/ ${suite} main" > "$sources"
        if apt-get update -qq 2>&1 | tee -a "$LOG"; then
            repo_ok=1
            log "ROCm APT repo accepted suite: ${suite}"
            break
        else
            log "ROCm APT suite '${suite}' unavailable -- trying next..."
            rm -f "$sources"
        fi
    done

    if [ $repo_ok -eq 0 ]; then
        log "WARNING: ROCm APT repo not available for this distro -- skipping ROCm packages."
        set -e; return 0
    fi

    log "Installing ROCm userland packages..."
    if apt-get install -y --no-install-recommends \
            rocminfo hip-runtime-amd rocm-libs \
            2>&1 | tee -a "$LOG"; then
        log "ROCm userland packages installed."
    else
        log "WARNING: Full ROCm install failed; attempting rocminfo only..."
        apt-get install -y --no-install-recommends rocminfo 2>&1 | tee -a "$LOG" || \
            log "WARNING: rocminfo also unavailable -- continuing without ROCm verification tool."
    fi

    set -e
}

if command -v rocminfo >/dev/null 2>&1; then
    log "rocminfo already installed -- skipping ROCm APT step."
else
    log "Adding ROCm APT repository (best-effort)..."
    install_rocm_packages
fi

# ---------------------------------------------------------------------------
# Detect Windows SDK path
# ---------------------------------------------------------------------------
if [ -z "${WIN_SDK:-}" ]; then
    SDK_BASE="/mnt/c/Program Files (x86)/Windows Kits/10/Include"
    if [ -d "$SDK_BASE" ]; then
        # Find the highest versioned directory that contains a 'shared' subdir
        WIN_SDK=$(
            find "$SDK_BASE" -maxdepth 2 -type d -name shared 2>/dev/null \
            | sed 's|/shared$||' \
            | sort -V \
            | tail -n1
        )
    fi
fi

if [ -z "${WIN_SDK:-}" ]; then
    log "ERROR: Windows SDK not found."
    log "  Install the Windows 10/11 SDK from:"
    log "    https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/"
    log "  Then re-run with:"
    log "    WIN_SDK='/mnt/c/Program Files (x86)/Windows Kits/10/Include/<version>' bash install_rocdxg.sh"
    exit 2
fi
log "Using Windows SDK: $WIN_SDK"

# ---------------------------------------------------------------------------
# Clone and build librocdxg
# ---------------------------------------------------------------------------
BUILD_DIR=/tmp/librocdxg
if [ -d "$BUILD_DIR" ]; then
    log "Removing previous build directory..."
    rm -rf "$BUILD_DIR"
fi

log "Cloning librocdxg from https://github.com/ROCm/librocdxg.git ..."
git clone --depth 1 https://github.com/ROCm/librocdxg.git "$BUILD_DIR" \
    2>&1 | tee -a "$LOG"

log "Running cmake (WIN_SDK/shared = ${WIN_SDK}/shared) ..."
mkdir -p "${BUILD_DIR}/build"
cd "${BUILD_DIR}/build"

cmake .. -DWIN_SDK="${WIN_SDK}/shared" 2>&1 | tee -a "$LOG" \
    || { log "ERROR: cmake configuration failed."; exit 3; }

NPROC=$(nproc 2>/dev/null || echo 4)
log "Building with ${NPROC} parallel jobs..."
make -j"$NPROC" 2>&1 | tee -a "$LOG" \
    || { log "ERROR: make failed."; exit 3; }

log "Installing librocdxg..."
make install 2>&1 | tee -a "$LOG" \
    || { log "ERROR: make install failed."; exit 3; }

cd /
ldconfig
log "ldconfig updated."

# ---------------------------------------------------------------------------
# Profile snippet: enable DXG detection on login
# ---------------------------------------------------------------------------
cat > /etc/profile.d/rocdxg.sh <<'EOF'
# AMD ROCDXG: enable GPU access via /dev/dxg (WSL2 DXCore path)
export HSA_ENABLE_DXG_DETECTION=1
# RDNA3 (RX 7900 XTX) GFX version override for ROCm compatibility
export HSA_OVERRIDE_GFX_VERSION=11.0.0
EOF
chmod 644 /etc/profile.d/rocdxg.sh
log "Wrote /etc/profile.d/rocdxg.sh"

# ---------------------------------------------------------------------------
# Idempotency marker
# ---------------------------------------------------------------------------
echo "$(date -Is)" > "$MARKER"

log "=== ROCDXG installation complete ==="
log ""
log "Verify inside WSL:"
log "  source /etc/profile.d/rocdxg.sh && rocminfo | head -n 50"
log ""
log "Expected output: Agent listing for gfx1100 / Radeon RX 7900 XTX"
log ""
log "To use ROCDXG in a container, add these flags to 'docker run':"
log "  --device /dev/dxg"
log "  -v /usr/lib/wsl/lib/libdxcore.so:/usr/lib/libdxcore.so"
log "  -v /opt/rocm/lib/librocdxg.so:/usr/lib/librocdxg.so"
log "  -e HSA_ENABLE_DXG_DETECTION=1"
