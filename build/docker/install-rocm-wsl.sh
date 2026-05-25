#!/usr/bin/env bash
set -euo pipefail

ROCM_KEY_URLS=(
  "https://repo.amd.com/rocm/packages/gpg/rocm.gpg.key"
  "https://repo.amd.com/rocm/packages/gpg/rocm.gpg"
  "https://repo.amd.com/rocm/rocm.gpg.key"
  "https://repo.amd.com/rocm/rocm.gpg"
  "https://repo.amd.com/rocm/packages/gpg/amdrocm.gpg"
  "https://repo.radeon.com/rocm/rocm.gpg.key"
)
ROCM_REPO_URL="https://repo.amd.com/rocm/packages/ubuntu2404"
AMDGPU_REPO_URL="https://repo.radeon.com/amdgpu/30.30/ubuntu"
ROCM_META_PKG="amdrocm7.12-gfx950"

export DEBIAN_FRONTEND=noninteractive

# initial update (best-effort)
apt-get update || true

# Try to capture missing key IDs and fetch them from multiple sources
update_out=$(apt-get update 2>&1 || true)
echo "$update_out"
missing_keys=$(echo "$update_out" | sed -n 's/.*NO_PUBKEY //p' | tr '\n' ' ')
if [ -n "$missing_keys" ]; then
    for k in $missing_keys; do
        echo "Attempting to fetch missing key $k via gpg keyserver"
        # try multiple keyservers with gpg
        gpg --no-default-keyring --keyring /tmp/attempt.keyring --keyserver hkps://keyserver.ubuntu.com --recv-keys "$k" || true
        # gpg --export outputs binary directly; write it without dearmoring
        gpg --no-default-keyring --keyring /tmp/attempt.keyring --export "$k" >/etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
        echo "Attempting apt-key adv for $k"
        apt-key adv --keyserver hkps://keyserver.ubuntu.com --recv-keys "$k" || true
    done
    apt-get update || true
fi

# Ensure tools installed
apt-get install -y --no-install-recommends gnupg wget ca-certificates lsb-release apt-transport-https software-properties-common build-essential cmake git || true

mkdir -p /etc/apt/keyrings

# Try multiple remote key URLs and heuristics
key_ok=false
for url in "${ROCM_KEY_URLS[@]}"; do
    echo "Fetching key from $url"
    wget -qO /tmp/rocm_key_temp "$url" || true
    if [ ! -s /tmp/rocm_key_temp ]; then continue; fi
    if grep -q "BEGIN PGP" /tmp/rocm_key_temp 2>/dev/null; then
        # ASCII armored - dearmor to binary
        gpg --dearmor /tmp/rocm_key_temp -o /etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
    else
        # Already binary GPG format - copy directly (gpg --dearmor only converts ASCII→binary)
        cp /tmp/rocm_key_temp /etc/apt/keyrings/amdrocm.gpg
    fi
    if [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
        echo "Wrote /etc/apt/keyrings/amdrocm.gpg from $url"
        key_ok=true
        break
    fi
done

# fallback: try amdgpu repo key
if [ "$key_ok" = false ]; then
    echo "Attempting to fetch AMDGPU key as fallback"
    if wget -qO- https://repo.radeon.com/amdgpu/rocm.gpg.key | gpg --dearmor -o /etc/apt/keyrings/amdrocm.gpg 2>/dev/null; then
        key_ok=true
    fi
fi

# fallback: export from legacy /etc/apt/trusted.gpg (apt-key may have deposited FA296B056C5BB456 there)
if [ "$key_ok" = false ] && [ -f /etc/apt/trusted.gpg ]; then
    gpg --no-default-keyring --keyring /etc/apt/trusted.gpg \
        --export FA296B056C5BB456 >/etc/apt/keyrings/amdrocm.gpg 2>/dev/null || true
    if [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
        echo "Exported FA296B056C5BB456 from legacy trusted.gpg"
        key_ok=true
    fi
fi

# write sources, prefer signed-by when key present
if [ "$key_ok" = true ] && [ -s /etc/apt/keyrings/amdrocm.gpg ]; then
    cat >/etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 signed-by=/etc/apt/keyrings/amdrocm.gpg] $ROCM_REPO_URL stable main
EOF
    cat >/etc/apt/sources.list.d/amdgpu.list <<EOF
deb [arch=amd64,i386 signed-by=/etc/apt/keyrings/amdrocm.gpg] $AMDGPU_REPO_URL noble main
EOF
else
    echo "WARNING: Could not fetch AMD ROCm GPG key; adding repos as trusted to continue (UNVERIFIED)."
    cat >/etc/apt/sources.list.d/rocm.list <<EOF
deb [arch=amd64 trusted=yes] $ROCM_REPO_URL stable main
EOF
    cat >/etc/apt/sources.list.d/amdgpu.list <<EOF
deb [arch=amd64,i386 trusted=yes] $AMDGPU_REPO_URL noble main
EOF
fi

# Update and detect remaining missing keys; if present, switch to trusted=yes for AMD repos
update_out2=$(apt-get update 2>&1 || true)
echo "$update_out2"
if echo "$update_out2" | grep -q "NO_PUBKEY"; then
    echo "Still missing pubkeys after fetch attempts. Enabling trusted=yes for AMD repos to continue."
    sed -i 's/signed-by=\/etc\/apt\/keyrings\/amdrocm.gpg/trusted=yes/g' /etc/apt/sources.list.d/rocm.list || true
    sed -i 's/signed-by=\/etc\/apt\/keyrings\/amdrocm.gpg/trusted=yes/g' /etc/apt/sources.list.d/amdgpu.list || true
    apt-get update || true
fi

# Remove conflicting packages if present (ignore errors)
apt-get remove -y libhsa-runtime64-1 libhsakmt1 || true

# Install additional packages and ROCm meta package (best-effort)
apt-get install -y --no-install-recommends libatomic1 libquadmath0 || true
apt-get install -y --no-install-recommends $ROCM_META_PKG || true

# Install WSL-specific HSA runtime (package name may vary; || true if absent)
apt-get install -y --no-install-recommends hsa-runtime-rocr4wsl-amdgpu hsa-runtime-rocr4wsl || true

# Build and install librocdxg (best-effort; failure does not abort the script)
# Requires WIN_SDK env var pointing to the Windows SDK Include directory, e.g.:
#   /mnt/c/Program Files (x86)/Windows Kits/10/Include/10.0.26100.0
# cmake expects: -DWIN_SDK=<path-to-sdk-shared-subdir>
build_librocdxg() {
    # Resolve the 'shared' subdirectory of the Windows SDK
    local win_sdk_shared=""
    if [ -n "${WIN_SDK:-}" ] && [ -d "${WIN_SDK}/shared" ]; then
        # Symlink avoids spaces in the path when passed to cmake
        ln -sfn "${WIN_SDK}/shared" /tmp/winsdk_shared 2>/dev/null || true
        win_sdk_shared="/tmp/winsdk_shared"
        echo "librocdxg: using Windows SDK shared headers -> ${WIN_SDK}/shared"
    elif [ -f "/usr/lib/wsl/include/ntstatus.h" ]; then
        win_sdk_shared="/usr/lib/wsl/include"
        echo "librocdxg: using /usr/lib/wsl/include"
    else
        echo "WARNING: WIN_SDK not set or Windows SDK 'shared' dir not found; skipping librocdxg build"
        return 1
    fi

    cd /tmp
    rm -rf librocdxg
    git clone https://github.com/ROCm/librocdxg.git || return 1
    cd librocdxg
    git checkout develop 2>&1 || true
    mkdir -p build && cd build
    cmake .. "-DWIN_SDK=${win_sdk_shared}" -DCMAKE_INSTALL_PREFIX=/opt/rocm 2>&1 || { echo "cmake failed"; return 1; }
    make -j"$(nproc)" 2>&1 || { echo "make failed"; return 1; }
    make install 2>&1 || true
}
build_librocdxg || echo "WARNING: librocdxg build failed (non-fatal; ROCm packages are still installed)"

# Post-install env
cat >/etc/profile.d/set-rocm-env.sh <<EOT
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/core/lib/rocm_sysdeps/lib:\$LD_LIBRARY_PATH
EOT
chmod +x /etc/profile.d/set-rocm-env.sh

# Verify
echo "=== ROCm files ==="
ls -l /opt/rocm* || true
echo "=== librocdxg ==="
ldconfig || true
